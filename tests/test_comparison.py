import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from utils.comparison import *

jan, mar = load_sample_report("jan_clear"), load_sample_report("mar_clear")
other, blurry = load_sample_report("other_lab"), load_sample_report("blurry")


def row(c, name):
    return next(r for r in c["changes"] if r["test_name"] == name)


def test_increase():
    c = compare_reports(jan, mar)
    r = row(c, "Hemoglobin")
    assert r["change"] == 1.2 and r["direction"] == "increased" and r["unit"] == "g/dL"

def test_decrease_and_unchanged():
    assert row(compare_reports(jan, mar), "WBC")["direction"] == "decreased"
    assert row(compare_reports(jan, jan), "WBC")["direction"] == "unchanged"

def test_alias_and_only_in():
    c = compare_reports(mar, other)
    assert row(c, "Hb")["change"] == 0.9            # Hemoglobin == Hb
    assert row(c, "Total Leukocyte Count")["previous_value"] == 6.8   # WBC == TLC
    assert c["only_in_current"] == ["PCV"] and c["only_in_previous"] == ["Platelets"]

def test_null_value_and_unit_mismatch():
    import copy
    a = copy.deepcopy(jan); a["tests"][0]["value"] = None
    assert row(compare_reports(a, mar), "Hemoglobin")["direction"] == "cannot_compare"
    b = copy.deepcopy(mar); b["tests"][0]["unit"] = "g/L"
    assert row(compare_reports(jan, b), "Hemoglobin")["change"] is None

def test_unreadable_report_does_not_crash():
    c = compare_reports(jan, blurry)
    assert c["changes"] == [] and len(c["only_in_previous"]) == 3
    assert compare_reports(None, mar)["changes"] == []

def test_trend_sorted_and_band():
    df = build_trend_data([other, mar, jan], "Hemoglobin")
    assert list(df["value"]) == [10.2, 11.4, 12.3]      # sorted by date, alias matched
    assert not range_is_stable(df)                       # other lab uses 13-17
    df2 = build_trend_data([jan, mar], "Hb")
    assert range_is_stable(df2) and len(df2) == 2
    assert len(build_trend_figure(df2, "Hemoglobin").layout.shapes) == 1
    assert len(build_trend_figure(df, "Hemoglobin").layout.shapes) == 0

def test_trend_empty():
    assert build_trend_data([jan], "Ferritin").empty


# ---- 3+ reports (checklist item 16) ----
def test_three_reports_trend_is_sorted_and_complete():
    # passed in scrambled order on purpose: Mar, May (other lab), Jan
    df = build_trend_data([mar, other, jan], "Hemoglobin")
    assert list(df["value"]) == [10.2, 11.4, 12.3]          # Jan, Mar, May
    assert list(df["label"]) == ["15 Jan 2026", "15 Mar 2026", "10 May 2026"]
    assert len(df) == 3

def test_three_reports_different_ranges_hide_band():
    df = build_trend_data([jan, mar, other], "Hemoglobin")  # 12-16, 12-16, 13-17
    assert not range_is_stable(df)
    fig = build_trend_figure(df, "Hemoglobin")
    assert len(fig.layout.shapes) == 0                       # no misleading band
    assert len(fig.data[0].x) == 3                           # but all 3 points plotted

def test_three_reports_same_range_shows_band():
    jan2 = {**jan, "report_date": "2026-02-15"}              # a third report, same lab and range
    df = build_trend_data([jan, jan2, mar], "Hb")
    assert len(df) == 3 and range_is_stable(df)
    assert len(build_trend_figure(df, "Hemoglobin").layout.shapes) == 1

def test_three_reports_compare_uses_last_two():
    # app compares the two most recent uploads: mar -> other lab
    c = compare_reports(mar, other)
    assert row(c, "Hb")["change"] == 0.9 and row(c, "Hb")["direction"] == "increased"
    assert c["only_in_previous"] == ["Platelets"] and c["only_in_current"] == ["PCV"]

def test_three_reports_one_missing_value_is_skipped():
    import copy
    gap = copy.deepcopy(mar)
    gap["tests"][0]["value"] = None                          # Hb unreadable in the middle report
    df = build_trend_data([jan, gap, other], "Hemoglobin")
    assert list(df["value"]) == [10.2, 12.3]                 # skipped, not crashed, not guessed

def test_available_tests_across_three_reports():
    names = available_tests([jan, mar, other])
    assert "Hemoglobin" in names and "PCV" in names          # union across all reports
