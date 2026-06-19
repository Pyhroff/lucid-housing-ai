"""
dev_smoke_m6.py — proves the multilingual translate-last layer (Milestone 6), OFFLINE.

The live translation needs an LLM key; here we test the architecture deterministically:
no-op for English, graceful English fallback when offline, and (via monkeypatch) that a
translation is applied as the LAST step with the English original preserved.

NOTE: the monkeypatch tests run LAST, because they replace module globals for the rest of the
process — the genuine offline checks must come first.
Run:  python dev_smoke_m6.py
"""
from __future__ import annotations

import os

# Force offline so the smoke suite stays deterministic and free even when a real key is in .env.
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

import core.translate as T
import pipeline as P
from agents.intake import naive_extract
from core.translate import translate
from pipeline import run_pipeline


def main() -> None:
    print("Lucid - Milestone 6: multilingual (reason-in-English, translate-last) [offline]")

    # 1. no-op for English / empty
    assert translate("You may qualify.", "en") == "You may qualify."
    assert translate("", "es") == ""

    # 2. offline (no key) -> graceful: returns the English text unchanged
    assert translate("You may qualify. Source: https://hud.gov", "es") == "You may qualify. Source: https://hud.gov"

    # 3. Spanish user, OFFLINE end-to-end -> answer stays English, no crash, english-original NOT set
    es_facts = naive_extract("desalojo en 5 dias, tengo dos hijos")
    assert es_facts.language == "es"
    res_off, _ = run_pipeline("desalojo en 5 dias, tengo dos hijos")
    assert res_off.guardian.final_message and res_off.guardian.final_message_en == ""
    print("  offline spanish user : English answer (graceful), no crash")

    # --- monkeypatch tests (these replace module globals for the rest of the process) ---

    # 4. monkeypatch the LLM -> translation applied, URL preserved by our contract
    T.complete = lambda system, user, json_mode=False: "[ES] " + user
    out = translate("You may qualify. Source: https://www.hud.gov/counseling", "es")
    assert out.startswith("[ES]") and "https://www.hud.gov/counseling" in out
    print(f"  translate(es) sample : {out[:58]}...")

    # 5. Spanish user WITH translation -> final translated, English original preserved
    P.translate = lambda text, lang: "[ES] " + text
    res_tr, _ = run_pipeline("desalojo en 5 dias, tengo dos hijos")
    assert res_tr.guardian.final_message.startswith("[ES]"), "final answer should be in the user's language"
    assert res_tr.guardian.final_message_en and not res_tr.guardian.final_message_en.startswith("[ES]"), \
        "English original must be preserved for the trace/eval"
    print("  translated spanish   : final_message=ES, final_message_en=EN preserved")

    print("\nOK - English no-op; offline falls back to English; translation applied LAST with English original kept.")


if __name__ == "__main__":
    main()
