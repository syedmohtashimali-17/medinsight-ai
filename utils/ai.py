"""STUB (P3 owns the real version). Returns dummy JSON-B."""
from utils.safety import get_status


def explain_report(report: dict, language: str) -> dict:
    out = []
    for t in report.get("tests", []):
        rr = t.get("reference_range") or {}
        out.append({
            "test_name": t["test_name"],
            "status": get_status(t.get("value"), rr.get("low"), rr.get("high")),
            "explanation": "(stub) Explanation placeholder.",
            "safety_note": "A doctor should interpret this result.",
        })
    return {"language": language, "explanations": out}
