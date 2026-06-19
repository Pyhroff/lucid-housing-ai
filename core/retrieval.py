"""
core/retrieval.py — load the knowledge base and select relevant rules + citations.

WHY this file exists:
  This is the "retrieval" half of the neuro-symbolic core: a *deterministic* lookup over the
  curated KB. We deliberately do NOT brand this "RAG" — with ~9 curated rules a transparent
  keyword/field match is honest and sufficient; the rules engine, not vector search, carries
  the reasoning. Every rule we surface carries its official source_url so every claim cites a
  source (the "receipts" design principle).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from core.schemas import IntakeFacts, KBRule

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"


@lru_cache(maxsize=1)
def load_kb(path: str | None = None) -> tuple[KBRule, ...]:
    """Load and validate the knowledge base once (cached)."""
    p = Path(path) if path else KB_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    return tuple(KBRule(**r) for r in raw["rules"])


def category_of(rule: KBRule) -> str:
    """How the rules engine should treat this rule (see knowledge_base.json _meta.categories)."""
    return rule.eligibility_criteria.get("category", "income_tested_benefit")


def select_candidates(facts: IntakeFacts, kb: tuple[KBRule, ...] | None = None) -> list[KBRule]:
    """Return rules relevant to the user's need, plus always-available safety-net resources.

    Selection is intentionally simple and transparent:
      - any rule whose need_types include the user's need_type, PLUS
      - every universal_resource (free counseling, crisis shelter) so the most vulnerable
        users always see a safety net even when they may not qualify for a benefit.
    """
    rules = kb if kb is not None else load_kb()
    need = (facts.need_type or "").strip().lower()
    chosen: list[KBRule] = []
    seen: set[str] = set()
    for rule in rules:
        matches_need = need in [n.lower() for n in rule.need_types]
        is_universal = category_of(rule) == "universal_resource"
        if (matches_need or is_universal) and rule.program not in seen:
            chosen.append(rule)
            seen.add(rule.program)
    return chosen
