"""Offline regression checks for unknown and failed eligibility criteria.

Run with: python dev_smoke_m7.py
"""
from core.rules_engine import determine
from core.schemas import IntakeFacts, KBRule


def rule(*, income_max="very_low", household_min=2):
    return KBRule(
        program="Test housing program",
        jurisdiction="test",
        need_types=["rental_assistance"],
        eligibility_criteria={
            "category": "income_tested_benefit",
            "income_band_max": income_max,
            **({"household_size_min": household_min} if household_min is not None else {}),
        },
        plain_summary="A test program.",
        source_url="https://example.org/program",
        last_checked="2026-01-01",
        verified=False,
    )


def hit(facts, candidate):
    return determine(facts, [candidate])[0]


def main():
    # Missing required household size must not be treated as a passing condition.
    missing_size = IntakeFacts(language="en", need_type="rental_assistance", income_band="very_low")
    result = hit(missing_size, rule())
    assert result.status == "need_more_info", result
    assert "household size" in result.reason.lower(), result.reason

    # An explicitly undersized household fails for the correct reason, not income.
    undersized = IntakeFacts(
        language="en", need_type="rental_assistance",
        income_band="very_low", household_size=1,
    )
    result = hit(undersized, rule())
    assert result.status == "likely_not", result
    assert "household size" in result.reason.lower(), result.reason
    assert "income may be above" not in result.reason.lower(), result.reason

    # Income failure remains accurately explained.
    over_income = IntakeFacts(
        language="en", need_type="rental_assistance",
        income_band="low", household_size=2,
    )
    result = hit(over_income, rule())
    assert result.status == "likely_not", result
    assert "income may be above" in result.reason.lower(), result.reason

    # If no household-size rule exists, an unknown size does not block evaluation.
    no_size_rule = IntakeFacts(
        language="en", need_type="rental_assistance",
        income_band="very_low", household_size=None,
    )
    result = hit(no_size_rule, rule(household_min=None))
    assert result.status == "may_qualify", result

    print("OK - missing household size abstains; failed criteria have accurate explanations.")


if __name__ == "__main__":
    main()
