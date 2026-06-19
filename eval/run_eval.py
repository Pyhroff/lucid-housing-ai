"""
eval/run_eval.py — Lucid's evaluation harness.

Two layers, deliberately separated:

  * REGRESSION (deterministic, free): runs the symbolic engine over each scenario's labelled
    ground-truth facts (`expected_extraction`). It tests that our rule ENCODING matches the
    official program rules, plus the scam / injection / abstention behaviour. ~100% determination
    here is the GOAL — it's a regression guard, not a brag.

  * LIVE (real LLM, --live): runs real intake on the raw story, so the metrics can actually FAIL —
    extraction accuracy, end-to-end determination, faithfulness, reading level. THIS is the honest
    "we measured it" table, sliced per persona (the equity audit). The gap between the live
    end-to-end number and the perfect-facts regression number is the insight: the symbolic engine
    is exact; intake is the bottleneck — and here's where.

Run:  python eval/run_eval.py            # regression only (deterministic, free)
      python eval/run_eval.py --live     # + live LLM metrics (needs a key in .env)
      python eval/run_eval.py --live --sleep 1   # space calls out to dodge free-tier rate limits
Writes eval/results.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env up front so the --live key check sees the key (before any project import).
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

SCENARIOS = json.loads((ROOT / "data" / "eval_scenarios.json").read_text(encoding="utf-8"))["scenarios"]


def _rate(num: int, den: int) -> float:
    return (100.0 * num / den) if den else 0.0


# ---------------------------------------------------------------- regression (deterministic, no LLM)
def run_regression() -> list[dict]:
    from agents.guardian import run_guardian
    from core.confidence import derive_confidence
    from core.retrieval import select_candidates
    from core.rules_engine import determine
    from core.schemas import EngineResult, IntakeFacts

    rows = []
    for sc in SCENARIOS:
        f = IntakeFacts(**sc["expected_extraction"])
        hits = determine(f, select_candidates(f))
        conf, _ = derive_confidence(f, hits)
        engine = EngineResult(rule_hits=hits, confidence=conf)
        g = run_guardian(f, engine, raw_text=sc["input_text"], pasted_item=sc["pasted_item"] or None)
        hit = next((h for h in hits if h.program == sc["expected_program"]), None)
        rows.append({
            "id": sc["id"],
            "det_ok": bool(hit) and hit.status == sc["expected_status"],
            "det_got": hit.status if hit else "MISSING",
            "det_exp": sc["expected_status"],
            "scam_pred": bool(g.scam_flags), "is_scam": sc["is_scam"],
            "inj_pred": g.injection_detected, "is_injection": sc["is_injection"],
            "esc_ok": g.escalate_to_human == sc["should_escalate"],
            "conf": conf, "escalate": g.escalate_to_human,
            "cited": len(hits) > 0 and all(h.source_url.startswith("http") for h in hits),
        })
    return rows


# ---------------------------------------------------------------- live (real LLM)
def run_live(sleep: float = 0.0) -> list[dict]:
    from agents.intake import run_intake
    from pipeline import run_pipeline
    try:
        import textstat
    except ImportError:
        textstat = None

    rows = []
    for sc in SCENARIOS:
        exp = sc["expected_extraction"]
        facts, mode = run_intake(sc["input_text"], sc["pasted_item"] or None)
        res, _ = run_pipeline(sc["input_text"], sc["pasted_item"] or None, facts_override=facts)
        hit = next((h for h in res.engine.rule_hits if h.program == sc["expected_program"]), None)
        text = res.guardian.final_message_en or res.guardian.final_message
        rows.append({
            "id": sc["id"], "mode": mode, "tags": sc["persona_tags"],
            "lang_ok": facts.language == exp["language"],
            "need_ok": facts.need_type == exp["need_type"],
            "inc_ok": facts.income_band == exp.get("income_band", "unknown"),
            "extract_ok": (facts.language == exp["language"] and facts.need_type == exp["need_type"]
                           and facts.income_band == exp.get("income_band", "unknown")),
            "e2e_ok": bool(hit) and hit.status == sc["expected_status"],
            "removed": res.engine.unsupported_claims_removed,
            "fk": round(textstat.flesch_kincaid_grade(text), 1) if textstat else None,
        })
        if sleep:
            time.sleep(sleep)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run live LLM metrics (needs a key)")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between live cases (rate limits)")
    args = ap.parse_args()

    results: dict = {"n": len(SCENARIOS)}
    print(f"\nLUCID — EVALUATION  ({len(SCENARIOS)} scenarios)")
    print("=" * 56)

    reg = run_regression()
    det = _rate(sum(r["det_ok"] for r in reg), len(reg))
    esc = _rate(sum(r["esc_ok"] for r in reg), len(reg))
    cit = _rate(sum(r["cited"] for r in reg), len(reg))
    s_pos = [r for r in reg if r["is_scam"]]
    s_neg = [r for r in reg if not r["is_scam"]]
    i_pos = [r for r in reg if r["is_injection"]]
    i_neg = [r for r in reg if not r["is_injection"]]
    s_rec = _rate(sum(r["scam_pred"] for r in s_pos), len(s_pos))
    s_fp = _rate(sum(r["scam_pred"] for r in s_neg), len(s_neg))
    i_rec = _rate(sum(r["inj_pred"] for r in i_pos), len(i_pos))
    i_fp = _rate(sum(r["inj_pred"] for r in i_neg), len(i_neg))

    print("\nRULES-ENGINE REGRESSION  (deterministic - given correct facts - tests encoding)")
    print(f"  Determination accuracy ........ {det:5.0f}%  ({sum(r['det_ok'] for r in reg)}/{len(reg)})")
    print(f"  Abstention vs design intent ... {esc:5.0f}%  ({sum(r['esc_ok'] for r in reg)}/{len(reg)})")
    print(f"  Citation-grounding ............ {cit:5.0f}%  (every claim carries a source)")
    print("\nSECURITY  (deterministic - adversarial inputs incl. HARD cases)")
    print(f"  Scam catch (recall) ........... {s_rec:5.0f}%  ({sum(r['scam_pred'] for r in s_pos)}/{len(s_pos)})")
    print(f"  Scam false-positive rate ...... {s_fp:5.0f}%  ({sum(r['scam_pred'] for r in s_neg)}/{len(s_neg)})")
    print(f"  Injection catch (recall) ...... {i_rec:5.0f}%  ({sum(r['inj_pred'] for r in i_pos)}/{len(i_pos)})")
    print(f"  Injection false-positive ...... {i_fp:5.0f}%  ({sum(r['inj_pred'] for r in i_neg)}/{len(i_neg)})")

    for label, ids in [("determination misses", [r["id"] for r in reg if not r["det_ok"]]),
                       ("escalation mismatches", [r["id"] for r in reg if not r["esc_ok"]]),
                       ("scams missed (hard)", [r["id"] for r in s_pos if not r["scam_pred"]]),
                       ("scam false positives", [r["id"] for r in s_neg if r["scam_pred"]]),
                       ("injections missed (hard)", [r["id"] for r in i_pos if not r["inj_pred"]])]:
        if ids:
            print(f"   · {label}: {', '.join(ids)}")

    # combined adversarial robustness + confidence calibration
    from core.config import confidence_band

    attacks = len(s_pos) + len(i_pos)
    caught = sum(r["scam_pred"] for r in s_pos) + sum(r["inj_pred"] for r in i_pos)
    robust = _rate(caught, attacks)
    print(f"\n  Adversarial robustness ........ {robust:5.0f}%  (caught {caught}/{attacks} planted attacks)")

    print("\nCONFIDENCE CALIBRATION  (does higher confidence mean safer to act without a human?)")
    calib = {}
    for b in ("high", "moderate", "low"):
        grp = [r for r in reg if confidence_band(r["conf"]) == b]
        if grp:
            mean = round(sum(r["conf"] for r in grp) / len(grp), 2)
            esc = _rate(sum(r["escalate"] for r in grp), len(grp))
            calib[b] = {"n": len(grp), "mean_conf": mean, "escalates_pct": esc}
            print(f"  {b:9} n={len(grp):2}  mean conf {mean:.2f}  ->  escalates to a human {esc:3.0f}%")
    print("  (calibrated = low confidence escalates often, high confidence rarely)")

    results["robustness_pct"] = robust
    results["calibration"] = calib
    results["regression"] = {
        "determination_pct": det, "abstention_match_pct": esc, "citation_pct": cit,
        "scam_recall_pct": s_rec, "scam_fp_pct": s_fp,
        "injection_recall_pct": i_rec, "injection_fp_pct": i_fp, "rows": reg,
    }

    if args.live:
        if not (os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")):
            print("\n[!] --live requested but no LLM key in env; skipping live metrics.")
        else:
            print("\nLIVE LLM  (real model - where it can fail) ... calling the API, please wait")
            live = run_live(sleep=args.sleep)
            lang = _rate(sum(r["lang_ok"] for r in live), len(live))
            need = _rate(sum(r["need_ok"] for r in live), len(live))
            inc = _rate(sum(r["inc_ok"] for r in live), len(live))
            allx = _rate(sum(r["extract_ok"] for r in live), len(live))
            e2e = _rate(sum(r["e2e_ok"] for r in live), len(live))
            grounded = _rate(sum(not r["removed"] for r in live), len(live))
            caught = sum(r["removed"] for r in live)
            fks = [r["fk"] for r in live if r["fk"] is not None]
            fk_mean = round(sum(fks) / len(fks), 1) if fks else None
            llm_used = sum(1 for r in live if r["mode"] == "llm")

            print(f"  Intake used the real LLM ...... {llm_used}/{len(live)} scenarios")
            print(f"  Extraction accuracy (all 3) ... {allx:5.0f}%")
            print(f"     - language ................. {lang:5.0f}%")
            print(f"     - need_type ................ {need:5.0f}%")
            print(f"     - income_band .............. {inc:5.0f}%  (the usual bottleneck)")
            print(f"  End-to-end determination ...... {e2e:5.0f}%  (live facts; vs {det:.0f}% with perfect facts)")
            print(f"  Faithfulness: render grounded . {grounded:5.0f}%  ({caught} drift(s) caught + replaced)")
            print(f"  Reading level (FK grade) ...... {fk_mean}")

            tags = sorted({t for r in live for t in r["tags"]})
            persona = {}
            shown = []
            print("\nEQUITY AUDIT  (extraction accuracy by persona - the metric that varies; groups of 2+)")
            for t in tags:
                grp = [r for r in live if t in r["tags"]]
                persona[t] = {"n": len(grp),
                              "extraction_pct": _rate(sum(r["extract_ok"] for r in grp), len(grp)),
                              "e2e_pct": _rate(sum(r["e2e_ok"] for r in grp), len(grp))}
                if len(grp) >= 2:
                    print(f"  {t:24} {persona[t]['extraction_pct']:5.0f}%  (n={len(grp)})")
                    shown.append((t, persona[t]["extraction_pct"]))
            if shown:
                worst = min(shown, key=lambda x: x[1])
                print(f"   -> weakest group: {worst[0]} ({worst[1]:.0f}%) - where to focus next")

            results["live"] = {
                "intake_llm_used": llm_used, "extraction_all_pct": allx,
                "lang_pct": lang, "need_pct": need, "income_pct": inc,
                "e2e_determination_pct": e2e, "render_grounded_pct": grounded,
                "drift_caught": caught, "reading_grade": fk_mean, "by_persona": persona, "rows": live,
            }

    print("\nCAVEAT: synthetic, self-authored scenarios. Determination labels derive from official")
    print("program rules — the regression line tests our ENCODING; the live line is where it fails.")
    out = ROOT / "eval" / "results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
