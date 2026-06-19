"""
pipeline.py — orchestrates the end-to-end path: Intake -> Retrieval -> Rules -> Eligibility -> Guardian.

run_pipeline() is a pure function that BOTH the UI and the eval call (so what we demo is exactly
what we measure). Stage ownership:
  - intake (agents/intake.py):      story -> structured facts (LLM, with offline keyword fallback)
  - retrieval + rules (core/):      select candidate rules, make the deterministic determination
  - eligibility (agents/eligibility.py): derived confidence + faithfulness-guarded plain-language body
  - guardian (agents/guardian.py):  scam + injection gate, escalation, final safe message
"""
from __future__ import annotations

from agents.eligibility import build_engine_result
from agents.guardian import run_guardian
from agents.intake import run_intake
from core.config import MAX_USER_TEXT_LEN
from core.retrieval import select_candidates
from core.rules_engine import determine
from core.schemas import IntakeFacts, LucidResult
from core.translate import translate


def run_pipeline(
    user_text: str,
    pasted_item: str | None = None,
    facts_override: IntakeFacts | None = None,
) -> tuple[LucidResult, str]:
    """Run the pipeline.

    If `facts_override` is given (the user-confirmed facts from the UI's confirmation step),
    intake is skipped. Returns (result, intake_mode) where mode is "llm", "offline-fallback",
    or "confirmed".

    The Guardian scans the ORIGINAL untrusted text (`user_text`) plus the pasted item, so an
    injection in the story itself is caught even when facts are user-confirmed (Fix #2).
    """
    # Cap untrusted input length before anything touches it (robustness + LLM cost guard).
    user_text = (user_text or "")[:MAX_USER_TEXT_LEN]
    if pasted_item:
        pasted_item = pasted_item[:MAX_USER_TEXT_LEN]

    if facts_override is not None:
        facts, mode = facts_override, "confirmed"
    else:
        facts, mode = run_intake(user_text, pasted_item)

    rule_hits = determine(facts, select_candidates(facts))
    engine = build_engine_result(facts, rule_hits)
    guardian = run_guardian(facts, engine, raw_text=user_text, pasted_item=pasted_item)

    # Translate-last (M6 / Fix #8): everything above reasoned in English; now render the final
    # safe message in the user's language. Offline/no-key -> unchanged English (graceful).
    if facts.language and not facts.language.lower().startswith("en"):
        translated = translate(guardian.final_message, facts.language)
        if translated != guardian.final_message:
            guardian = guardian.model_copy(
                update={"final_message_en": guardian.final_message, "final_message": translated}
            )

    return LucidResult(intake=facts, engine=engine, guardian=guardian), mode
