"""core/rules_engine.py — deterministic eligibility determination; no LLM calls."""
from __future__ import annotations

from core.retrieval import category_of
from core.schemas import IntakeFacts, KBRule, RuleHit

# Income bands ordered from lowest to highest income.
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

    income_ok = _income_ok(facts.income_band, crit.get("income_band_max"))
    size_min = crit.get("household_size_min")
    # A configured household-size condition is not satisfied merely because the
    # intake did not capture household size. Missing is unknown, not a pass.
    size_ok = (
        True if size_min is None
        else None if facts.household_size is None
        else facts.household_size >= size_min
    )

    if income_ok is None:
        return RuleHit(
            program=rule.program,
            status="need_more_info",
            reason=f"To check this we need your household income. {summary}",
            source_url=rule.source_url,
            category=cat,
        )
    if size_ok is None:
        return RuleHit(
            program=rule.program,
            status="need_more_info",
            reason=f"To check this we need your household size. {summary}",
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

    failed_conditions: list[str] = []
    if not income_ok:
        failed_conditions.append("your income may be above this program's limit")
    if not size_ok:
        failed_conditions.append("your household size may not meet this program's requirement")
    reason = " and ".join(failed_conditions).capitalize()
    return RuleHit(
        program=rule.program,
        status="likely_not",
        reason=f"{reason}, but rules vary — a caseworker can confirm. {summary}",
        source_url=rule.source_url,
        category=cat,
    )


def determine(facts: IntakeFacts, candidates: list[KBRule]) -> list[RuleHit]:
    """Run deterministic determination; surface actionable and uncertain results first."""
    hits = [_determine_one(facts, rule) for rule in candidates]
    order = {"may_qualify": 0, "need_more_info": 1, "likely_not": 2}
    hits.sort(key=lambda hit: order.get(hit.status, 3))
    return hits
