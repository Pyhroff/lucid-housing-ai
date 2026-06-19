"""
core/counterfactual.py — "what would change your answer" (the wow feature).

Because Lucid's determination is made by a DETERMINISTIC rules engine — not an LLM — it can
compute *exactly* what would flip an eligibility result. For each income-tested program the
user does not currently qualify for, we surface the income threshold that WOULD qualify them.

This is precise, explainable, and **only possible because of the symbolic core** — a
probabilistic LLM cannot reliably tell you the exact counterfactual that changes its own answer.
That's a genuine edge over a plain chatbot.
"""
from __future__ import annotations

from core.rules_engine import determine
from core.schemas import IntakeFacts, KBRule

_BAND_LABEL = {"very_low": "very low", "low": "low", "moderate": "moderate", "above_moderate": "higher"}


def unlock_hints(facts: IntakeFacts, candidates: list[KBRule]) -> list[tuple[str, str]]:
    """Income-tested programs the user does NOT currently qualify for, with the income band that would.

    Returns [(program_name, income_band_label)]. Empty if the user already qualifies for everything
    income-tested (or there are no income-tested options) — so we only ever show actionable hints.
    """
    current_may = {h.program for h in determine(facts, candidates) if h.status == "may_qualify"}
    hints: list[tuple[str, str]] = []
    for rule in candidates:
        crit = rule.eligibility_criteria
        if crit.get("category") != "income_tested_benefit" or rule.program in current_may:
            continue
        cap = crit.get("income_band_max")
        if cap in _BAND_LABEL:
            hints.append((rule.program, _BAND_LABEL[cap]))
    return hints
