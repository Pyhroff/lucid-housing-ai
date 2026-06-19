"""
core/confidence.py — DERIVED confidence (not "calibrated"): computed from concrete signals.

WHY this file exists (direct answer to the qualifier feedback "how is confidence derived?"):
  Confidence is NOT an LLM guess. It is a documented weighted combination of three measurable
  signals:
    - field_completeness: how many of the facts that drive a determination we actually know,
    - match_clarity:      did we reach decisions, or are answers stuck at "need more info",
    - retrieval_strength: did we surface multiple relevant options.
  The weights are explicit design choices (tunable) and are returned alongside the score so the
  UI/eval can SHOW the breakdown. We say "derived", never "calibrated" — calibration would mean
  validating predicted confidence against observed accuracy, which the eval (M7) can add later.
"""
from __future__ import annotations

from core.schemas import IntakeFacts, RuleHit

# documented weights — design choices, reported in the trace
WEIGHTS = {"field_completeness": 0.5, "match_clarity": 0.3, "retrieval_strength": 0.2}
REQUIRED_FIELDS = ("need_type", "income_band", "household_size", "location")


def _field_completeness(facts: IntakeFacts) -> float:
    known = 0
    if facts.need_type:
        known += 1
    if facts.income_band and facts.income_band != "unknown":
        known += 1
    if facts.household_size is not None:
        known += 1
    if facts.location:
        known += 1
    return known / len(REQUIRED_FIELDS)


def _match_clarity(rule_hits: list[RuleHit]) -> float:
    """How cleanly we reached an actual eligibility DETERMINATION.

    Scoped to income-tested benefits only: referral/universal resources are `may_qualify` by
    construction, so counting them would pin clarity near 1.0 on every query and make confidence
    almost meaningless. If we made no income-tested determination at all (only surfaced free
    resources), clarity is a neutral 0.5 — we found options but determined nothing.
    """
    income_tested = [h for h in rule_hits if h.category == "income_tested_benefit"]
    if not income_tested:
        return 0.5
    need_more = sum(1 for h in income_tested if h.status == "need_more_info")
    return 1.0 - need_more / len(income_tested)


def _retrieval_strength(rule_hits: list[RuleHit]) -> float:
    may = sum(1 for h in rule_hits if h.status == "may_qualify")
    return min(1.0, may / 2)


def derive_confidence(facts: IntakeFacts, rule_hits: list[RuleHit]) -> tuple[float, dict]:
    """Return (confidence in 0..1, breakdown dict with weights + signals for transparency)."""
    signals = {
        "field_completeness": round(_field_completeness(facts), 2),
        "match_clarity": round(_match_clarity(rule_hits), 2),
        "retrieval_strength": round(_retrieval_strength(rule_hits), 2),
    }
    score = sum(WEIGHTS[k] * v for k, v in signals.items())
    return round(score, 2), {"weights": WEIGHTS, "signals": signals}
