# Lucid

A multilingual, **neuro-symbolic** assistant that helps people under stress safely navigate a public support system (housing). *Neuro-symbolic* means: an **LLM handles the language** (parsing a messy human story), while a **deterministic rules engine makes the eligibility determination** — so the answer is explainable, cited to official sources, and **cannot fabricate eligibility**. It also checks pasted links for scams, resists prompt-injection, abstains to a human when unsure, and reports its own measured accuracy.

> USAII Global AI Hackathon 2026 · Undergraduate Track · Challenge Brief 4 ("Fix Systems People Depend On") · Team **Three Athaan**. Built with AI assistance (**Claude Code**) — disclosed in the submission.

---

## Build status

**Milestones 1–7 of 8 complete.** `app.py` runs end to end: story → *confirmed* facts → cited determination → a **Guardian** (scam + prompt-injection + bias), with **derived confidence**, a **faithfulness guard**, and **multilingual output**. A two-layer **evaluation harness** (`eval/`) measures it — deterministic regression + live LLM metrics sliced per persona. Works **offline** in English; multilingual + LLM-quality intake light up with a key in `.env`. Every claim grounded in a real official source.

| # | Milestone | State |
|---|---|---|
| 1 | Spine: `llm.py` + `schemas.py` + 9-rule verified KB | ✅ done |
| 2 | Thin end-to-end path (Intake → Rules → Retrieval → minimal UI) | ✅ done |
| 3 | Guardian (scam + injection caught; story treated as untrusted) | ✅ done |
| 4 | Derived confidence + faithfulness guard | ✅ done |
| 5 | Bias/exclusion check + hardened injection + transparency statement | ✅ done |
| 6 | Multilingual output (reason-in-English, translate-last) | ✅ done |
| 7 | **Eval harness + metrics table** (regression + live, per-persona) | ✅ done |
| 8 | UI polish + demo prep | ⏳ next |

**Eval headline** (`eval/EVAL_RESULTS.md`): rules-engine regression 100%; live extraction 91%; faithfulness grounded 100%; security shows *real* limits (scam recall 75%, injection 67%); equity audit flags underserved users (50% extraction) — the honest "where we underperform" finding.

> KB is 9 verified real rules (the optional stretch to ~15 just adds your demo city's PHA + legal-aid org).

Full plan and rationale: `../00_EVALUATION_REPORT.md` (§6).

## Setup

```bash
cd lucid
python -m venv .venv && .venv\Scripts\activate     # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env                              # then paste ONE provider's API key
```

## Verify (no API key needed)

```bash
python dev_smoke_m1.py   # data contracts: KB validates against schema, all models instantiate
python dev_smoke_m2.py   # full path offline: story -> facts -> cited options, every claim sourced
python dev_smoke_m3.py   # Guardian: scam + injection caught, determination UNCHANGED by the attack
python dev_smoke_m4.py   # derived confidence + faithfulness guard blocks fake URLs / over-claims / ungrounded $
python dev_smoke_m5.py   # bias check (soft for non-English, hard for underserved) + hardened injection
python dev_smoke_m6.py   # multilingual: English no-op, offline English fallback, translate-last w/ English original kept

# evaluation harness (the credibility centerpiece) — see eval/EVAL_RESULTS.md
python eval/run_eval.py          # regression line only (deterministic, free)
python eval/run_eval.py --live   # + live LLM metrics, sliced per persona (needs a key)
```

## Run the app

```bash
streamlit run app.py
```

Polished three-step UI: **Step 1** tell your story (or click a sidebar **example** — Rosa EN/ES, a scam link, an injection attempt), **Step 2** confirm the facts it *assumed* (the anti-hallucination step), **Step 3** cited option cards with colour-coded status badges, a confidence bar, scam/security/equity alerts, and expandable "how confidence was derived" + full reasoning trace. A "What Lucid does NOT do" transparency panel is always visible.

With a key in `.env`, intake uses the LLM. Without one, it falls back to keyword extraction and shows an "offline mode" banner — either way the app runs.

## Knowledge base — curated & web-verified (done)

`data/knowledge_base.json` holds **9 real US-federal programs**, each web-confirmed against its official `.gov`/`.org` source on 2026-06-16 (every row carries a `source_note` recording how it was confirmed). They span the whole housing-instability journey: vouchers, public housing, privately owned subsidized housing, 211 emergency help, the CFPB renter tool, LIHEAP, free legal aid, HUD housing counseling, and HUD Find Shelter.

Light follow-ups (optional, team's call):
- **Spot-check local dollar figures** for whichever demo city you pick (AMI thresholds, state LIHEAP limits) — the rows deliberately don't assert local numbers.
- **Push toward ~15** by adding your demo city's specific PHA and LSC-funded legal-aid org as their own rows (Milestone 6).

## The one human task that remains: defend it live

In the Round-3 panel, judges ask the 30%-weighted question directly: *"why does this need AI vs. a plain rules engine?"* Every member must answer that — and *"how do you stop the LLM hallucinating the facts the engine runs on?"* — cold. See `../00_EVALUATION_REPORT.md` §5. *(Parked for now per the team; not blocking the build.)*

## Open decision

**Region = US-federal by default** (matches the Rosa persona: Spanish-speaking, US-style eviction). The architecture is region-agnostic — only the KB content changes if the team prefers an Indian system. Confirm before Milestone 6.

## Repository layout

```
lucid/
├── core/
│   ├── llm.py            # provider-agnostic LLM wrapper (Gemini/Groq)  [M1 ✅]
│   ├── schemas.py        # Pydantic data contracts for every stage      [M1 ✅]
│   ├── config.py         # central thresholds, input cap, confidence band[polish ✅]
│   ├── rules_engine.py   # deterministic determination (no LLM)         [M2 ✅]
│   ├── retrieval.py      # KB lookup + citations                        [M2 ✅]
│   └── confidence.py     # derived-confidence calculation               [M4 ✅]
├── agents/
│   ├── intake.py         # Agent 1: story -> structured facts           [M2 ✅]
│   ├── eligibility.py    # render + faithfulness guard + confidence     [M4 ✅]
│   └── guardian.py       # Agent 3: scam + injection + bias + escalate    [M3/M5 ✅]
├── data/
│   ├── knowledge_base.json   # 9 real rules, web-verified                [M1 ✅ curated]
│   └── eval_scenarios.json   # 23 labelled synthetic test cases          [M7 ✅]
├── eval/run_eval.py          # regression + live metrics, per-persona    [M7 ✅]
├── eval/EVAL_RESULTS.md      # pitch-ready results table + honest caveats [M7 ✅]
├── pipeline.py               # run_pipeline(): Intake -> Engine -> Guardian [M2]
├── app.py                    # Streamlit UI                             [M2]
├── dev_smoke_m1.py           # offline check of the M1 spine            [M1 ✅]
├── requirements.txt
├── .env.example
└── README.md
```
