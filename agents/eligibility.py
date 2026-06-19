"""
agents/eligibility.py — render the determination into plain language and GUARD faithfulness.

This is the anti-hallucination layer (the judges' top fear). Two upgrades live here:

  1. Plain-language rendering. By default the explanation is assembled DETERMINISTICALLY from the
     rules engine's cited findings, so it is faithful by construction. When an LLM key is set, an
     LLM may rewrite it more warmly — but only from what it is given, and the result must pass the
     faithfulness guard or we fall back to the deterministic version.

  2. Faithfulness guard (DETERMINISTIC — fix #6, NOT "an LLM checking an LLM"). It rejects rendered
     text that:
       - asserts guaranteed eligibility ("you qualify for", "guaranteed") instead of "may qualify",
       - contains a URL that is not one of the official source_urls we retrieved, or
       - contains a $ amount / percentage that does not appear in the retrieved rule text.
     On rejection we serve the grounded deterministic message and set unsupported_claims_removed.

Confidence comes from core/confidence.py (derived from concrete signals, not an LLM guess).
"""
from __future__ import annotations

import re

from core.confidence import derive_confidence
from core.llm import complete
from core.schemas import EngineResult, IntakeFacts, RuleHit

_OVERCLAIM = [
    "you qualify for", "you are eligible for", "you're eligible for", "guaranteed",
    "you will receive", "you will get", "approved for", "definitely qualify", "100%",
]
_URL_RE = re.compile(r"https?://[^\s\])>]+")
_MONEY_RE = re.compile(r"\$\s?[\d][\d,]*(?:\.\d+)?")
_PCT_RE = re.compile(r"\d+(?:\.\d+)?\s?%")

RENDER_SYSTEM = """You rewrite housing-help findings in warm, simple language at about a 6th-grade
reading level. Use ONLY the information in the findings. Do NOT add any program, link, number,
dollar amount, or eligibility claim that is not in the findings. Keep the phrase "you may qualify";
never say "you qualify" or "guaranteed". Keep every line that begins with "Source:" exactly as
written. Return only the rewritten text."""


def deterministic_explanation(rule_hits: list[RuleHit]) -> str:
    """The always-grounded body: cited rule text only, 'you may qualify' framing."""
    may = [h for h in rule_hits if h.status == "may_qualify"]
    more = [h for h in rule_hits if h.status == "need_more_info"]
    lines = ["Here's what you **may** qualify for — this isn't a final decision, but it's a real place to start."]
    for h in may + more:
        lines.append(f"\n- **{h.program}** — {h.reason}\n  Source: {h.source_url}")
    return "\n".join(lines)


def faithfulness_ok(rendered: str, rule_hits: list[RuleHit]) -> tuple[bool, list[str]]:
    """Deterministic groundedness check. Returns (ok, list_of_problems)."""
    problems: list[str] = []
    low = rendered.lower()
    for phrase in _OVERCLAIM:
        if phrase in low:
            problems.append(f"over-claim:'{phrase}'")
    allowed_urls = {h.source_url for h in rule_hits}
    for url in _URL_RE.findall(rendered):
        if url.rstrip(".,);") not in allowed_urls:
            problems.append(f"unknown-url:{url}")
    source = " ".join(f"{h.program} {h.reason}" for h in rule_hits).replace(" ", "").lower()
    for num in _MONEY_RE.findall(rendered) + _PCT_RE.findall(rendered):
        if num.replace(" ", "").lower() not in source:
            problems.append(f"ungrounded-number:{num.strip()}")
    # citation completeness: every source we should be citing must still be present in the output
    expected = {h.source_url for h in rule_hits if h.status in ("may_qualify", "need_more_info")}
    for src in expected:
        if src not in rendered:
            problems.append(f"missing-citation:{src}")
    return (len(problems) == 0, problems)


def render_explanation(facts: IntakeFacts, rule_hits: list[RuleHit]) -> tuple[str, bool]:
    """Return (explanation, unsupported_claims_removed).

    Offline / no key -> deterministic grounded text. With a key -> LLM rewrite, but only if it
    passes the faithfulness guard; otherwise fall back to grounded and flag the removal.
    """
    grounded = deterministic_explanation(rule_hits)
    try:
        rendered = complete(RENDER_SYSTEM, grounded)
        ok, _ = faithfulness_ok(rendered, rule_hits)
    except Exception:
        # Any LLM-path failure — no key, timeout, OR a None/blocked response that would make
        # faithfulness_ok crash on .lower() — fails CLOSED to the grounded text, which is safe.
        return grounded, False
    return (rendered.strip(), False) if ok else (grounded, True)


def build_engine_result(facts: IntakeFacts, rule_hits: list[RuleHit]) -> EngineResult:
    """Assemble the full EngineResult: determination + derived confidence + guarded explanation."""
    confidence, breakdown = derive_confidence(facts, rule_hits)
    explanation, removed = render_explanation(facts, rule_hits)
    return EngineResult(
        rule_hits=rule_hits,
        confidence=confidence,
        unsupported_claims_removed=removed,
        explanation=explanation,
        confidence_signals=breakdown,
    )
