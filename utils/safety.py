"""utils/safety.py - Safety layer (P3).
Deterministic safety layer for MedInsight AI. No LLM calls in this file.

Public API
----------
get_status(value, low, high)                -> str
attach_status(report)                       -> list[dict]
strip_patient_notes(text)                   -> str
sanitize_report(report)                     -> dict
fallback_explanation(test_name, status, language) -> str
safety_note(language)                       -> str
check_explanation(text, allowed_numbers)    -> (bool, str)
filter_explanations(result, report=None)    -> dict
DISCLAIMER                                  -> str
"""

import logging
import re
from typing import Any, Optional

log = logging.getLogger("medinsight.safety")

WITHIN = "Within Range"
BELOW = "Below Range"
ABOVE = "Above Range"
CANNOT = "Cannot Determine"
VALID_STATUS = {WITHIN, BELOW, ABOVE, CANNOT}
VALID_LANGUAGES = {"English", "Urdu", "Roman Urdu"}

DISCLAIMER = (
    "This tool helps explain laboratory information and does not replace "
    "professional medical advice or diagnosis."
)


# --------------------------------------------------------------------------
# 1. Deterministic status (pure Python, never an LLM)
# --------------------------------------------------------------------------
def _num(x: Any) -> Optional[float]:
    """Convert to float or return None. Rejects bool, NaN, junk strings."""
    if x is None or isinstance(x, bool):
        return None
    try:
        f = float(str(x).strip()) if isinstance(x, str) else float(x)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # NaN check


def get_status(value: Any, low: Any, high: Any) -> str:
    """
    Compare a value to the lab's OWN printed range.
    - missing/unparsable value, or no usable bound  -> Cannot Determine
    - inverted range (low > high)                   -> Cannot Determine
    - one-sided ranges ("<5.0" => low=None, high=5.0) are supported
    - bounds are inclusive
    """
    v, lo, hi = _num(value), _num(low), _num(high)
    if v is None or (lo is None and hi is None):
        return CANNOT
    if lo is not None and hi is not None and lo > hi:
        return CANNOT
    if lo is not None and v < lo:
        return BELOW
    if hi is not None and v > hi:
        return ABOVE
    return WITHIN


def attach_status(report: dict) -> list:
    """Flatten JSON-A tests into dicts that include a computed status."""
    out = []
    if not isinstance(report, dict):
        return out
    tests = report.get("tests")
    for t in tests if isinstance(tests, list) else []:
        if not isinstance(t, dict):
            continue
        rng = t.get("reference_range")
        if not isinstance(rng, dict):
            rng = {}
        low, high = rng.get("low"), rng.get("high")
        out.append(
            {
                "test_name": t.get("test_name"),
                "value": t.get("value"),
                "unit": t.get("unit"),
                "low": low,
                "high": high,
                "raw_range": rng.get("raw"),
                "status": get_status(t.get("value"), low, high),
            }
        )
    return out


# --------------------------------------------------------------------------
# 2. Prompt-injection hardening
# --------------------------------------------------------------------------
_NOTES_HEADING = re.compile(
    r"^\s*(patient\s*notes?|clinical\s*notes?|comments?|remarks?|notes?|"
    r"additional\s*information|interpretation|advice)\s*[:\-]?.*$",
    re.IGNORECASE,
)


def strip_patient_notes(text: str) -> str:
    """
    Remove a free-text 'Patient notes / Comments / Remarks' section from raw
    OCR text. Everything from that heading to the end of the text is dropped
    (these sections sit at the bottom of lab reports), which is the
    conservative choice.
    """
    if not text:
        return ""
    kept = []
    for line in text.splitlines():
        if _NOTES_HEADING.match(line):
            break
        kept.append(line)
    return "\n".join(kept).strip()


_NAME_OK = re.compile(r"[^A-Za-z0-9 ()%/.,#+\-]")


def _clean_label(s: Any, max_len: int) -> str:
    """Whitelist characters so a test name/unit cannot carry instructions."""
    if s is None:
        return ""
    s = _NAME_OK.sub("", str(s))
    return re.sub(r"\s+", " ", s).strip()[:max_len]


def sanitize_report(report: dict) -> dict:
    """
    Return a minimal copy of JSON-A containing only structured, cleaned
    fields. Free-text keys (notes, comments, raw_text, ...) are discarded, so
    nothing a malicious report says can reach the explanation LLM.
    """
    clean_tests = []
    for t in attach_status(report):
        name = _clean_label(t["test_name"], 60)
        if not name:
            continue
        clean_tests.append(
            {
                "test_name": name,
                "value": _num(t["value"]),
                "unit": _clean_label(t["unit"], 20),
                "low": _num(t["low"]),
                "high": _num(t["high"]),
                "raw_range": _clean_label(t["raw_range"], 30),
                "status": t["status"],
            }
        )
    return {"tests": clean_tests}


# --------------------------------------------------------------------------
# 3. Safe fixed text (used as fallback and for safety_note)
# --------------------------------------------------------------------------
_FALLBACK = {
    "English": {
        WITHIN: "Your reported {name} value is within the reference range printed by the laboratory.",
        BELOW: "Your reported {name} value is below the reference range printed by the laboratory.",
        ABOVE: "Your reported {name} value is above the reference range printed by the laboratory.",
        CANNOT: "The value or the reference range for {name} is not clear in the report, so it cannot be compared with the laboratory range.",
    },
    "Roman Urdu": {
        WITHIN: "Aap ki reported {name} value laboratory ki di hui reference range ke andar hai.",
        BELOW: "Aap ki reported {name} value laboratory ki di hui reference range se neeche hai.",
        ABOVE: "Aap ki reported {name} value laboratory ki di hui reference range se upar hai.",
        CANNOT: "{name} ki value ya reference range report mein wazeh nahi hai, is liye ise lab ki range se compare nahi kiya ja sakta.",
    },
    "Urdu": {
        WITHIN: "آپ کی رپورٹ میں {name} کی قدر لیبارٹری کی دی ہوئی ریفرنس رینج کے اندر ہے۔",
        BELOW: "آپ کی رپورٹ میں {name} کی قدر لیبارٹری کی دی ہوئی ریفرنس رینج سے کم ہے۔",
        ABOVE: "آپ کی رپورٹ میں {name} کی قدر لیبارٹری کی دی ہوئی ریفرنس رینج سے زیادہ ہے۔",
        CANNOT: "رپورٹ میں {name} کی قدر یا ریفرنس رینج واضح نہیں ہے، اس لیے اسے لیب کی رینج سے موازنہ نہیں کیا جا سکتا۔",
    },
}

_SAFETY_NOTE = {
    "English": (
        "This only compares your number with the laboratory's printed range. "
        "Only a doctor, who can see your overall health and other results, can say what it means for you."
    ),
    "Roman Urdu": (
        "Is result ka clinical meaning doctor aapki overall health aur doosre "
        "results ko dekh kar hi bata sakta hai."
    ),
    "Urdu": "اس نتیجے کا طبی مطلب صرف ڈاکٹر ہی آپ کی مجموعی صحت اور دیگر نتائج دیکھ کر بتا سکتا ہے۔",
}


def _lang(language: str) -> str:
    return language if language in VALID_LANGUAGES else "English"


def fallback_explanation(test_name: str, status: str, language: str) -> str:
    status = status if status in VALID_STATUS else CANNOT
    name = _clean_label(test_name, 60) or "this test"
    return _FALLBACK[_lang(language)][status].format(name=name)


def safety_note(language: str) -> str:
    return _SAFETY_NOTE[_lang(language)]


# --------------------------------------------------------------------------
# 4. Banned-language filter
# --------------------------------------------------------------------------
_BANNED_PATTERNS = [
    # direct diagnosis phrasing
    r"\byou have\b", r"\byou've\b", r"\byou are (suffering|diagnosed|sick|ill)\b",
    r"\bdiagnos\w*", r"\bsuffer\w*",
    # named conditions
    r"an[a]?emi\w*", r"diabet\w*", r"cancer\w*", r"leuk[a]?emi\w*", r"thalass[a]?emi\w*",
    r"\binfection\w*", r"\bdisease\w*", r"\bdisorder\w*", r"\bdeficien\w*",
    r"\bpolycyth\w*", r"\bsepsis\b", r"\bmalaria\b", r"\bdengue\b",
    # treatment / medication advice
    r"\bprescri\w*", r"\bmedicat\w*", r"\bmedicine\w*", r"\bsupplement\w*",
    r"\btreat(ment|ments|ed)?\b", r"\btherapy\b",
    r"\btake\b.{0,40}\b(tablet|pill|capsule|dose|mg|syrup|iron|vitamin)",
    r"\b(tablet|pill|capsule|syrup)s?\b", r"\bshould (eat|take|stop|start|avoid)\b",
    # Roman Urdu
    r"\bkhoon ki kami\b", r"\banemia\b", r"\bbim[a]?ari\b", r"\bbeemari\b",
    r"\bdawa(i|ee)?\b", r"\bgoli\b", r"\bilaj\b", r"\btashkhees\b", r"\bsugar ki\b",
    # Urdu script
    r"خون کی کمی", r"ذیابیطس", r"کینسر", r"بیماری", r"دوا", r"گولی", r"علاج", r"تشخیص",
]
_BANNED_RE = re.compile("|".join(f"(?:{p})" for p in _BANNED_PATTERNS), re.IGNORECASE)
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers_in(text: str) -> set:
    return {float(m) for m in _NUM_RE.findall(text or "")}


def check_explanation(text: str, allowed_numbers: Optional[set] = None):
    """
    Return (is_safe, reason). Unsafe if the text is empty, contains banned
    diagnostic/medication language, or contains numbers that are not the
    test's own value or lab range (invented numbers).
    """
    if not isinstance(text, str) or not text.strip():
        return False, "empty"
    m = _BANNED_RE.search(text)
    if m:
        return False, f"banned phrase: {m.group(0)!r}"
    # allowed_numbers=None means "no report context": skip the number check
    extra = (_numbers_in(text) - allowed_numbers) if allowed_numbers is not None else set()
    if extra:
        return False, f"unexpected numbers: {sorted(extra)}"
    return True, "ok"


def _allowed_numbers(test: dict) -> set:
    nums = set()
    for k in ("value", "low", "high"):
        n = _num(test.get(k))
        if n is not None:
            nums.add(n)
    nums |= _numbers_in(str(test.get("raw_range") or ""))
    # numbers that are part of the unit or test name (e.g. "10^3/uL", "Neutrophils 2")
    nums |= _numbers_in(str(test.get("unit") or ""))
    nums |= _numbers_in(str(test.get("test_name") or ""))
    return nums


def filter_explanations(result: dict, report: Optional[dict] = None) -> dict:
    """
    Final gate on JSON-B before it reaches the UI.
    - status is ALWAYS recomputed from the report (never trusts the LLM)
    - unsafe explanation text is replaced by a fixed safe sentence
    - safety_note is always the fixed, vetted note
    """
    result = result if isinstance(result, dict) else {}
    language = _lang(result.get("language", "English"))
    lookup = {}
    if report is not None:
        for t in attach_status(report):
            lookup[_clean_label(t["test_name"], 60).lower()] = t

    cleaned = []
    for e in result.get("explanations") or []:
        if not isinstance(e, dict):
            continue
        name = _clean_label(e.get("test_name"), 60)
        test = lookup.get(name.lower(), {})
        status = test.get("status") or (
            e.get("status") if e.get("status") in VALID_STATUS else CANNOT
        )
        ok, reason = check_explanation(
            e.get("explanation"), _allowed_numbers(test) if test else None
        )
        if ok:
            text = e["explanation"].strip()
        else:
            log.warning("Explanation for %r replaced (%s)", name, reason)
            text = fallback_explanation(name, status, language)
        cleaned.append(
            {
                "test_name": name or e.get("test_name"),
                "status": status,
                "explanation": text,
                "safety_note": safety_note(language),
            }
        )
    return {"language": language, "explanations": cleaned}
