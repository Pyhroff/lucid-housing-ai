"""
app.py — Lucid Streamlit UI (human-centered, navigation-themed).

All wording lives in core/ui_copy.py (one editable file); the situational lines there ADAPT to
the user's need + urgency. This file is layout + styling + flow only. Logic is UNCHANGED — it
just renders run_intake()/run_pipeline().
"""
from __future__ import annotations

import os
try:
    import streamlit as _st
    for _k in ("GROQ_API_KEY", "GEMINI_API_KEY", "LLM_PROVIDER", "GROQ_MODEL"):
        if _k in _st.secrets and not os.environ.get(_k):
            os.environ[_k] = _st.secrets[_k]
except Exception:
    pass

import html
import json

import streamlit as st
import streamlit.components.v1 as components

from agents.guardian import LIMITATIONS, detect_harmful, detect_injection, detect_scam
from agents.intake import run_intake
from core import ui_copy as C
from core.config import confidence_band
from core.counterfactual import unlock_hints
from core.retrieval import select_candidates
from core.rules_engine import determine
from core.schemas import IntakeFacts
from pipeline import run_pipeline


def listen_button(text: str, lang: str) -> None:
    """Read the answer aloud, client-side (browser SpeechSynthesis) — free, offline, any language."""
    payload, lng = json.dumps(text or ""), json.dumps(lang or "en")
    components.html(
        "<button onclick=\"(function(){var u=new SpeechSynthesisUtterance(" + payload + ");"
        "u.lang=" + lng + ";window.speechSynthesis.cancel();window.speechSynthesis.speak(u);})()\" "
        "style=\"font:600 13.5px system-ui;background:#0f6b5f;color:#fff;border:0;border-radius:10px;"
        "padding:8px 15px;cursor:pointer;box-shadow:0 2px 6px rgba(15,107,95,.25)\">🔊 Listen to this</button>",
        height=48,
    )

st.set_page_config(page_title=C.PAGE_TITLE, page_icon="🧭", layout="centered")

# ---------------------------------------------------------------- theme
st.markdown(
    """
    <style>
      :root{
        --ink:#2c2722; --muted:#7a7166; --line:#e7ddd0;
        --clay:#c2613f; --clay-d:#a84f30; --teal:#0f6b5f;
        --good:#2e7d56; --amber:#b07a18; --bad:#c0392b;
      }
      .block-container{max-width:760px;}
      .hero h1{margin:0;font-family:Georgia,'Iowan Old Style','Times New Roman',serif;
        font-size:2.7rem;font-weight:700;letter-spacing:-.5px;color:var(--ink);}
      .hero .tag{color:var(--muted);margin-top:7px;font-size:1.08rem;line-height:1.55;max-width:48ch;}
      .pills{display:flex;flex-wrap:wrap;gap:7px;margin:13px 0 2px;}
      .pill{font-size:.74rem;font-weight:600;color:var(--teal);background:#fff;
        border:1px solid var(--line);padding:4px 12px;border-radius:999px;box-shadow:0 1px 2px rgba(0,0,0,.03);}
      .trust{color:var(--muted);font-size:.82rem;margin:11px 0 2px;}
      .journey{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:20px 0 6px;}
      .jstep{font-size:.8rem;color:var(--muted);background:#fff;
        padding:6px 16px;border-radius:999px;border:1px solid var(--line);transition:all .2s;}
      .jstep.active{color:#fff;border-color:transparent;background:var(--clay);
        box-shadow:0 4px 12px rgba(194,97,63,.32);}
      .jstep.done{color:var(--teal);border-color:#cfe5e0;background:#f0f8f6;}
      .jsep{color:#d8ccba;}
      .step{font-size:.76rem;font-weight:700;letter-spacing:.11em;text-transform:uppercase;
        color:var(--clay);margin:24px 0 3px;}
      .substep{color:var(--muted);font-size:.95rem;margin-bottom:8px;line-height:1.55;}
      .card{background:#fff;border:1px solid var(--line);border-left:4px solid #d8ccba;
        border-radius:14px;padding:14px 18px;margin:11px 0;box-shadow:0 1px 3px rgba(44,39,34,.05);
        transition:transform .15s ease,box-shadow .15s ease;}
      .card:hover{transform:translateY(-2px);box-shadow:0 10px 26px rgba(44,39,34,.10);}
      .card.green{border-left-color:var(--good);} .card.amber{border-left-color:var(--amber);}
      .card.red{border-left-color:var(--bad);}
      .badge{display:inline-block;padding:3px 12px;border-radius:999px;font-size:.72rem;font-weight:700;}
      .badge.green{background:#e6f4ec;color:#256b48;} .badge.amber{background:#f7eccf;color:#8a6100;}
      .badge.red{background:#f9e3df;color:#9b2c1c;} .badge.grey{background:#f0ebe2;color:#7a7166;}
      .pname{font-weight:700;font-size:1.05rem;color:var(--ink);}
      .muted{color:var(--muted);font-size:.87rem;}
      .conf-track{height:14px;background:#efe7da;border-radius:8px;overflow:hidden;margin:4px 0 4px;}
      .conf-fill{height:100%;border-radius:8px;}
      .cf{background:#fff7f0;border:1px solid #f0d9c6;border-radius:13px;padding:11px 16px;margin:9px 0;}
      a.src{font-size:.82rem;text-decoration:none;color:var(--clay-d);font-weight:600;}
    </style>
    """,
    unsafe_allow_html=True,
)

BAND_COLOR = {"high": "#2e7d56", "moderate": "#b07a18", "low": "#c0392b"}
STATUS_CLASS = {"may_qualify": "green", "need_more_info": "amber", "likely_not": "red"}


def esc(s: str) -> str:
    return html.escape(str(s))


# ---------------------------------------------------------------- state
for k, v in {"facts": None, "mode": None, "story_input": "", "pasted_input": "", "result": None}.items():
    st.session_state.setdefault(k, v)


def _load_example(story: str, pasted: str) -> None:
    st.session_state["story_input"] = story
    st.session_state["pasted_input"] = pasted
    st.session_state["facts"] = None
    st.session_state["result"] = None


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(f"### {C.BRAND}")
    st.caption(C.SIDEBAR_BLURB)
    st.markdown(f"**{C.SIDEBAR_EXAMPLES_HEADER}**")
    for label, (s, p) in C.EXAMPLES.items():
        st.button(label, use_container_width=True, on_click=_load_example, args=(s, p))
    st.divider()
    with st.expander(C.LIMITATIONS_TITLE):
        st.markdown(LIMITATIONS)
    if st.session_state.mode:
        engine = "AI + rules" if st.session_state.mode in ("llm", "confirmed") else "offline (keywords + rules)"
        st.caption(f"Running on: {engine}")

# ---------------------------------------------------------------- hero
st.markdown(
    f"<div class='hero'><h1>{C.BRAND}</h1><div class='tag'>{C.TAGLINE}</div></div>",
    unsafe_allow_html=True,
)
st.markdown("<div class='pills'>" + "".join(f"<span class='pill'>{p}</span>" for p in C.PILLS) + "</div>",
            unsafe_allow_html=True)
st.markdown("<div class='trust'>" + " &nbsp;·&nbsp; ".join(C.TRUST) + "</div>", unsafe_allow_html=True)

with st.expander(C.HOW_TITLE):
    st.markdown(C.HOW_BODY)

# "Judge-bait" showcases in TABS (tabs persist across reruns, so the live widgets don't collapse).
_show = st.tabs(["🔬 Eligibility Explorer", C.REDTEAM_TITLE, "💚 Ethics & Impact"])

with _show[0]:
    st.markdown(f"<span class='muted'>{C.EXPLORER_INTRO}</span>", unsafe_allow_html=True)
    _e1, _e2 = st.columns([3, 2])
    with _e1:
        _inc = st.select_slider("Household income", options=C.EXPLORER_BANDS, value="moderate",
                                format_func=lambda b: C.EXPLORER_BAND_LABEL[b], key="ex_income")
        _need = st.selectbox("What you need", C.EXPLORER_NEEDS, key="ex_need")
    with _e2:
        _hh = st.slider("Household size", 1, 8, 3, key="ex_house")
    _ef = IntakeFacts(language="en", need_type=_need, income_band=_inc, household_size=_hh, location="Anytown")
    _eh = determine(_ef, select_candidates(_ef))
    _nmay = sum(1 for h in _eh if h.status == "may_qualify")
    st.markdown(
        f"<div style='font-size:1.45rem;font-weight:800;color:var(--teal);margin:8px 0 2px'>"
        f"✓ You may qualify for {_nmay} of {len(_eh)} options</div>",
        unsafe_allow_html=True,
    )
    for h in _eh:
        _cls = STATUS_CLASS.get(h.status, "grey")
        st.markdown(
            f"<div class='card {_cls}' style='padding:8px 14px;margin:6px 0'>"
            f"<span class='badge {_cls}'>{esc(C.STATUS_LABEL.get(h.status, h.status))}</span> "
            f"<b>{esc(h.program)}</b></div>",
            unsafe_allow_html=True,
        )
    st.caption(C.EXPLORER_FOOT)

with _show[1]:
    st.markdown(C.REDTEAM_INTRO)
    for _label, _kind, _payload in C.REDTEAM_CASES:
        if _kind == "scam":
            _flags = detect_scam(_payload)
            _ok, _detail = bool(_flags), (", ".join(f.replace("_", " ") for f in _flags) if _flags else "no signals")
        elif _kind == "injection":
            _det, _ = detect_injection(_payload)
            _ok, _detail = _det, ("instruction-override attempt neutralised" if _det else "not detected")
        else:  # benign control: success = NOT flagged
            _flagged = bool(detect_scam(_payload)) or detect_injection(_payload)[0]
            _ok, _detail = (not _flagged), ("correctly left alone (no false alarm)" if not _flagged else "false alarm")
        st.markdown(f"{'✅' if _ok else '❌'} **{_label}** — {_detail}")
    st.caption(C.REDTEAM_FOOT)

with _show[2]:
    st.markdown(f"**{C.IMPACT_TITLE}**")
    for _col, (_num, _desc) in zip(st.columns(len(C.IMPACT_STATS)), C.IMPACT_STATS):
        _col.markdown(
            f"<div style='font-size:1.7rem;font-weight:800;color:var(--clay)'>{_num}</div>"
            f"<div class='muted'>{_desc}</div>",
            unsafe_allow_html=True,
        )
    st.markdown(" ")
    st.markdown(C.WHO_WE_SERVE)
    st.markdown(f"**{C.ETHICS_TITLE}**")
    for _c in C.ETHICS_COMMITMENTS:
        st.markdown(_c)
    st.markdown(f"**{C.HONESTY_TITLE}**")
    st.caption(C.HONESTY_BODY)

# ---------------------------------------------------------------- journey
active = 3 if st.session_state.result is not None else (2 if st.session_state.facts is not None else 1)
st.markdown(
    "<div class='journey'>"
    + "<span class='jsep'>→</span>".join(
        f"<span class='jstep{' active' if int(n) == active else (' done' if int(n) < active else '')}'>"
        f"<b>{n}</b>&nbsp;{label}</span>"
        for n, label in C.JOURNEY
    )
    + "</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- step 1
st.markdown(f"<div class='step'>{C.STEP1_TITLE}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='substep'>{C.STEP1_SUB}</div>", unsafe_allow_html=True)
story = st.text_area("Your situation", key="story_input", height=130,
                     label_visibility="collapsed", placeholder=C.STEP1_PLACEHOLDER)
pasted = st.text_input(C.PASTE_LABEL, key="pasted_input", placeholder=C.PASTE_PLACEHOLDER)
if st.button(C.BTN_UNDERSTAND, type="primary"):
    if story.strip():
        facts, mode = run_intake(story, pasted or None)
        st.session_state.facts = facts
        st.session_state.mode = mode
        st.session_state.result = None
    else:
        st.warning(C.EMPTY_NUDGE)

facts: IntakeFacts | None = st.session_state.facts

# ---------------------------------------------------------------- step 2: confirm (Fix #1)
if facts is not None:
    if st.session_state.mode == "offline-fallback":
        st.info(C.OFFLINE_NOTE)

    st.markdown(f"<div class='step'>{C.STEP2_TITLE}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='substep'>{C.STEP2_SUB}</div>", unsafe_allow_html=True)

    crisis = C.crisis_note(facts.need_type, facts.urgency)
    if crisis:
        st.warning(crisis)

    # Immediate safety feedback at Step 2 (injection / illegal-request in the story itself)
    if detect_injection(st.session_state.story_input)[0] or detect_harmful(st.session_state.story_input):
        st.warning(C.GUARD_NOTICE)

    chips = [f"language: {facts.language}", f"urgency: {facts.urgency}"] + list(facts.situation_flags)
    st.markdown(" ".join(f"<span class='badge grey'>{esc(c)}</span>" for c in chips), unsafe_allow_html=True)
    if facts.assumptions:
        st.caption(C.assumptions_note(facts.assumptions))

    inc_labels = list(C.INCOME_LABELS)
    cur_inc_label = next((k for k, v in C.INCOME_LABELS.items() if v == facts.income_band), "I'm not sure")
    c1, c2 = st.columns(2)
    with c1:
        income = C.INCOME_LABELS[st.selectbox(
            C.INCOME_LABEL, inc_labels, index=inc_labels.index(cur_inc_label), help=C.INCOME_HELP)]
        household = st.number_input(C.HOUSEHOLD_LABEL, min_value=0, value=int(facts.household_size or 0))
    with c2:
        location = st.text_input(C.CITY_LABEL, value=facts.location or "")
        need = st.text_input(C.NEED_LABEL, value=facts.need_type)

    lang_labels = list(C.LANGS)
    default_label = next((k for k, v in C.LANGS.items() if v == facts.language), "English")
    answer_lang = C.LANGS[st.selectbox(
        C.LANG_LABEL, lang_labels, index=lang_labels.index(default_label), help=C.LANG_HELP)]

    if st.button(C.BTN_CONFIRM, type="primary"):
        confirmed = facts.model_copy(update={
            "income_band": income, "household_size": household or None,
            "location": location or None, "need_type": need or facts.need_type,
            "language": answer_lang,
        })
        st.session_state.result, _ = run_pipeline(
            st.session_state.story_input, st.session_state.pasted_input or None, facts_override=confirmed)

# ---------------------------------------------------------------- step 3: results
result = st.session_state.result
if result is not None:
    g, e = result.guardian, result.engine
    st.markdown(f"<div class='step'>{C.STEP3_TITLE}</div>", unsafe_allow_html=True)

    has_opts = any(h.status == "may_qualify" for h in e.rule_hits)
    st.markdown(f"<div class='substep'>{C.step3_intro(has_opts, result.intake.need_type)}</div>",
                unsafe_allow_html=True)
    listen_button(g.final_message, result.intake.language)  # read aloud, in the user's language

    if g.final_message_en:  # answer was translated into the user's language
        st.caption(C.lang_caption(result.intake.language))
        st.success(g.final_message)
        with st.expander(C.ENGLISH_ORIGINAL):
            st.markdown(g.final_message_en)

    # safety first
    if g.scam_flags:
        st.error(C.scam_warning(g.scam_flags))
    if g.injection_detected:
        st.info(C.INJECTION_NOTE)
    if g.harmful_request:
        st.warning(C.HARMFUL_NOTE)
    if g.bias_flag:
        st.info(C.EQUITY_NOTE)
    if g.escalate_to_human:
        st.warning(C.ESCALATE_NOTE)

    # confidence + plain meaning
    band = confidence_band(e.confidence)
    st.markdown(
        f"<div class='muted'>{C.confidence_line(round(e.confidence * 100), band)}</div>"
        f"<div class='conf-track'><div class='conf-fill' "
        f"style='width:{e.confidence * 100:.0f}%;background:{BAND_COLOR[band]}'></div></div>",
        unsafe_allow_html=True,
    )

    hint = C.next_best_step(result.intake.income_band, result.intake.household_size, result.intake.location)
    if hint:
        st.info(hint)

    # option cards
    for h in e.rule_hits:
        cls = STATUS_CLASS.get(h.status, "grey")
        st.markdown(
            f"<div class='card {cls}'><span class='badge {cls}'>{esc(C.STATUS_LABEL.get(h.status, h.status))}</span> "
            f"<span class='pname'>{esc(h.program)}</span><br>"
            f"<span class='muted'>{esc(h.reason)}</span><br>"
            f"<a class='src' href='{esc(h.source_url)}' target='_blank'>{C.SOURCE_LINK}</a></div>",
            unsafe_allow_html=True,
        )

    # counterfactual ("what would change this") — the wow feature, only possible because symbolic
    cf = unlock_hints(result.intake, select_candidates(result.intake))
    if cf:
        rows = "".join(
            f"<div style='margin-top:4px'>• <b>{esc(p)}</b> opens up if your household income is "
            f"<b>{esc(b)}</b> or below.</div>" for p, b in cf[:4]
        )
        st.markdown(
            f"<div class='cf'><b>{C.CF_TITLE}</b><br><span class='muted'>{C.CF_INTRO}</span>{rows}</div>",
            unsafe_allow_html=True,
        )

    with st.expander(C.CONF_WHY_TITLE):
        st.caption(C.CONF_WHY_CAPTION)
        st.json(e.confidence_signals)
        if e.unsupported_claims_removed:
            st.caption(C.FAITHFULNESS_REMOVED)

    with st.expander(C.PROOF_TITLE):
        for h in e.rule_hits:
            st.markdown(
                f"- **{h.program}** → `{h.status}` · _{h.category}_  \n"
                f"  {h.reason}  \n"
                f"  [{h.source_url}]({h.source_url})"
            )

    st.caption(C.FOOTER)
