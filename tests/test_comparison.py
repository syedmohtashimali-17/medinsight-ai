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
