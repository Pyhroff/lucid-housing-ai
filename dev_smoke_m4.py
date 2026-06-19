"""
dev_smoke_m4.py — proves derived confidence + the faithfulness guard (Milestone 4), OFFLINE.

The faithfulness guard is tested directly with crafted strings (no LLM needed): a grounded
message passes; a fabricated URL, an over-claim, and an ungrounded dollar amount are all rejected.
Run:  python dev_smoke_m4.py
"""
from __future__ import annotations

import os

# Force offline so the smoke suite stays deterministic and free even when a real key is in .env.
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from agents.eligibility import build_engine_result, deterministic_explanation, faithfulness_ok
from agents.intake import naive_extract
from core.confidence import derive_confidence
from core.retrieval import select_candidates
from core.rules_engine import determine


def main() -> None:
    print("Lucid - Milestone 4: derived confidence + faithfulness guard (offline)")

    # --- 1. confidence is DERIVED and returns its signal breakdown ---
    facts = naive_extract("They gave me a notice to leave in 5 days. I have two kids.")
    hits = determine(facts, select_candidates(facts))
    conf, detail = derive_confidence(facts, hits)
    print(f"  confidence (eviction)      : {conf}  signals={detail['signals']}")
    assert 0.0 <= conf <= 1.0
    assert set(detail["signals"]) == {"field_completeness", "match_clarity", "retrieval_strength"}

    # --- 2. the faithfulness guard ---
    grounded = deterministic_explanation(hits)
    ok, problems = faithfulness_ok(grounded, hits)
    assert ok, f"grounded message should pass, got {problems}"

    fake_url = grounded + "\nApply now at http://totally-fake-grant.example/claim"
    ok_u, p_u = faithfulness_ok(fake_url, hits)
    assert not ok_u and any("unknown-url" in x for x in p_u)

    over_claim = "You qualify for $5,000 guaranteed. Just pay the fee."
    ok_c, p_c = faithfulness_ok(over_claim, hits)
    assert not ok_c and any("over-claim" in x for x in p_c) and any("ungrounded-number" in x for x in p_c)
    print(f"  faithfulness guard rejects : {p_u + p_c}")

    # --- 3. offline build_engine_result stays grounded (no claims removed because no LLM ran) ---
    engine = build_engine_result(facts, hits)
    assert engine.explanation and engine.unsupported_claims_removed is False
    assert engine.confidence_signals, "expected confidence breakdown attached"

    # --- 4. abstention contrast: income-tested need + unknown income is LESS confident ---
    facts2 = naive_extract("I am behind on my rent and need rental assistance.")
    hits2 = determine(facts2, select_candidates(facts2))
    conf2, _ = derive_confidence(facts2, hits2)
    print(f"  confidence (rent, no income): {conf2}")
    assert conf2 < conf, "unknown-income rental case should be less confident than referral-rich eviction case"

    # --- 5. LLM-path failure handling (no real key: monkeypatch the LLM to misbehave) ---
    import agents.eligibility as elig

    elig.complete = lambda system, user, json_mode=False: None  # simulate a blocked/empty response
    expl, removed = elig.render_explanation(facts, hits)
    assert expl and removed is False, "a None LLM response must fall back to grounded WITHOUT crashing"

    elig.complete = lambda system, user, json_mode=False: "You qualify for $9,999 guaranteed http://fake.example"
    expl2, removed2 = elig.render_explanation(facts, hits)
    assert removed2 is True, "a hallucinated render must be caught and replaced"
    assert "fake.example" not in expl2, "the grounded fallback must not contain the fabricated URL"
    print("  llm-path guard            : None-response and hallucination both fall back to grounded")

    print("\nOK - confidence derived from signals; guard blocks fake URLs/over-claims/ungrounded $; LLM path fails closed.")


if __name__ == "__main__":
    main()
