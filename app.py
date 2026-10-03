"""MedInsight AI - Streamlit UI (P1). Follows Execution Plan v2.0, Sec. 9, 11, 12."""
import html

import pandas as pd
import plotly.graph_objects as pgo
import streamlit as st

from utils.ocr import extract_report
from utils.ai import explain_report
from utils.comparison import (compare_reports, build_trend_data,
                              is_demo_mode, load_sample_report)
from utils.auth import require_login, logout_button

DISCLAIMER = ("This tool helps explain laboratory information and does not replace "
              "professional medical advice or diagnosis.")
LANGUAGES = ["English", "Roman Urdu", "Urdu"]
DEMO = is_demo_mode()  # streamlit run app.py -- --demo-mode  (no API calls)
DEMO_FILES = ["jan_clear", "mar_clear", "other_lab"]
STATUS_COLORS = {
    "Within Range": ("#d4edda", "#155724"),
    "Below Range": ("#fff3cd", "#856404"),
    "Above Range": ("#f8d7da", "#721c24"),
    "Cannot Determine": ("#e2e3e5", "#383d41"),
}

CSS = """
<style>
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1150px; }
h1, h2, h3 { color: #0F3D4A; letter-spacing: -0.01em; }
[data-testid="stSidebar"] { background: #EAF3F3; border-right: 1px solid #CFE0E0; }
[data-testid="stSidebar"] h1 { font-size: 1.4rem; color: #0F3D4A; }
.stButton > button { border-radius: 8px; font-weight: 600; }
.hero { background: linear-gradient(135deg, #0F3D4A 0%, #1B6B73 100%); color: #fff;
        padding: 2.4rem 2.2rem; border-radius: 14px; margin-bottom: 1.4rem; }
.hero h1 { color: #fff; margin: 0 0 .4rem 0; font-size: 2.3rem; }
.hero p { color: #D8ECEC; font-size: 1.05rem; max-width: 46rem; margin: 0; }
.feat { border: 1px solid #D5E3E3; border-radius: 12px; padding: 1.1rem 1.2rem;
        background: #fff; height: 100%; }
.feat b { color: #0F3D4A; font-size: 1.02rem; }
.feat span { color: #5A6B71; font-size: .93rem; }
.sumbox { border-radius: 12px; padding: .9rem 1rem; text-align: center; }
.sumbox .n { font-size: 1.9rem; font-weight: 700; line-height: 1.1; }
.sumbox .l { font-size: .85rem; }
.pill { display: inline-block; padding: 2px 12px; border-radius: 999px;
        font-size: .82rem; font-weight: 700; }
.excard { border: 1px solid #D5E3E3; border-left-width: 6px; border-radius: 10px;
          padding: .9rem 1.1rem; margin-bottom: .8rem; background: #fff; }
.excard .top { display: flex; justify-content: space-between; align-items: center; margin-bottom: .35rem; }
.excard .name { font-weight: 700; color: #0F3D4A; font-size: 1.02rem; }
.excard .note { color: #5A6B71; font-size: .86rem; margin-top: .45rem; }
.tag { display: inline-block; font-size: .8rem; font-weight: 600; color: #1B6B73;
       background: #E3F1F1; border-radius: 6px; padding: 2px 10px; margin-bottom: .5rem; }
.disc { margin-top: 2rem; padding: .8rem 1rem; border-radius: 10px; background: #F1F5F6;
        color: #4A5A60; font-size: .85rem; border: 1px solid #DCE5E7; }
</style>
"""


def pill(status):
    bg, fg = STATUS_COLORS.get(status, STATUS_COLORS["Cannot Determine"])
    return f"<span class='pill' style='background:{bg};color:{fg}'>{html.escape(status)}</span>"


# ---------------------------------------------------------------- state (Sec. 9)
def init_state():
    st.session_state.setdefault("reports", [])       # list of JSON-A
    st.session_state.setdefault("explanations", [])  # list of JSON-B
    st.session_state.setdefault("current_page", "welcome")
    st.session_state.setdefault("quality_error", None)


def go(page):
    st.session_state.current_page = page


def reset():
    st.session_state.reports = []
    st.session_state.explanations = []
    st.session_state.quality_error = None
    go("upload")


def scan(uploaded, language):
    """extract_report -> quality check -> explain_report. True on success."""
    with st.spinner("Scanning report..."):
        if DEMO:  # sample JSONs, one per scan, no API call
            n = min(len(st.session_state.reports), len(DEMO_FILES) - 1)
            report = load_sample_report(DEMO_FILES[n])
        else:
            report = extract_report(uploaded.getvalue(), uploaded.name)
    status = report.get("quality", {}).get("status", "unreadable")
    if status in ("low", "unreadable"):
        st.session_state.quality_error = status
        return False
    with st.spinner("Preparing explanations..."):
        expl = explain_report(report, language)
    st.session_state.quality_error = None
    st.session_state.reports.append(report)
    st.session_state.explanations.append(expl)
    return True


# ---------------------------------------------------------------- shared pieces
def disclaimer():
    st.markdown(f"<div class='disc'><b>Disclaimer:</b> {DISCLAIMER}</div>", unsafe_allow_html=True)


def quality_error_box():
    if st.session_state.quality_error:
        st.error("This report could not be read clearly enough, so no values were guessed. "
                 "Please upload a clearer image or PDF.")


def color_status(val):
    bg, fg = STATUS_COLORS.get(val, STATUS_COLORS["Cannot Determine"])
    return f"background-color: {bg}; color: {fg}; font-weight: 600"


def nav():
    with st.sidebar:
        st.title("MedInsight AI")
        for key, label in [("welcome", "Welcome"), ("upload", "Upload"), ("results", "Results"),
                           ("compare", "Compare"), ("trend", "Trend")]:
            st.button(label, key=f"nav_{key}", on_click=go, args=(key,), use_container_width=True)


# ---------------------------------------------------------------- screens
def welcome():
    st.markdown(
        "<div class='hero'><h1>MedInsight AI</h1>"
        "<p>Understand and track your CBC lab reports. Upload a report, see each value "
        "against your lab's own reference range, and read a simple explanation in English "
        "or Roman Urdu.</p></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown("<div class='feat'><b>Reads your report</b><br><span>Image or PDF. Values, units "
                "and the lab's printed range are extracted.</span></div>", unsafe_allow_html=True)
    c2.markdown("<div class='feat'><b>Explains it simply</b><br><span>Plain English or Roman Urdu. "
                "No diagnosis, no medicine advice.</span></div>", unsafe_allow_html=True)
    c3.markdown("<div class='feat'><b>Tracks changes</b><br><span>Compare two reports and see a "
                "trend chart for each test.</span></div>", unsafe_allow_html=True)
    st.write("")
    st.button("Get started", type="primary", on_click=go, args=("upload",))
    disclaimer()


def upload():
    st.title("Upload report")
    file = st.file_uploader("CBC report (PNG, JPG or PDF)", type=["png", "jpg", "jpeg", "pdf"])
    language = st.selectbox("Language", LANGUAGES, key="language")
    if language == "Urdu":
        st.caption("Urdu is best-effort. Roman Urdu is recommended.")
    c1, c2 = st.columns(2)
    if c1.button("Scan", type="primary", disabled=file is None and not DEMO):
        if scan(file, language):
            go("results")
            st.rerun()
    c2.button("Reset", on_click=reset)
    quality_error_box()
    disclaimer()


def results():
    st.title("Results")
    if not st.session_state.reports:
        st.info("No report yet. Please upload one first.")
        st.button("Go to Upload", on_click=go, args=("upload",))
        disclaimer()
        return
    idx = len(st.session_state.reports) - 1
    report = st.session_state.reports[idx]
    expl = st.session_state.explanations[idx]

    # language switch re-runs explain_report for this report
    current = expl.get("language", "English")
    lang = st.selectbox("Explanation language", LANGUAGES, index=LANGUAGES.index(current))
    if lang != current:
        with st.spinner("Preparing explanations..."):
            st.session_state.explanations[idx] = explain_report(report, lang)
        st.rerun()

    st.caption(f"Lab: {report.get('lab_name') or 'Unknown'}  |  "
               f"Date: {report.get('report_date') or 'Unknown'}  |  "
               f"Type: {report.get('report_type') or 'CBC'}")

    st.subheader("Reported laboratory result")
    status_by_test = {e["test_name"]: e["status"] for e in expl["explanations"]}
    rows = []
    for t in report["tests"]:
        rr = t.get("reference_range") or {}
        rows.append({
            "Test": t["test_name"],
            "Value": t["value"] if t["value"] is not None else "Not found",
            "Unit": t.get("unit") or "",
            "Lab reference range": rr.get("raw") or "Not printed",
            "Status": status_by_test.get(t["test_name"], "Cannot Determine"),
        })
    df = pd.DataFrame(rows)
    counts = df["Status"].value_counts()
    cols = st.columns(4)
    for col, name in zip(cols, STATUS_COLORS):
        bg, fg = STATUS_COLORS[name]
        col.markdown(f"<div class='sumbox' style='background:{bg};color:{fg}'>"
                     f"<div class='n'>{int(counts.get(name, 0))}</div><div class='l'>{name}</div></div>",
                     unsafe_allow_html=True)
    st.write("")
    st.dataframe(df.style.map(color_status, subset=["Status"]),
                 use_container_width=True, hide_index=True)

    st.subheader("AI explanation")
    st.markdown("<span class='tag'>AI-generated. Not a diagnosis.</span>", unsafe_allow_html=True)
    for e in expl["explanations"]:
        fg = STATUS_COLORS.get(e["status"], STATUS_COLORS["Cannot Determine"])[1]
        st.markdown(
            f"<div class='excard' style='border-left-color:{fg}'>"
            f"<div class='top'><span class='name'>{html.escape(e['test_name'])}</span>{pill(e['status'])}</div>"
            f"<div>{html.escape(e['explanation'])}</div>"
            f"<div class='note'>{html.escape(e['safety_note'])}</div></div>",
            unsafe_allow_html=True)
    disclaimer()


def compare():
    st.title("Compare reports")
    if not st.session_state.reports:
        st.info("Upload your first report before comparing.")
        st.button("Go to Upload", on_click=go, args=("upload",))
        disclaimer()
        return
    file = st.file_uploader("Second report (PNG, JPG or PDF)", type=["png", "jpg", "jpeg", "pdf"],
                            key="second_uploader")
    language = st.session_state.explanations[-1].get("language", "English")
    if st.button("Scan", type="primary", disabled=file is None and not DEMO, key="scan_second"):
        if scan(file, language):
            st.rerun()
    quality_error_box()

    if len(st.session_state.reports) >= 2:
        result = compare_reports(st.session_state.reports[-2], st.session_state.reports[-1])
        st.subheader(f"{result['previous_date']}  vs  {result['current_date']}")
        st.dataframe(pd.DataFrame(result["changes"]).rename(columns={
            "test_name": "Test", "previous_value": "Previous", "current_value": "Current",
            "change": "Change", "direction": "Direction", "unit": "Unit"}),
            use_container_width=True, hide_index=True)
        if result["only_in_previous"]:
            st.write("Only in previous report: " + ", ".join(result["only_in_previous"]))
        if result["only_in_current"]:
            st.write("Only in current report: " + ", ".join(result["only_in_current"]))
    disclaimer()


def trend():
    st.title("Trend")
    reports = st.session_state.reports
    if len(reports) < 2:
        st.info("Upload at least two reports to see a trend.")
        disclaimer()
        return
    names = sorted({t["test_name"] for r in reports for t in r["tests"]})
    test = st.selectbox("Test", names)
    df = build_trend_data(reports, test)
    if df.empty:
        st.warning("No data for this test.")
        disclaimer()
        return
    fig = pgo.Figure()
    # lab-range band only when the range is the same in every report
    ranges = df[["low", "high"]].drop_duplicates()
    if len(ranges) == 1 and ranges.notna().all(axis=None):
        fig.add_hrect(y0=ranges.iloc[0]["low"], y1=ranges.iloc[0]["high"],
                      fillcolor="green", opacity=0.12, line_width=0, annotation_text="Lab range")
    fig.add_trace(pgo.Scatter(x=df["date"], y=df["value"], mode="lines+markers", name=test))
    fig.update_layout(xaxis_title="Report date", yaxis_title=test, height=420)
    st.plotly_chart(fig, use_container_width=True)
    disclaimer()


# ---------------------------------------------------------------- main
st.set_page_config(page_title="MedInsight AI", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
require_login()   # login gate: nothing below runs until the user is logged in
init_state()
nav()
logout_button()
if DEMO:
    st.sidebar.caption("Demo mode: sample data, no API calls")
{"welcome": welcome, "upload": upload, "results": results,
 "compare": compare, "trend": trend}[st.session_state.current_page]()
