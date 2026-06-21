# Lucid — Model Card & Responsible-AI Statement

*A model card is how serious AI teams document what a system is for, where it fails, and how it's kept safe. This is ours. It is deliberately honest about limitations — that honesty is the point.*

---

## 1. Intended use
Lucid helps an individual under stress **understand and take the next step** toward public housing support — in plain language, in their own language, with every claim tied to an official source. It is an **information and navigation aid**, designed especially for the people these systems fail most: non-English speakers, low-literacy users, people in crisis, and people being targeted by scammers.

## 2. Out-of-scope and prohibited use
Lucid must **not** be used to:
- make a **final** eligibility determination (it says *"you may qualify,"* never *"you qualify"*);
- give **legal or medical** advice;
- auto-apply for benefits or act on a person's behalf;
- certify that a website or person is safe to trust with money or data;
- process **real personal/sensitive data** (it is built and tested on synthetic data only).

## 3. Who we build for — and who we may underserve
**Primary user:** "Rosa" — a renter facing eviction in days, limited English, low digital literacy, no lawyer, scam-targeted. Every design decision is tested against *"does this help Rosa?"*

**Honest equity statement (measured, not claimed):** Lucid is **most reliable for English-language US-federal programs.** Our evaluation shows it is **weakest at understanding the most underserved users** (extraction accuracy ~50% for veteran/domestic-violence cases vs ~89% for English) and at catching **subtle, keyword-free scams** (75% recall). We **surface these gaps to the user and route those cases to a human**, rather than hiding them. (See §6.)

## 4. Design rationale — honesty by architecture
The central choice: **an LLM reads the story, but a separate deterministic rules engine — not the LLM — decides eligibility.** This makes the system *structurally incapable of fabricating eligibility*. The LLM is used only where it's genuinely better than rules (parsing messy, multilingual human language) and never where it's dangerous (deciding who qualifies). Every visible claim is grounded in, and links to, an official source.

## 5. Risk register — and which mitigations are *measured*
| # | Risk | Mitigation in code | Measured? |
|---|---|---|---|
| 1 | Hallucinated eligibility | Determination by deterministic rules engine, never the LLM | ✅ 100% rules-engine accuracy |
| 2 | Misinformation about rules | RAG grounding + faithfulness guard + cited sources | ✅ guard caught a live drift → 0 reached the user |
| 3 | Over-reliance / false confidence | "May qualify" framing + derived confidence + escalation | ✅ low confidence → escalates 100% |
| 4 | Bias / exclusion | Multilingual + bias check + equity audit + abstention | ✅ per-persona equity reported |
| 5 | Privacy harm | No login, no PII collected, nothing stored | ✅ by design |
| 6 | Scams / fraud against the user | Guardian scam detection on pasted content | ✅ 75% recall (honest limit) |
| 7 | Prompt-injection / manipulation | Whole user input treated as untrusted; determination is deterministic | ✅ 67% recall; *and* can't change eligibility even if missed |

## 6. Measured limitations & failure modes (from `eval/EVAL_RESULTS.md`)
- **Income extraction (~91%)** is the intake bottleneck; income-band errors are the main way the answer can go wrong.
- **Scam recall 75%** — subtle, keyword-free social-engineering can slip past the deterministic detector.
- **Injection recall 67%** — novel phrasings can evade detection (but cannot change eligibility — the determination is deterministic).
- **Reading level 8.7** (target ~6th grade) — official program names ("Housing Choice Voucher Program") set a floor we can't lower.
- **Underserved-persona extraction ~50%** — the honest equity gap; these cases are escalated to a human.

## 7. Data & provenance
- **Knowledge base:** 9 real US-federal programs, each curated from its **official public source** (HUD, CFPB, Benefits.gov, United Way 211, ACF/HHS LIHEAP, LSC/LawHelp) with a real `source_url`, web-verified June 2026.
- **No real user data.** All test/demo scenarios are **synthetic and self-authored** (23 evaluation cases + demo personas).

## 8. Human oversight (human-in-the-loop)
Lucid keeps a person in control at three points: it **confirms the extracted facts with the user before deciding**; it **abstains and routes to a caseworker** when confidence is low or it may underserve the user; and it **never makes the final determination**. The decision it explicitly does *not* make is the official eligibility ruling.

## 9. Privacy
No account, no login, no personal data collected, nothing stored. The system requires no SSN, bank details, or account numbers — and warns users that *real assistance never asks for a fee or those details.*

## 10. Social impact — the gap we're closing
- **$140B/year** in US benefits goes unclaimed — largely due to confusion, not ineligibility ([source](https://link-health.org/2025/04/22/bridging-the-140-billion-gap-how-we-can-close-the-unclaimed-benefits-crisis/)).
- **7.6M renters** face eviction yearly, **~2.9M of them children** ([source](https://nlihc.org/resource/new-research-finds-27-million-households-receive-eviction-filings-annually)).
- **~$65M** lost to rental scams since 2020 ([FTC](https://www.ftc.gov/news-events/data-visualizations/data-spotlight/2025/12/rental-scams-hit-home-65-million-reported-losses)).

**Inclusion is the product, not an afterthought:** multilingual (7 languages), answers read aloud, ~plain-language output, low-bandwidth text UI, no login, works on a cheap phone. *We designed for the people these systems fail most, because that is where the failure is greatest.*
