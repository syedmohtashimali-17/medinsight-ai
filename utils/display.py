"""utils/display.py -- DISPLAY-ONLY text helpers for the UI.

Never write the output of these functions back into the report data:
comparison (P4) and status logic (P3) must keep the original text
exactly as extracted (e.g. 'x10^3/uL').
"""
import re

_SUPERSCRIPT = str.maketrans("0123456789-+", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺")


def pretty_unit(unit):
    """'x10^3/uL' -> '×10³/µL'.  Non-strings / empty values are returned unchanged."""
    if not isinstance(unit, str) or not unit:
        return unit
    s = unit
    s = re.sub(r"\b[xX]\s*(?=10\s*\^)", "×", s)                                      # x10^3 -> ×10^3
    s = re.sub(r"\^\s*\{?([+-]?\d+)\}?", lambda m: m.group(1).translate(_SUPERSCRIPT), s)  # ^3 -> ³
    s = re.sub(r"\bu(?=[A-Za-z]?L\b)", "µ", s)                                      # uL -> µL
    s = re.sub(r"\bu(?=g\b|m\b)", "µ", s)                                            # ug, um -> µg, µm
    return s
