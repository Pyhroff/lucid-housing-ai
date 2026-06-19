"""
dev_live_check.py — LIVE check of the real LLM path (needs a working key in .env).

Exercises ALL THREE LLM call sites in one run: intake (story->facts JSON), eligibility render
(plain-language rewrite behind the faithfulness guard), and translate (final answer -> Spanish).
Run:  python dev_live_check.py
"""
from __future__ import annotations

from core.llm import PROVIDER, complete
from pipeline import run_pipeline

ROSA_ES = (
    "Tengo un aviso de desalojo en 5 dias. Tengo dos hijos y no hablo bien ingles. "
    "No tengo abogado y no se que hacer."
)


def main() -> None:
    print(f"Provider: {PROVIDER}")
    print("1) basic LLM call ...")
    print("   ->", complete("You are terse.", "Reply with exactly the word: pong"))

    print("\n2) full pipeline, Spanish user (LLM intake + render + translate) ...")
    result, mode = run_pipeline(ROSA_ES)
    print("   intake mode :", mode, "(expect 'llm')")
    print("   language    :", result.intake.language)
    print("   need_type   :", result.intake.need_type)
    print("   confidence  :", result.engine.confidence)
    print("   rule hits   :", [(h.program[:34], h.status) for h in result.engine.rule_hits])
    print("   translated? :", bool(result.guardian.final_message_en))
    print("\n   --- final_message (user's language) ---")
    print(result.guardian.final_message)
    print("\n   --- final_message_en (English original, first 400 chars) ---")
    print((result.guardian.final_message_en or "(not translated)")[:400])


if __name__ == "__main__":
    main()
