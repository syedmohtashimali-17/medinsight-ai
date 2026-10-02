"""P4 module: report comparison, trend data, trend chart, demo-mode loader.
Pure Python + pandas + plotly. No LLM calls, fully deterministic."""
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

# ---------- name normalisation ----------
_ALIASES = {
    "hemoglobin": ["hemoglobin", "haemoglobin", "hb", "hgb"],
    "rbc": ["rbc", "rbc count", "red blood cells", "red blood cell count", "total rbc count", "erythrocytes"],
    "wbc": ["wbc", "wbc count", "white blood cells", "white blood cell count", "tlc",
            "total leukocyte count", "total leucocyte count", "total wbc count", "leukocytes"],
    "platelets": ["platelets", "platelet count", "plt", "thrombocytes"],
    "hematocrit": ["hematocrit", "haematocrit", "hct", "pcv", "packed cell volume"],
    "mcv": ["mcv", "mean corpuscular volume"],
    "mch": ["mch", "mean corpuscular hemoglobin", "mean corpuscular haemoglobin"],
    "mchc": ["mchc", "mean corpuscular hemoglobin concentration"],
    "rdw": ["rdw", "rdw cv", "rdw-cv", "red cell distribution width"],
    "neutrophils": ["neutrophils", "neutrophil", "neutrophils %", "neut"],
    "lymphocytes": ["lymphocytes", "lymphocyte", "lymphocytes %", "lymph"],
    "monocytes": ["monocytes", "monocyte", "monocytes %", "mono"],
    "eosinophils": ["eosinophils", "eosinophil", "eosinophils %", "eos"],
    "basophils": ["basophils", "basophil", "basophils %", "baso"],
}
_LOOKUP = {}
for _canon, _names in _ALIASES.items():
    for _n in _names:
        _LOOKUP[re.sub(r"[^a-z0-9%]+", " ", _n.lower()).strip()] = _canon


def normalize_name(name):
    """'Hb' / 'Haemoglobin ' / 'HEMOGLOBIN' -> 'hemoglobin'. Unknown names -> cleaned lowercase."""
    cleaned = re.sub(r"[^a-z0-9%]+", " ", str(name or "").lower()).strip()
    return _LOOKUP.get(cleaned, cleaned)


def _usable(report):
    return isinstance(report, dict) and isinstance(report.get("tests"), list)


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _index_tests(report):
    """canonical name -> test dict (first occurrence wins)."""
    out = {}
    if not _usable(report):
        return out
    for t in report["tests"]:
        key = normalize_name(t.get("test_name"))
        if key and key not in out:
            out[key] = t
    return out


def _unit_key(u):
    return re.sub(r"\s+", "", str(u or "")).lower()


# ---------- Contract C ----------
def compare_reports(previous: dict, current: dict) -> dict:
    prev, curr = _index_tests(previous), _index_tests(current)
    result = {
        "previous_date": (previous or {}).get("report_date"),
        "current_date": (current or {}).get("report_date"),
        "changes": [],
        "only_in_previous": [],
        "only_in_current": [],
    }
    for key, c in curr.items():
        if key not in prev:
            result["only_in_current"].append(c.get("test_name"))
            continue
        p = prev[key]
        pv, cv = _num(p.get("value")), _num(c.get("value"))
        unit = c.get("unit") or p.get("unit")
        row = {
            "test_name": c.get("test_name"),
            "previous_value": pv,
            "current_value": cv,
            "change": None,
            "direction": "cannot_compare",  # extra value beyond the contract; P1 must handle it
            "unit": unit,
        }
        same_unit = _unit_key(p.get("unit")) == _unit_key(c.get("unit")) or not (p.get("unit") and c.get("unit"))
        if pv is not None and cv is not None and same_unit:
            diff = round(cv - pv, 2)
            row["change"] = diff
            row["direction"] = "increased" if diff > 0 else "decreased" if diff < 0 else "unchanged"
        result["changes"].append(row)
    for key, p in prev.items():
        if key not in curr:
            result["only_in_previous"].append(p.get("test_name"))
    return result


# ---------- Trend ----------
def _sort_key(item):
    idx, rep = item
    d = pd.to_datetime(rep.get("report_date"), errors="coerce")
    return (pd.isna(d), d if not pd.isna(d) else pd.Timestamp.max, idx)


def build_trend_data(reports: list, test_name: str) -> pd.DataFrame:
    """One row per report that has a numeric value for test_name, sorted by date."""
    cols = ["date", "label", "value", "unit", "low", "high", "lab_name"]
    key = normalize_name(test_name)
    rows = []
    for idx, rep in sorted(enumerate(reports or []), key=_sort_key):
        t = _index_tests(rep).get(key)
        if not t:
            continue
        v = _num(t.get("value"))
        if v is None:
            continue
        rr = t.get("reference_range") or {}
        d = pd.to_datetime(rep.get("report_date"), errors="coerce")
        rows.append({
            "date": d,
            "label": d.strftime("%d %b %Y") if not pd.isna(d) else f"Report {idx + 1}",
            "value": v,
            "unit": t.get("unit"),
            "low": _num(rr.get("low")),
            "high": _num(rr.get("high")),
            "lab_name": rep.get("lab_name"),
        })
    return pd.DataFrame(rows, columns=cols)


def available_tests(reports: list) -> list:
    """Test names (display form) with a numeric value in at least one report."""
    seen = {}
    for rep in reports or []:
        for key, t in _index_tests(rep).items():
            if _num(t.get("value")) is not None and key not in seen:
                seen[key] = t.get("test_name")
    return list(seen.values())


def range_is_stable(df: pd.DataFrame) -> bool:
    if df.empty or df["low"].isna().any() or df["high"].isna().any():
        return False
    return df["low"].nunique() == 1 and df["high"].nunique() == 1


def build_trend_figure(df: pd.DataFrame, test_name: str):
    """Plotly line chart with markers; lab-range band shaded ONLY if range is identical across reports."""
    import plotly.graph_objects as go

    fig = go.Figure()
    unit = df["unit"].dropna().iloc[0] if not df.empty and df["unit"].notna().any() else ""
    if not df.empty and range_is_stable(df):
        lo, hi = float(df["low"].iloc[0]), float(df["high"].iloc[0])
        fig.add_hrect(y0=lo, y1=hi, fillcolor="green", opacity=0.12, line_width=0,
                      annotation_text=f"Lab range {lo:g}-{hi:g}", annotation_position="top left")
    fig.add_trace(go.Scatter(x=df["label"], y=df["value"], mode="lines+markers",
                             name=test_name, line=dict(width=3), marker=dict(size=10)))
    fig.update_layout(title=f"{test_name} trend", xaxis_title="Report date",
                      yaxis_title=f"Value ({unit})" if unit else "Value", template="plotly_white")
    return fig


# ---------- Demo mode ----------
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_reports"


def is_demo_mode() -> bool:
    """True if run as `streamlit run app.py -- --demo-mode` or DEMO_MODE=1."""
    return "--demo-mode" in sys.argv or os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")


def load_sample_report(name: str) -> dict:
    with open(SAMPLE_DIR / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)
