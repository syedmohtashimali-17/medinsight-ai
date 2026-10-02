"""Integration skeleton (P4). P1 replaces the UI parts; the wiring below stays.
Run:  streamlit run app.py            (real APIs)
      streamlit run app.py -- --demo-mode   (no API calls, sample JSONs)"""
import streamlit as st

from utils.comparison import (available_tests, build_trend_data, build_trend_figure,
                              compare_reports, is_demo_mode, load_sample_report)
from utils.ocr import extract_report
from utils.ai import explain_report
from utils.safety import filter_explanations

DISCLAIMER = ("This tool helps explain laboratory information and does not replace "
              "professional medical advice or diagnosis.")
DEMO = is_demo_mode()

st.set_page_config(page_title="MedInsight AI", layout="wide")
ss = st.session_state
ss.setdefault("reports", [])
ss.setdefault("explanations", [])


def process(file_bytes, filename, language):
    """Upload -> JSON-A -> JSON-B. Falls back to demo data on API failure."""
    try:
        if DEMO:
            demo_files = ["jan_clear", "mar_clear", "other_lab"]
            report = load_sample_report(demo_files[min(len(ss.reports), 2)])
        else:
            report = extract_report(file_bytes, filename)
        if report.get("quality", {}).get("status") == "unreadable":
            st.error("Report is unclear. Please upload a clearer image or PDF.")
            return
        expl = filter_explanations(explain_report(report, language))
        ss.reports.append(report)
        ss.explanations.append(expl)
    except Exception as e:  # outage / 5xx -> don't kill the demo
        st.error(f"Something went wrong ({e}). Try again or run with --demo-mode.")


st.title("MedInsight AI")
if DEMO:
    st.info("Demo mode: using sample data, no API calls.")
language = st.selectbox("Language", ["English", "Roman Urdu", "Urdu"])
up = st.file_uploader("Upload CBC report (image or PDF)", type=["png", "jpg", "jpeg", "pdf"])
c1, c2 = st.columns(2)
if c1.button("Scan") and (up or DEMO):
    process(up.getvalue() if up else b"", up.name if up else "demo", language)
if c2.button("Reset"):
    ss.reports, ss.explanations = [], []

if ss.reports:
    tab_r, tab_c, tab_t = st.tabs(["Results", "Compare", "Trend"])
    with tab_r:
        st.subheader("Reported laboratory result")
        st.dataframe([{"Test": t["test_name"], "Value": t["value"], "Unit": t["unit"],
                       "Lab range": t["reference_range"]["raw"]} for t in ss.reports[-1]["tests"]])
        st.subheader("AI explanation")
        for e in ss.explanations[-1]["explanations"]:
            st.markdown(f"**{e['test_name']}** - {e['status']}  \n{e['explanation']}  \n_{e['safety_note']}_")
    with tab_c:
        if len(ss.reports) < 2:
            st.info("Upload a second report to compare.")
        else:
            cmp = compare_reports(ss.reports[-2], ss.reports[-1])
            st.dataframe(cmp["changes"])
            if cmp["only_in_previous"] or cmp["only_in_current"]:
                st.caption(f"Only in previous: {cmp['only_in_previous']} | Only in current: {cmp['only_in_current']}")
    with tab_t:
        tests = available_tests(ss.reports)
        if len(ss.reports) < 2 or not tests:
            st.info("Upload at least two reports to see a trend.")
        else:
            pick = st.selectbox("Test", tests)
            df = build_trend_data(ss.reports, pick)
            st.plotly_chart(build_trend_figure(df, pick), use_container_width=True)
            if not df.empty and df["low"].notna().all() and df["low"].nunique() > 1:
                st.caption("Lab ranges differ between reports, so no range band is shown.")
    st.caption(DISCLAIMER)
