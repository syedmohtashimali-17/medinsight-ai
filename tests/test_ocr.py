"""P2 unit tests for utils/ocr.py. Gemini is always mocked: no API key, no network.

Run:  pytest tests/test_ocr.py -v
"""
import json

import fitz
import pytest

from utils import ocr

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image-data"
JPG_BYTES = b"\xff\xd8\xff\xe0" + b"fake-image-data"


# ---------------------------------------------------------------- helpers
def gemini_payload(**overrides) -> dict:
    """A realistic, good Gemini response (as a Python dict)."""
    tests = [
        ("Hemoglobin", 10.2, "g/dL", "12-16"),
        ("WBC", 7.5, "x10^3/uL", "4.0 - 11.0"),
        ("Platelets", 250, "x10^3/uL", "150-450"),
        ("RBC", 4.1, "x10^6/uL", "4.2-5.4"),
        ("CRP", 3.0, "mg/L", "<5.0"),
    ]
    payload = {
        "report_date": "2026-01-15",
        "lab_name": "Example Lab",
        "report_type": "CBC",
        "quality": {"status": "good", "confidence": 0.94},
        "tests": [
            {"test_name": n, "value": v, "unit": u, "reference_range": {"raw": r}}
            for n, v, u, r in tests
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def gemini(monkeypatch):
    """Mock the Gemini layer. Set gemini.reply to a str (or a list of
    str/Exception for successive calls). Inspect gemini.calls / gemini.sleeps."""

    class Mock:
        def __init__(self):
            self.reply = json.dumps(gemini_payload())
            self.calls = []
            self.sleeps = []

        def fake_generate(self, client, model, image_bytes, mime_type):
            self.calls.append({"model": model, "image": image_bytes, "mime": mime_type})
            reply = self.reply
            if isinstance(reply, list):
                reply = reply[min(len(self.calls), len(reply)) - 1]
            if isinstance(reply, Exception):
                raise reply
            return reply

    mock = Mock()
    monkeypatch.setattr(ocr, "_get_api_key", lambda: "fake-key")
    monkeypatch.setattr(ocr, "_get_client", lambda key: object())
    monkeypatch.setattr(ocr, "_generate", mock.fake_generate)
    monkeypatch.setattr(ocr, "_sleep", mock.sleeps.append)
    return mock


class FakeAPIError(Exception):
    """Stands in for google.genai.errors.APIError (has a .code)."""

    def __init__(self, code, message="error"):
        super().__init__(f"{code} {message}")
        self.code = code


def assert_unreadable(result, reason=None):
    assert ocr.validate_json_a(result) == []
    assert result["quality"]["status"] == "unreadable"
    assert result["tests"] == []
    if reason:
        assert result["quality"]["reason"] == reason


# ------------------------------------------- 1. valid PNG / JPG extraction
def test_valid_png_extraction(gemini):
    result = ocr.extract_report(PNG_BYTES, "report.png")
    assert ocr.validate_json_a(result) == []
    assert result["quality"] == {"status": "good", "confidence": 0.94}
    assert result["report_date"] == "2026-01-15"
    assert result["lab_name"] == "Example Lab"
    assert result["tests"][0] == {
        "test_name": "Hemoglobin", "value": 10.2, "unit": "g/dL",
        "reference_range": {"low": 12, "high": 16, "raw": "12-16"},
    }
    assert gemini.calls[0]["mime"] == "image/png"
    assert gemini.calls[0]["model"] == ocr.DEFAULT_MODEL


def test_valid_jpg_extraction(gemini):
    result = ocr.extract_report(JPG_BYTES, "scan.JPG")
    assert result["quality"]["status"] == "good"
    assert gemini.calls[0]["mime"] == "image/jpeg"


def test_model_name_comes_from_env(gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    ocr.extract_report(PNG_BYTES, "r.png")
    assert gemini.calls[0]["model"] == "gemini-2.0-flash"


# ------------------------------------------------- 2. PDF: first page only
def _make_pdf(pages: int) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"CBC page {i + 1}")
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_first_page_only(gemini):
    result = ocr.extract_report(_make_pdf(pages=3), "report.pdf")
    assert result["quality"]["status"] == "good"
    assert len(gemini.calls) == 1                       # one image, not 3
    assert gemini.calls[0]["mime"] == "image/png"
    assert gemini.calls[0]["image"].startswith(b"\x89PNG")


# ---------------------------------------------------------- 3. invalid PDF
@pytest.mark.parametrize("blob", [b"%PDF-1.4 this is not a real pdf", b"garbage bytes"])
def test_invalid_pdf_is_unreadable_and_never_calls_gemini(gemini, blob):
    result = ocr.extract_report(blob, "broken.pdf")
    assert_unreadable(result, "pdf_error")
    assert gemini.calls == []


def test_unsupported_and_empty_files(gemini):
    assert_unreadable(ocr.extract_report(b"hello", "notes.txt"), "unsupported_file")
    assert_unreadable(ocr.extract_report(b"junk", "fake.png"), "unsupported_file")
    assert_unreadable(ocr.extract_report(b"", "empty.png"), "empty_file")
    assert gemini.calls == []


# ------------------------------------------------ 4. malformed Gemini JSON
@pytest.mark.parametrize("reply", ["{not json", "", "I cannot read this.", "[1, 2, 3]", None])
def test_malformed_gemini_json(gemini, reply):
    gemini.reply = reply if reply is not None else ""
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"), "malformed_response")


def test_missing_required_keys(gemini):
    payload = gemini_payload()
    del payload["tests"]
    gemini.reply = json.dumps(payload)
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"), "malformed_response")


# ------------------------------------------------- 5. Markdown-fenced JSON
def test_markdown_fenced_json(gemini):
    gemini.reply = "```json\n" + json.dumps(gemini_payload()) + "\n```"
    assert ocr.extract_report(PNG_BYTES, "r.png")["quality"]["status"] == "good"


def test_plain_fence_and_surrounding_prose(gemini):
    gemini.reply = "```\n" + json.dumps(gemini_payload()) + "\n```"
    assert ocr.extract_report(PNG_BYTES, "r.png")["quality"]["status"] == "good"
    gemini.reply = "Here you go: " + json.dumps(gemini_payload()) + " Hope it helps!"
    assert ocr.extract_report(PNG_BYTES, "r.png")["quality"]["status"] == "good"


# ------------------------------------------- 6-8. reference range parsing
@pytest.mark.parametrize("raw, low, high", [
    ("12-16", 12, 16),                      # 6
    ("12 - 16", 12, 16),
    ("4.0-11.0", 4.0, 11.0),
    ("4.0 - 11.0", 4.0, 11.0),
    ("12\u201316", 12, 16),                 # en dash
    ("13.5 to 17.5", 13.5, 17.5),
    ("12-16 g/dL", 12, 16),
    ("150,000-450,000", 150000, 450000),
    ("<5.0", None, 5.0),                    # 7: never invent a 0 lower bound
    ("< 5.0", None, 5.0),
    ("<=5", None, 5),
    ("\u22645.0", None, 5.0),
    (">10", 10, None),                      # 8: never invent an upper bound
    (">=10.5", 10.5, None),
    ("\u226510", 10, None),
])
def test_reference_range_numeric(raw, low, high):
    result = ocr.parse_reference_range(raw)
    assert result == {"low": low, "high": high, "raw": raw}
    # int-vs-float is preserved exactly as printed
    assert type(result["low"]) is type(low) and type(result["high"]) is type(high)


@pytest.mark.parametrize("raw", ["Negative", "Normal", "Not detected", "16-12", "12-16-20", "abc"])
def test_reference_range_not_representable_keeps_raw(raw):
    assert ocr.parse_reference_range(raw) == {"low": None, "high": None, "raw": raw}


@pytest.mark.parametrize("raw", [None, "", "   ", 12, ["12-16"]])
def test_reference_range_empty_is_null(raw):
    assert ocr.parse_reference_range(raw) == {"low": None, "high": None, "raw": None}


def test_low_high_are_rederived_from_raw_never_trusted_from_gemini(gemini):
    payload = gemini_payload()
    payload["tests"][0]["reference_range"] = {"low": 13, "high": 17, "raw": None}   # invented
    payload["tests"][1]["reference_range"] = {"low": 1, "high": 99, "raw": "4.0 - 11.0"}  # wrong
    gemini.reply = json.dumps(payload)
    tests = ocr.extract_report(PNG_BYTES, "r.png")["tests"]
    assert tests[0]["reference_range"] == {"low": None, "high": None, "raw": None}
    assert tests[1]["reference_range"] == {"low": 4.0, "high": 11.0, "raw": "4.0 - 11.0"}


# ----------------------------------------------------- 9. missing / nulls
def test_null_fields_are_preserved_not_guessed(gemini):
    payload = gemini_payload(report_date=None, lab_name=None)
    payload["tests"][0]["value"] = None
    payload["tests"][1]["unit"] = None
    payload["tests"][2]["reference_range"] = {"raw": None}
    gemini.reply = json.dumps(payload)
    result = ocr.extract_report(PNG_BYTES, "r.png")
    assert ocr.validate_json_a(result) == []
    assert result["report_date"] is None and result["lab_name"] is None
    assert result["tests"][0]["value"] is None
    assert result["tests"][1]["unit"] is None
    assert result["tests"][2]["reference_range"] == {"low": None, "high": None, "raw": None}
    assert result["quality"]["status"] in ("good", "low")


def test_ambiguous_or_invalid_date_becomes_null(gemini):
    for bad in ("15/01/2026", "2026-13-45", "January 2026", 20260115):
        gemini.reply = json.dumps(gemini_payload(report_date=bad))
        assert ocr.extract_report(PNG_BYTES, "r.png")["report_date"] is None


def test_non_numeric_value_becomes_null_and_numeric_string_is_accepted(gemini):
    payload = gemini_payload()
    payload["tests"][0]["value"] = "10.2"      # numeric string -> number
    payload["tests"][1]["value"] = "H 7.5"     # flagged text -> null (no guessing)
    gemini.reply = json.dumps(payload)
    tests = ocr.extract_report(PNG_BYTES, "r.png")["tests"]
    assert tests[0]["value"] == 10.2
    assert tests[1]["value"] is None


def test_report_with_missing_range_is_still_accepted(gemini):
    payload = gemini_payload()
    payload["tests"][0]["reference_range"] = {"raw": None}
    gemini.reply = json.dumps(payload)
    result = ocr.extract_report(PNG_BYTES, "r.png")
    assert result["quality"]["status"] == "good"
    assert result["tests"][0]["reference_range"]["raw"] is None


def test_diagnostic_extras_from_gemini_are_dropped(gemini):
    payload = gemini_payload(diagnosis="anemia")
    payload["tests"][0]["interpretation"] = "low - anemia"
    gemini.reply = json.dumps(payload)
    result = ocr.extract_report(PNG_BYTES, "r.png")
    assert "diagnosis" not in result
    assert "interpretation" not in result["tests"][0]
    assert "anemia" not in json.dumps(result).lower()


# ------------------------------------------------ 10. fewer than 3 tests
def test_fewer_than_three_tests_is_unreadable(gemini):
    payload = gemini_payload()
    payload["tests"] = payload["tests"][:2]
    gemini.reply = json.dumps(payload)
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"), "too_few_tests")


def test_tests_without_values_do_not_count_as_usable(gemini):
    payload = gemini_payload()
    for t in payload["tests"][2:]:
        t["value"] = None                       # only 2 usable values left
    gemini.reply = json.dumps(payload)
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"))


def test_too_many_nulls_is_unreadable(gemini):
    payload = gemini_payload()
    for t in payload["tests"]:
        t["unit"] = None
        t["reference_range"] = {"raw": None}    # 2 of 3 cells null per test = 67%
    gemini.reply = json.dumps(payload)
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"), "too_many_missing_fields")


# ------------------------------------------------------- quality: confidence
@pytest.mark.parametrize("conf, status", [
    (0.94, "good"), (0.75, "good"), (0.74, "low"), (0.40, "low"), (0.39, "unreadable"),
    (0.0, "unreadable"), (94, "good"), (None, "low"),
])
def test_confidence_thresholds(gemini, conf, status):
    gemini.reply = json.dumps(gemini_payload(quality={"status": "good", "confidence": conf}))
    result = ocr.extract_report(PNG_BYTES, "r.png")
    assert ocr.validate_json_a(result) == []
    assert result["quality"]["status"] == status


def test_not_a_cbc_report_is_unreadable(gemini):
    payload = gemini_payload(report_type="Lipid Profile")
    payload["tests"] = [
        {"test_name": n, "value": v, "unit": "mg/dL", "reference_range": {"raw": "<200"}}
        for n, v in (("Cholesterol", 180), ("Triglycerides", 140), ("HDL", 50))
    ]
    gemini.reply = json.dumps(payload)
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"), "not_a_cbc_report")


def test_cbc_recognised_from_test_names_when_type_missing(gemini):
    gemini.reply = json.dumps(gemini_payload(report_type=None))
    assert ocr.extract_report(PNG_BYTES, "r.png")["quality"]["status"] == "good"


# ------------------------------------------------------ 11. 429 retry/backoff
def test_429_then_success_retries_with_backoff(gemini):
    gemini.reply = [FakeAPIError(429), FakeAPIError(429), json.dumps(gemini_payload())]
    result = ocr.extract_report(PNG_BYTES, "r.png")
    assert result["quality"]["status"] == "good"
    assert len(gemini.calls) == 3
    assert len(gemini.sleeps) == 2
    assert 2.0 <= gemini.sleeps[0] < 2.6        # ~2s
    assert 4.0 <= gemini.sleeps[1] < 4.6        # ~4s (exponential)


def test_429_forever_gives_up_after_max_attempts(gemini):
    gemini.reply = FakeAPIError(429, "RESOURCE_EXHAUSTED")
    result = ocr.extract_report(PNG_BYTES, "r.png")
    assert_unreadable(result, "rate_limited")
    assert len(gemini.calls) == ocr.MAX_ATTEMPTS == 3     # bounded, no infinite loop
    assert len(gemini.sleeps) == ocr.MAX_ATTEMPTS - 1


def test_503_is_retried_but_400_is_not(gemini):
    gemini.reply = [FakeAPIError(503), json.dumps(gemini_payload())]
    assert ocr.extract_report(PNG_BYTES, "r.png")["quality"]["status"] == "good"
    assert len(gemini.calls) == 2

    gemini.calls.clear()
    gemini.reply = FakeAPIError(400, "bad image")
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"), "bad_request")
    assert len(gemini.calls) == 1                          # invalid upload: no retry


def test_rate_limit_detected_from_message_text(gemini):
    gemini.reply = [Exception("429 RESOURCE_EXHAUSTED: quota"), json.dumps(gemini_payload())]
    assert ocr.extract_report(PNG_BYTES, "r.png")["quality"]["status"] == "good"


# ------------------------------------------------ 12. completely unreadable
def test_gemini_reports_unreadable(gemini):
    gemini.reply = json.dumps({
        "report_date": None, "lab_name": None, "report_type": None,
        "quality": {"status": "unreadable", "confidence": 0.05}, "tests": [],
    })
    result = ocr.extract_report(PNG_BYTES, "blurry.jpg")
    assert_unreadable(result, "model_reported_unreadable")
    assert result["quality"]["confidence"] == 0.05


def test_blank_or_unrelated_image_with_hallucinated_tests_is_rejected(gemini):
    gemini.reply = json.dumps(gemini_payload(quality={"status": "unreadable", "confidence": 0.1}))
    assert_unreadable(ocr.extract_report(PNG_BYTES, "blank.png"))


# --------------------------------------------------------- robustness
def test_missing_api_key(gemini, monkeypatch):
    monkeypatch.setattr(ocr, "_get_api_key", lambda: None)
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"), "config_error")
    assert gemini.calls == []


def test_extract_report_never_raises(gemini, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("something unexpected")
    monkeypatch.setattr(ocr, "_clean_tests", boom)
    assert_unreadable(ocr.extract_report(PNG_BYTES, "r.png"), "unexpected_error")


def test_failure_shape_matches_contract():
    f = ocr._failure("x", "msg")
    assert f["quality"]["status"] == "unreadable" and f["quality"]["confidence"] == 0
    assert f["tests"] == [] and ocr.validate_json_a(f) == []


def test_validate_json_a_catches_bad_output():
    assert ocr.validate_json_a({}) != []
    bad = {"report_date": None, "lab_name": None, "report_type": "CBC",
           "quality": {"status": "great", "confidence": 2}, "tests": [{"test_name": "Hb"}]}
    assert len(ocr.validate_json_a(bad)) >= 3
