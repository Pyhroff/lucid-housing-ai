"""
core/config.py — central tunable constants and small display helpers.

Single source of truth for thresholds and limits so they are not scattered across modules.
"""
from __future__ import annotations

CONFIDENCE_THRESHOLD = 0.6   # below this the Guardian escalates to a human
MAX_USER_TEXT_LEN = 4000     # cap on untrusted input length (robustness + LLM cost guard)


def confidence_band(score: float) -> str:
    """Map a 0..1 confidence to a coarse band for display. 'low' (<0.6) implies escalation."""
    if score >= 0.8:
        return "high"
    if score >= CONFIDENCE_THRESHOLD:
        return "moderate"
    return "low"
