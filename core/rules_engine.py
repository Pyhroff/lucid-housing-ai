"""
core/rules_engine.py — the deterministic eligibility determination. NO LLM, EVER.

WHY this file exists (the core trust argument — 30%-criterion material):
  Whether a user *may qualify* is decided here, by auditable Python over the curated rules,
  never by a language model. An LLM cannot hallucinate eligibility into existence because
  eligibility is decided by this function. The LLM's only job (upstream, in intake) is to
  parse the user's story into the structured facts this engine consumes.

  IMPORTANT (eval-report Fix #1): this engine is deterministic *given the facts*, but those
  facts come from a probabilistic LLM. So when a required fact is unknown we return
  `need_more_info` rather than guessing — and the UI confirms assumed facts with the user
  before this ever runs.
"""
from __future__ import annotations

from core.retrieval import category_of
from core.schemas import IntakeFacts, KBRule, RuleHit

# income bands ordered from lowest to highest income
_INCOME_RANK = {"very_low": 0, "low": 1, "moderate": 2, "above_moderate": 3}


def _income_ok(user_band: str, rule_max: str | None) -> bool | None:
    """True/False when decidable; None when we lack the user's income to decide."""
    if rule_max is None:
        return True  # no income test on this program/resource
    if user_band == "unknown" or user_band not in _INCOME_RANK:
        return None
    return _INCOME_RANK[user_band] <= _INCOME_RANK[rule_max]


def _determine_one(facts: IntakeFacts, rule: KBRule) -> RuleHit:
    crit = rule.eligibility_criteria
    summary = rule.plain_summary
    cat = category_of(rule)

    # Referral / universal resources are available regardless of income.
    if cat in ("universal_resource", "referral_resource"):
        return RuleHit(
            program=rule.program,
            status="may_qualify",
            reason=f"Available to you regardless of income. {summary}",
            source_url=rule.source_url,
            category=cat,
        )

    # Income-tested benefit.
    income_ok = _income_ok(facts.income_band, crit.get("income_band_max"))
    size_min = crit.get("household_size_min")
    size_ok = (
        True if (size_min is None or facts.household_size is None) else facts.household_size >= size_min
    )

    if income_ok is None:
        return RuleHit(
            program=rule.program,
            status="need_more_info",
            reason=f"To check this we need your household income. {summary}",
            source_url=rule.source_url,
            category=cat,
        )
    if income_ok and size_ok:
        return RuleHit(
            program=rule.program,
            status="may_qualify",
            reason=f"Your income appears within this program's limit. {summary}",
            source_url=rule.source_url,
            category=cat,
        )
    return RuleHit(
        program=rule.program,
        status="likely_not",
        reason=f"Your income may be above this program's limit, but rules vary — a caseworker can confirm. {summary}",
        source_url=rule.source_url,
        category=cat,
    )


def determine(facts: IntakeFacts, candidates: list[KBRule]) -> list[RuleHit]:
    """Run the deterministic determination over each candidate program.

    Ordered may_qualify -> need_more_info -> likely_not, so actionable options surface first.
    """
    hits = [_determine_one(facts, r) for r in candidates]
    order = {"may_qualify": 0, "need_more_info": 1, "likely_not": 2}
    hits.sort(key=lambda h: order.get(h.status, 3))
    return hits
