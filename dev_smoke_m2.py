"""
dev_smoke_m2.py — proves the Milestone 2 end-to-end path runs OFFLINE (no API key).

Uses the deterministic keyword intake fallback so anyone without a key (or CI) can verify the
full Intake -> Retrieval -> Rules -> message path and that every claim is cited.
Run:  python dev_smoke_m2.py
"""
from __future__ import annotations

import os

# Force offline so the smoke suite stays deterministic and free even when a real key is in .env.
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from pipeline import run_pipeline

SCENARIO = (
    "They gave me a notice to leave in 5 days. I have two kids and no lawyer. "
    "Someone sent me a link that says pay $90 to hold my rental aid."
)
PASTED = "http://rental-aid-now.example/pay-90-to-hold"


def main() -> None:
    result, mode = run_pipeline(SCENARIO, PASTED)
    facts, hits = result.intake, result.engine.rule_hits

    print("Lucid - Milestone 2 end-to-end smoke test (offline)")
    print(f"  intake mode      : {mode}")
    print(f"  need_type        : {facts.need_type}")
    print(f"  urgency          : {facts.urgency}")
    print(f"  assumptions      : {facts.assumptions}")
    print(f"  rule hits        : {len(hits)}")
    for h in hits:
        print(f"     - [{h.status}] {h.program}")
    print(f"  confidence       : {result.engine.confidence}")
    print(f"  escalate_to_human: {result.guardian.escalate_to_human}")

    assert hits, "expected at least one rule hit"
    assert any(h.status == "may_qualify" for h in hits), "expected at least one may_qualify"
    assert all(h.source_url.startswith("http") for h in hits), "every hit must cite a source"
    assert result.guardian.final_message, "expected a final message"

    print("\nOK - end-to-end path works offline; every claim is cited; 'may qualify' framing.")


if __name__ == "__main__":
    main()
