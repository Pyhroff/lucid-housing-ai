# Polish pass — change log (through Milestone 6)

**Goal:** make Lucid feel *human* (for a stressed real user like Rosa) and *distinctive* (memorable for AI-practitioner judges), without touching the verified pipeline logic. Every change below is **presentation, copy, or test-hygiene** — `run_intake()` / `run_pipeline()` and all agent/core logic are unchanged, so the six smoke suites still pass.

Judges noted: an AI Principal Engineer + a Booz-Allen technologist. The rubric *punishes* buzzwords and *rewards* a clear end-to-end user journey + a justified "why AI vs. rules" story — so the changes lean into plain-language credibility, not jargon.

---

## 1. Backend (1 line) — `agents/eligibility.py`
- **`deterministic_explanation()` opening line** changed from
  `"You **may** qualify for the options below — this is not a final decision."`
  → `"Here's what you **may** qualify for — this isn't a final decision, but it's a real place to start."`
- **Why:** warmer, gives hope without over-claiming; still keeps the "**may** qualify" framing the Responsible-AI rules require. Verified it still passes the faithfulness guard (no over-claim phrase introduced).

## 2. Frontend — `app.py` (rebuilt presentation; same logic)

| # | Change | Why / which criterion it serves |
|---|--------|----------------------------------|
| 2.1 | **New identity: navigation theme** — icon `🧭`, name *Lucid*, tagline *"Find your way through housing help — calmly, in your language, with real sources you can check."* | The brief's verb is literally *"navigate a system."* A compass is on-theme, hopeful, and more distinctive than a generic house. (Memorability — Problem Understanding / Impact.) |
| 2.2 | **Trust strip** under the hero: `🔒 No sign-in · 🗄️ We store nothing · 📎 Every claim has a source · 👤 A person makes the final call` | Signals privacy-by-design, citations, and human-in-the-loop at a glance. (Responsible AI.) |
| 2.3 | **"How Lucid works — and why you can trust it"** expander: a 4-step plain-language explanation (AI reads your story → a *separate rules engine, not the AI*, decides → every answer cites an official source → unsure → a real person). | This is the neuro-symbolic "why AI vs. a rules engine" argument **in human words, no buzzwords** — the 30%-weighted AI-Reasoning question, surfaced where a judge will see it. |
| 2.4 | **3-step journey stepper** (`Tell us → Confirm → Your options`) that highlights the current step. | Makes the end-to-end user journey *visible* (the Judge's Lens rewards exactly this) and reduces overwhelm for a stressed user. |
| 2.5 | **Humanized copy throughout** — warm, dignified, calm. e.g. Step 1 sub-line *"In your own words. There's no wrong way to say it."*; empty-input nudge *"Whenever you're ready…"*; Step 2 *"We don't check anything until you confirm. You're in control."* | Inclusion + dignity for someone in crisis. Tone kept **calm and respectful, not cutesy** (eviction is serious). (Impact & Insight.) |
| 2.6 | **Crisis-sensitive callout** — when `urgency == high`, a gentle: *"This sounds urgent — take a breath. You have options right now, and help is free… calling 2-1-1 is the fastest step."* | Meets the "real person under time pressure" constraint the brief calls out. |
| 2.7 | **Humanized income field** — dropdown now reads *"I'm not sure / Very low income / Low income / Moderate income"* (mapped to the internal bands) instead of raw `very_low` etc. | Removes jargon for low-literacy users; the determination still runs on the same enum. |
| 2.8 | **"Answer me in…" language selector** (7 languages, defaults to detected) in Step 2. | Makes the M6 multilingual feature explicit and user-controlled (Social Impact). |
| 2.9 | **Confidence shown with a plain-language meaning** — e.g. *"How sure we are: 47% — We're not sure here; please have a real person check this."* | Turns a number into honest, calibrated-feeling guidance (Responsible AI / over-reliance mitigation). |
| 2.10 | **Renamed the trace expanders** to *"Why are we this sure?"* and *"📎 See the proof — every claim and its official source."* | "Proof / receipts" framing is memorable and reinforces "cite everything." |
| 2.11 | **Refined visual system** — CSS variables (calm teal `#0b6e6e` + warm accent `#d9663b`), status-colored option cards with left borders + pill badges, a thin colored confidence bar, theme-resilient translucent backgrounds. | Distinctive but tasteful — looks intentional, not default-Streamlit. |
| 2.12 | **Safety/equity messaging warmed** — scam alert, injection note, and equity note rephrased to be supportive rather than clinical, still accurate. | Inclusion without losing the security signal. |
| — | Kept: the **confirm-before-deciding** step (Fix #1), `html.escape` on all dynamic text, results persisted in `session_state` (the expander-rerun fix), and the "What Lucid does NOT do" panel. | No regressions to the safety/robustness work. |

## 3. Test hygiene — `dev_smoke_m2..m6.py`
- Added a 2-line **force-offline guard** (`os.environ["GROQ_API_KEY"]="" / GEMINI_API_KEY=""`) at the top of each smoke test.
- **Why:** now that a real key lives in `.env`, python-dotenv auto-discovers it from `core/llm.py`, so the smoke tests had started making **live API calls** (slow, costs, rate-limit-flaky, and it broke M6's offline assertion). The smoke suite must stay deterministic and free; the **live** path is covered separately by `dev_live_check.py`.

---

## Verification
- ✅ All six offline suites pass (`dev_smoke_m1..m6.py`) — logic untouched.
- ✅ `app.py` compiles; the new hero/tagline, trust strip, "How Lucid works", and journey stepper confirmed rendering on the live server.
- ✅ Live LLM path still works (`dev_live_check.py`): Spanish in → cited Spanish answer out.
- Tone intentionally kept dignified given the subject (eviction/housing crisis) — warmth, not whimsy.

---

## 4. Hotfixes after the first live screenshot
- **Red primary button → calm teal.** Streamlit's default `primaryColor` is red (`#FF4B4B`), which clashed with the identity and read as "danger" on a *"Help me understand"* button. Added **`.streamlit/config.toml`** with `primaryColor = "#0b6e6e"`. Verified: the button now computes to `rgb(11,110,110)`.
- **Offline-mode copy was inaccurate.** It said *"No AI key is set"* even when a key exists; the real cause can also be the model being briefly unreachable. Reworded to *"the AI step didn't run just now (no key, or it was unreachable)…"*.
- **Note on the screenshot's offline mode:** the live LLM path is confirmed working (`dev_live_check.py` → `pong`, intake mode `llm`, Spanish extraction). The offline-fallback seen in the preview is **environmental** — the preview sandbox has no outbound network. Running `streamlit run app.py` on a networked machine uses Groq; the sidebar shows *"Running on: AI + rules"* when it does.

---

## 5. Copy: centralized + situation-aware (per request)
- **All user-facing text now lives in one file: `core/ui_copy.py`.** Every label, button, heading, hero line, trust-strip item, expander title, and message is a constant there — rewrite any wording in one place without touching `app.py`. `app.py` imports it as `C` and only does layout/flow.
- **Situational messages now ADAPT** instead of repeating one canned line:
  - `crisis_note(need, urgency)` → only fires on high urgency, and the tail changes by situation: **eviction →** "ask about free legal aid — a lawyer can sometimes pause an eviction"; **utilities →** the energy-help hotline; **shelter/homelessness →** HUD Find Shelter; **general →** 2-1-1.
  - `step3_intro(has_options, need)` → a different opening line for eviction / utilities / shelter / rights / "no clear match."
- **Why:** addresses "not exactly the same thing over and over" — different users in different situations now see different, *relevant* wording (context-aware, not random — appropriate for a serious tool).
- Verified: app renders with zero exceptions; the adaptive functions return distinct strings per need; all 6 smoke suites still pass.

---

## 6. `above_moderate` income band (the "we correctly say NO" upgrade)
- **What:** added a fifth income band `above_moderate` (rank 3, above the `moderate` cap of every program). A clearly-high earner ("$250k a year", "six figures") now gets an explicit **"likely not a fit — your income is above the limit"** on every income-tested program, instead of being parked at "unknown."
- **Files:** `core/schemas.py` (enum), `core/rules_engine.py` (`_INCOME_RANK`), `agents/intake.py` (income-mapping prompt), `core/ui_copy.py` (a "Higher income" dropdown option), and eval scenario `rent-en-moderate` ($250k) re-labelled `above_moderate`.
- **Why it impresses judges:** strengthens the Responsible-AI story — Lucid doesn't just say "yes" to everyone; it correctly and explicitly tells people when they *don't* qualify. (This was the gap surfaced during testing.)
- Verified: all 6 smoke suites pass; eval regression stays 100% (23/23) with the new band; nothing else changed.

---

## 7. Warm redesign + "win-level" features (user-directed)
**Visual:** switched to a **warm, premium, light** theme (`.streamlit/config.toml` base=light, cream `#faf7f2` canvas, terracotta `#c2613f` CTAs) with an **editorial serif hero** (Georgia), soft rounded white cards with hover lift, warm pills/stepper. Reads as *caring and trustworthy* — the right tone for a stressed, vulnerable user (and for Impact/Social-Impact judges). Verified live: cream bg, serif hero, terracotta buttons, zero exceptions.

**New features:**
- 🌟 **Counterfactual explanations (`core/counterfactual.py`)** — "Section 8 opens up if your household income is *very low* or below." Computed by re-running the *deterministic* engine, so it's exact — a genuine edge over any LLM (a chatbot can't reliably state the counterfactual that flips its own answer). Shown as a warm `.cf` box in Step 3.
- 🔊 **Voice / listen** — a client-side `SpeechSynthesis` button reads the answer aloud **in the user's language** (free, offline, accessibility win for low-literacy / visually-impaired users).
- 📊 **Confidence calibration** in the eval — bins scenarios by confidence band and shows low→escalates 100%, high→11% (the 11% is deliberate equity routing). Confidence is *meaningful*, shown honestly.
- 🛡️ **Adversarial robustness score** — a single combined "caught 5/7 planted attacks (71%)" headline in the eval.
- Verified: compile clean, all 6 smoke suites pass, eval regression 100%, counterfactual returns correct thresholds.
