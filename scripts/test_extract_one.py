"""Run P2 extraction on ONE file with your real Gemini key and check the result.

Usage (from repo root, with GEMINI_API_KEY in .env or the environment):
    python scripts/test_extract_one.py data/sample_reports/cbc_jan_clear.png

Prints the JSON-A, validates it against the contract, and (for the bundled
synthetic samples) compares it to tests/fixtures/sample_ground_truth.json.
Exit code 0 = valid JSON-A (even if "unreadable"); 1 = contract violation.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.ocr import extract_report, validate_json_a  # noqa: E402


def compare_with_truth(result: dict, name: str) -> None:
    truth_file = ROOT / "tests" / "fixtures" / "sample_ground_truth.json"
    if not truth_file.exists():
        return
    entry = next((e for e in json.loads(truth_file.read_text()) if e["file"] == name), None)
    if entry is None:
        return
    print("\n--- comparison with ground truth ---")
    if "expected_quality" in entry:
        print(f"expected: unreadable (or at least not 'good'); got: {result['quality']['status']}")
        return
    problems = []
    for key in ("report_date", "lab_name"):
        if result.get(key) != entry[key]:
            problems.append(f"{key}: expected {entry[key]!r}, got {result.get(key)!r}")
    got = {t["test_name"].strip().lower(): t for t in result["tests"]}
    for exp in entry["tests"]:
        t = got.get(exp["test_name"].lower())
        if t is None:
            problems.append(f"missing test: {exp['test_name']}")
            continue
        if t["value"] != exp["value"]:
            problems.append(f"{exp['test_name']}: value expected {exp['value']}, got {t['value']}")
        if t["reference_range"]["raw"] != exp["raw"]:
            problems.append(f"{exp['test_name']}: range expected {exp['raw']!r}, got {t['reference_range']['raw']!r}")
    print("ground truth match: OK" if not problems else "differences:\n  " + "\n  ".join(problems))


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    result = extract_report(path.read_bytes(), path.name)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    errors = validate_json_a(result)
    print("\n--- JSON-A contract check ---")
    print("VALID" if not errors else "INVALID:\n  " + "\n  ".join(errors))
    q = result["quality"]
    print(f"status={q['status']} confidence={q.get('confidence')} tests={len(result['tests'])}"
          + (f" reason={q['reason']}" if "reason" in q else ""))
    compare_with_truth(result, path.name)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
