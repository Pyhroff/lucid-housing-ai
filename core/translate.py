"""
core/translate.py — translate the final user-facing message into the user's language.

Fix #8 / Milestone 6 (reason-in-English, translate-last):
  The whole pipeline REASONS in English — the KB rule text, the rules engine, the
  faithfulness guard and the confidence signals all operate in English. ONLY the final,
  already-safe message is translated, as the very last step. This keeps the determination
  and the anti-hallucination checks in one language (no cross-lingual entailment problems)
  while still meeting the user where they are.

  Offline / no key / any failure -> returns the English text unchanged (graceful: the user
  still gets a usable, cited answer).
"""
from __future__ import annotations

from core.llm import complete

_TRANSLATE_SYSTEM = (
    "You are a translator for a housing-help assistant. Translate the message into the target "
    "language given as an ISO 639-1 code. RULES: keep ALL program names, web links (URLs), phone "
    "numbers and dollar amounts EXACTLY as written; preserve meaning precisely; use simple, "
    "~6th-grade wording. Return ONLY the translation — no notes, no preamble."
)


def translate(text: str, target_lang: str) -> str:
    """Translate `text` into `target_lang`. No-op for English/empty; graceful on any failure."""
    if not text or not text.strip() or not target_lang or target_lang.lower().startswith("en"):
        return text
    try:
        out = complete(f"{_TRANSLATE_SYSTEM}\nTarget language code: {target_lang}", text)
    except Exception:
        return text  # offline / blocked / error -> keep the English original
    return out.strip() if (out and out.strip()) else text
