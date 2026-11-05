"""Unit tests for Lucid's deterministic core: rules engine, derived confidence, counterfactuals, retrieval.

These are the parts the README calls "structurally incapable of fabricating eligibility", so they are
pinned against both synthetic rules (each branch) and the real curated knowledge base.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.confidence import WEIGHTS, derive_confidence  # noqa: E402
from core.counterfactual import unlock_hints  # noqa: E402
from core.retrieval import load_kb, select_candidates  # noqa: E402
from core.rules_engine import determine  # noqa: E402
from core.schemas import IntakeFacts, KBRule, RuleHit  # noqa: E402


def facts(**overrides) -> IntakeFacts:
    base = dict(language="en", need_type="rental_assistance", income_band="low", household_size=2, location="Austin")
    return IntakeFacts(**{**base, **overrides})


def rule(program="P", category="income_tested_benefit", income_max="low", size_min=None, need_types=("rental_assistance",)):
    crit = {"category": category}
    if income_max is not None:
        crit["income_band_max"] = income_max
    if size_min is not None:
        crit["household_size_min"] = size_min
    return KBRule(
        program=program,
        jurisdiction="US",
        need_types=list(need_types),
        eligibility_criteria=crit,
        plain_summary=f"{program} summary.",
        source_url=f"https://example.gov/{program}",
        last_checked="2026-01-01",
    )


def hit(status, category="income_tested_benefit", program="P"):
    return RuleHit(program=program, status=status, reason="r", source_url="https://x", category=category)


# --- rules engine ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("income", "cap", "expected"),
    [
        ("very_low", "low", "may_qualify"),
        ("low", "low", "may_qualify"),
        ("moderate", "low", "likely_not"),
        ("above_moderate", "moderate", "likely_not"),
        ("unknown", "low", "need_more_info"),
    ],
)
def test_income_band_against_cap(income, cap, expected):
    (result,) = determine(facts(income_band=income), [rule(income_max=cap)])
    assert result.status == expected


@pytest.mark.parametrize(
    ("size", "size_min", "expected"),
    [(3, 3, "may_qualify"), (4, 3, "may_qualify"), (2, 3, "likely_not"), (None, 3, "need_more_info"), (None, None, "may_qualify")],
)
def test_household_size_condition(size, size_min, expected):
    (result,) = determine(facts(household_size=size), [rule(size_min=size_min)])
    assert result.status == expected


def test_missing_income_is_reported_before_missing_size():
    (result,) = determine(facts(income_band="unknown", household_size=None), [rule(size_min=1)])
    assert result.status == "need_more_info"
    assert result.reason.startswith("To check this we need your household income.")


def test_likely_not_names_every_failed_condition():
    (result,) = determine(facts(income_band="moderate", household_size=1), [rule(income_max="low", size_min=3)])
    assert result.status == "likely_not"
    assert result.reason.startswith(
        "Your income may be above this program's limit and your household size may not meet this program's requirement"
    )


@pytest.mark.parametrize("category", ["universal_resource", "referral_resource"])
def test_resources_are_available_regardless_of_income_or_size(category):
    (result,) = determine(facts(income_band="above_moderate", household_size=None), [rule(category=category, size_min=5)])
    assert result.status == "may_qualify"
    assert result.category == category


def test_rule_without_income_test_does_not_need_income():
    (result,) = determine(facts(income_band="unknown"), [rule(income_max=None)])
    assert result.status == "may_qualify"


def test_hits_are_ordered_actionable_first_and_cite_their_source():
    candidates = [rule("No", income_max="very_low"), rule("Maybe", size_min=9), rule("Yes", income_max="moderate")]
    hits = determine(facts(income_band="low", household_size=None), candidates)
    assert [(h.program, h.status) for h in hits] == [
        ("Yes", "may_qualify"),
        ("Maybe", "need_more_info"),
        ("No", "likely_not"),
    ]
    assert all(h.source_url == f"https://example.gov/{h.program}" for h in hits)


def test_reasons_only_repeat_the_rule_summary():
    for result in determine(facts(), [rule("A"), rule("B", income_max="very_low"), rule("C", category="referral_resource")]):
        assert result.reason.endswith(f"{result.program} summary.")


# --- derived confidence ---------------------------------------------------------


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_confidence_full_information_and_clear_matches():
    score, breakdown = derive_confidence(facts(), [hit("may_qualify", program="A"), hit("likely_not", program="B")])
    assert breakdown["signals"] == {"field_completeness": 1.0, "match_clarity": 1.0, "retrieval_strength": 0.5}
    assert score == pytest.approx(0.9)
    assert breakdown["weights"] == WEIGHTS


def test_confidence_drops_with_missing_facts_and_undecided_matches():
    score, breakdown = derive_confidence(
        facts(income_band="unknown", household_size=None, location=None),
        [hit("need_more_info"), hit("may_qualify", category="universal_resource")],
    )
    assert breakdown["signals"] == {"field_completeness": 0.25, "match_clarity": 0.0, "retrieval_strength": 0.5}
    assert score == pytest.approx(0.23)


def test_free_resources_alone_give_neutral_clarity():
    _, breakdown = derive_confidence(facts(), [hit("may_qualify", category="referral_resource")])
    assert breakdown["signals"]["match_clarity"] == 0.5


@pytest.mark.parametrize(
    "hits", [[], [hit("may_qualify")] * 5, [hit("need_more_info")] * 3, [hit("likely_not"), hit("may_qualify", category="universal_resource")]]
)
def test_confidence_is_always_within_bounds(hits):
    for f in (facts(), facts(income_band="unknown", household_size=None, location=None, need_type="")):
        score, _ = derive_confidence(f, hits)
        assert 0.0 <= score <= 1.0


# --- counterfactuals ------------------------------------------------------------


def test_hint_when_income_is_the_only_blocker():
    assert unlock_hints(facts(income_band="moderate"), [rule("P", income_max="low")]) == [("P", "low")]


def test_hint_when_income_is_unknown():
    assert unlock_hints(facts(income_band="unknown"), [rule("P", income_max="very_low")]) == [("P", "very low")]


def test_no_hint_for_programs_already_qualified_for():
    assert unlock_hints(facts(income_band="very_low"), [rule("P", income_max="low")]) == []


def test_no_income_hint_when_household_size_is_the_blocker():
    # Income is already within the cap; telling the user it "opens up" at that income would be false.
    assert unlock_hints(facts(income_band="low", household_size=1), [rule("P", income_max="low", size_min=3)]) == []
    assert unlock_hints(facts(income_band="low", household_size=None), [rule("P", income_max="low", size_min=1)]) == []


def test_no_hint_when_lowering_income_would_not_be_enough():
    assert unlock_hints(facts(income_band="moderate", household_size=1), [rule("P", income_max="low", size_min=3)]) == []


def test_no_hints_for_resources():
    assert unlock_hints(facts(income_band="above_moderate"), [rule("R", category="referral_resource")]) == []


def test_every_hint_is_a_true_counterfactual_on_the_real_knowledge_base():
    bands = ["very_low", "low", "moderate", "above_moderate", "unknown"]
    for income in bands:
        for size in (None, 1, 4):
            f = facts(income_band=income, household_size=size)
            candidates = select_candidates(f)
            before = {h.program: h.status for h in determine(f, candidates)}
            label_to_band = {"very low": "very_low", "low": "low", "moderate": "moderate", "higher": "above_moderate"}
            for program, label in unlock_hints(f, candidates):
                assert before[program] != "may_qualify"
                after = determine(f.model_copy(update={"income_band": label_to_band[label]}), candidates)
                assert {h.program: h.status for h in after}[program] == "may_qualify", (income, size, program)


# --- retrieval / knowledge base -------------------------------------------------


def test_knowledge_base_loads_and_every_rule_cites_an_https_source():
    kb = load_kb()
    assert len(kb) >= 9
    assert all(r.source_url.startswith("https://") for r in kb)
    assert len({r.program for r in kb}) == len(kb)


def test_income_tested_rules_use_known_bands():
    for r in load_kb():
        crit = r.eligibility_criteria
        if crit.get("category", "income_tested_benefit") == "income_tested_benefit":
            assert crit.get("income_band_max") in {"very_low", "low", "moderate", "above_moderate"}, r.program


def test_universal_resources_are_always_selected():
    universal = {r.program for r in load_kb() if r.eligibility_criteria.get("category") == "universal_resource"}
    assert universal
    for need in ("rental_assistance", "something_unrelated", ""):
        assert universal <= {r.program for r in select_candidates(facts(need_type=need))}


def test_selection_has_no_duplicates_and_matches_need_case_insensitively():
    lower = select_candidates(facts(need_type="rental_assistance"))
    upper = select_candidates(facts(need_type="  RENTAL_ASSISTANCE "))
    assert [r.program for r in lower] == [r.program for r in upper]
    assert len({r.program for r in lower}) == len(lower)
