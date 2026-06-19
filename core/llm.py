"""
core/llm.py — the single, provider-agnostic LLM wrapper.

WHY this file exists:
  Every LLM call in Lucid goes through complete(). Centralizing the provider, retries,
  timeouts and JSON-mode here means the rest of the codebase never touches a vendor SDK.
  Swapping Gemini <-> Groq is a one-line .env change (LLM_PROVIDER=gemini|groq) — exactly
  the "put the provider behind one wrapper so it can be swapped" instruction in the spec.

DESIGN CHOICES:
  - Vendor SDKs are imported *lazily* inside each provider function, so importing this
    module (in unit tests, the eval, or the smoke test) does NOT require any SDK to be
    installed. You only need the SDK for the provider you actually use.
  - Retries use exponential backoff. Transient rate-limit / 5xx errors are the #1 cause
    of dead hackathon demos (eval report Fix #7). Demo-mode response caching lives one
    layer up in the pipeline so the live walkthrough never depends on a cold API call.
"""
from __future__ import annotations

import os
import time

from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))


class LLMError(RuntimeError):
    """Raised when a call fails unrecoverably. Callers should fail safe (escalate)."""


def complete(system: str, user: str, json_mode: bool = False) -> str:
    """Run one LLM completion and return the raw text response.

    Args:
        system: the system / role instruction. TRUSTED — authored by us only.
        user:   the user-turn content. MAY contain untrusted text; callers passing
                user-pasted content must keep it clearly delimited and must never let its
                output change control flow (see agents/guardian.py).
        json_mode: ask the provider for strict JSON output (used by Intake).

    Returns:
        The model's text output (a JSON string when json_mode=True).

    Raises:
        LLMError: on configuration errors, or after MAX_RETRIES transient failures.
    """
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if PROVIDER == "gemini":
                return _complete_gemini(system, user, json_mode)
            if PROVIDER == "groq":
                return _complete_groq(system, user, json_mode)
            raise LLMError(f"Unknown LLM_PROVIDER={PROVIDER!r}; use 'gemini' or 'groq'.")
        except LLMError:
            raise  # config errors are not retryable
        except Exception as e:  # transient: rate limit, timeout, 5xx, transport
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)  # 2s, 4s, ...
    raise LLMError(f"LLM call failed after {MAX_RETRIES} attempts: {last_err}")


def _complete_gemini(system: str, user: str, json_mode: bool) -> str:
    # Check the key BEFORE importing, so offline/no-key runs never touch the SDK.
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY is not set (see .env.example).")
    from google import genai  # lazy import — current SDK (google-genai), not the deprecated one
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json" if json_mode else None,
    )
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=user, config=config)
    return resp.text


def _complete_groq(system: str, user: str, json_mode: bool) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise LLMError("GROQ_API_KEY is not set (see .env.example).")
    from groq import Groq  # lazy import — only needed for this provider

    client = Groq(api_key=api_key, timeout=REQUEST_TIMEOUT)
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    # Manual smoke test — requires a configured provider + API key in .env.
    print(complete("You are a terse assistant.", "Reply with the single word: pong"))
