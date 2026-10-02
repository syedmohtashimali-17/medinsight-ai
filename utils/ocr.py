"""STUB (P2 owns the real version). Returns sample JSON-A so the app runs end to end."""
from utils.comparison import load_sample_report


def extract_report(file_bytes: bytes, filename: str) -> dict:
    return load_sample_report("jan_clear")
