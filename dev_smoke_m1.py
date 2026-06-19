"""
dev_smoke_m1.py — offline sanity check for the Milestone 1 spine.

Runs with NO API key and NO vendor SDK installed (llm.py imports its SDKs lazily). It
proves the data contracts hold: the knowledge base parses against the KBRule schema and
every Pydantic model instantiates. Run:  python dev_smoke_m1.py
"""
from __future__ import annotations

import json
from pathlib import Path

from core.schemas import (
    EngineResult,
    GuardianResult,
    IntakeFacts,
    KBRule,
    LucidResult,
    RuleHit,
)

KB_PATH = Path(__file__).parent / "data" / "knowledge_base.json"


def check_knowledge_base() -> int:
    raw = json.loads(KB_PATH.read_text(encoding="utf-8"))
    rules = [KBRule(**r) for r in raw["rules"]]  # raises if any row is malformed
    unverified = [r.program for r in rules if not r.verified]
    print(f"  knowledge_base.json: {len(rules)} rule(s) parsed OK against KBRule schema.")
    if unverified:
        print(f"  TEAM TODO - {len(unverified)} rule(s) still verified=false:")
        for name in unverified:
            print(f"      - {name}")
    return len(rules)


def check_schemas() -> None:
    facts = IntakeFacts(
        language="es",
        need_type="eviction_help",
        household_size=4,
        income_band="very_low",
        location="example city",
        urgency="high",
        situation_flags=["eviction_notice", "has_children"],
        item_to_verify="http://example-scam.test/pay-to-hold-aid",
        stated_fields=["need_type", "language", "urgency"],
        assumptions=["household_size", "income_band"],
    )
    engine = EngineResult(
        rule_hits=[
            RuleHit(
                program="Housing Choice Voucher Program (Section 8)",
                status="may_qualify",
                reason="Income at or below the very-low threshold; household size meets the minimum.",
                source_url="https://www.hud.gov/helping-americans/housing-choice-vouchers",
            )
        ],
        confidence=0.74,
        unsupported_claims_removed=True,
    )
    guardian = GuardianResult(
        scam_flags=["upfront_fee_request"],
        injection_detected=False,
        bias_flag=False,
        escalate_to_human=False,
        final_message="You may qualify for rental help. The site you pasted asks for a fee — real aid is free.",
    )
    LucidResult(intake=facts, engine=engine, guardian=guardian)
    print("  schemas: IntakeFacts / EngineResult / GuardianResult / LucidResult all instantiate OK.")


if __name__ == "__main__":
    print("Lucid - Milestone 1 spine smoke test")
    n = check_knowledge_base()
    check_schemas()
    print(f"\nOK - spine is sound ({n} seed rules). Next: Milestone 2 (thin end-to-end path).")
