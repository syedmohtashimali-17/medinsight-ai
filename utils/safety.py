"""STUB (P3 owns the real version). Same signatures, dummy behaviour."""


def get_status(value, low, high) -> str:
    if value is None or (low is None and high is None):
        return "Cannot Determine"
    if low is not None and value < low:
        return "Below Range"
    if high is not None and value > high:
        return "Above Range"
    return "Within Range"


def filter_explanations(b: dict) -> dict:
    return b
