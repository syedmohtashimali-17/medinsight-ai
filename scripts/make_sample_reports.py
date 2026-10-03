"""Generate the 5 SYNTHETIC CBC sample reports required by plan Sec. 19.

All data is fictional ("Example Lab", "Test Patient"). No real PHI.
Needs Pillow (dev-only dependency):  pip install pillow
Run from repo root:                  python scripts/make_sample_reports.py

Writes:
  data/sample_reports/cbc_jan_clear.png        1. clear image, Hb 10.2
  data/sample_reports/cbc_mar_clear.pdf        2. clear PDF,   Hb 11.4 (for comparison)
  data/sample_reports/cbc_other_layout.png     3. different lab layout
  data/sample_reports/cbc_blurry_dark.jpg      4. blurry / dark photo
  data/sample_reports/cbc_missing_range.png    5. missing reference ranges
  tests/fixtures/sample_ground_truth.json      what a correct extraction should contain
"""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample_reports"
FIXTURES = ROOT / "tests" / "fixtures"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BANNER = "SYNTHETIC SAMPLE - FICTIONAL DATA - NOT A REAL PATIENT"


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT, size)
    except OSError:  # fall back to Pillow's built-in font if DejaVu is missing
        return ImageFont.load_default()


# (name, value, unit, printed range or None)
JAN = [
    ("Hemoglobin", 10.2, "g/dL", "12.0-16.0"),
    ("WBC", 7.8, "x10^3/uL", "4.0 - 11.0"),
    ("RBC", 4.1, "x10^6/uL", "4.2-5.4"),
    ("Hematocrit", 33.0, "%", "36.0-46.0"),
    ("MCV", 80.5, "fL", "80-100"),
    ("MCH", 27.0, "pg", "27-33"),
    ("MCHC", 31.5, "g/dL", "32-36"),
    ("Platelets", 245, "x10^3/uL", "150-450"),
    ("Neutrophils", 58, "%", "40-75"),
    ("Lymphocytes", 32, "%", "20-45"),
]
MAR = [
    ("Hemoglobin", 11.4, "g/dL", "12.0-16.0"),
    ("WBC", 7.2, "x10^3/uL", "4.0 - 11.0"),
    ("RBC", 4.3, "x10^6/uL", "4.2-5.4"),
    ("Hematocrit", 35.1, "%", "36.0-46.0"),
    ("MCV", 81.2, "fL", "80-100"),
    ("MCH", 27.6, "pg", "27-33"),
    ("MCHC", 32.4, "g/dL", "32-36"),
    ("Platelets", 262, "x10^3/uL", "150-450"),
    ("Neutrophils", 56, "%", "40-75"),
    ("Lymphocytes", 34, "%", "20-45"),
]
OTHER = [  # different layout, units, naming, one-sided range, date with month name
    ("Haemoglobin (Hb)", 13.1, "g/dL", "13.0 - 17.0"),
    ("Total Leucocyte Count (TLC)", 9.4, "10^3/uL", "4.0 - 10.0"),
    ("Red Blood Cell Count", 4.9, "10^6/uL", "4.5 - 5.5"),
    ("Packed Cell Volume (PCV)", 41.0, "%", "40 - 50"),
    ("Platelet Count", 310, "10^3/uL", "150 - 410"),
    ("Basophils", 1, "%", "<2"),
    ("Eosinophils", 3, "%", "1 - 6"),
]
MISSING = [(n, v, u, None if n in ("Hemoglobin", "Platelets") else r) for n, v, u, r in JAN]


def layout_classic(title_date, tests, lab="Example Lab"):
    """Layout 1: simple centred table. Test | Result | Unit | Reference Range."""
    img = Image.new("RGB", (1000, 260 + 56 * len(tests)), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 24), lab, font=font(34, True), fill="black")
    d.text((40, 70), "COMPLETE BLOOD COUNT (CBC)", font=font(24, True), fill="black")
    d.text((40, 108), f"Report Date: {title_date}", font=font(20), fill="black")
    d.text((40, 136), "Patient: Test Patient (Fictional)   ID: 000-SAMPLE", font=font(20), fill="black")
    d.text((40, 164), BANNER, font=font(16, True), fill=(160, 0, 0))
    y = 205
    for x, h in zip((40, 330, 520, 700), ("Test", "Result", "Unit", "Reference Range")):
        d.text((x, y), h, font=font(20, True), fill="black")
    d.line((40, y + 32, 960, y + 32), fill="black", width=2)
    y += 46
    for name, val, unit, rng in tests:
        d.text((40, y), name, font=font(20), fill="black")
        d.text((330, y), str(val), font=font(20, True), fill="black")
        d.text((520, y), unit, font=font(20), fill="black")
        d.text((700, y), rng or "", font=font(20), fill="black")
        y += 56
    return img


def layout_other(tests):
    """Layout 2: grey header band, different column order and wording."""
    img = Image.new("RGB", (1100, 330 + 52 * len(tests)), (252, 252, 247))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 1100, 110), fill=(30, 70, 120))
    d.text((30, 20), "Sample Diagnostics Centre (Fictional)", font=font(32, True), fill="white")
    d.text((30, 66), "Haematology Department", font=font(20), fill=(220, 230, 245))
    d.text((30, 135), "HAEMOGRAM / CBC", font=font(26, True), fill="black")
    d.text((30, 180), "Collected: 15-Feb-2026     Reported: 15-Feb-2026", font=font(19), fill="black")
    d.text((30, 210), "Name: Test Patient (Fictional)     Age/Sex: 30/F", font=font(19), fill="black")
    d.text((30, 240), BANNER, font=font(16, True), fill=(160, 0, 0))
    y = 290
    d.rectangle((20, y - 6, 1080, y + 36), fill=(225, 230, 238))
    for x, h in zip((30, 440, 570, 700, 900), ("Investigation", "Result", "Units", "Ref. Interval", "")):
        d.text((x, y), h, font=font(19, True), fill="black")
    y += 54
    for i, (name, val, unit, rng) in enumerate(tests):
        if i % 2:
            d.rectangle((20, y - 8, 1080, y + 34), fill=(238, 241, 246))
        d.text((30, y), name, font=font(19), fill="black")
        d.text((440, y), str(val), font=font(19, True), fill="black")
        d.text((570, y), unit, font=font(19), fill="black")
        d.text((700, y), rng or "", font=font(19), fill="black")
        y += 52
    return img


def blur_and_darken(img):
    img = img.filter(ImageFilter.GaussianBlur(7))
    img = ImageEnhance.Brightness(img).enhance(0.28)
    img = img.resize((img.width // 3, img.height // 3)).resize(img.size)
    rnd = random.Random(7)
    px = img.load()
    for _ in range(40000):
        x, y = rnd.randrange(img.width), rnd.randrange(img.height)
        r, g, b = px[x, y]
        n = rnd.randint(-25, 25)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    return img


def truth(file, date, lab, tests, **extra):
    return {"file": file, "report_date": date, "lab_name": lab,
            "tests": [{"test_name": n, "value": v, "unit": u, "raw": r} for n, v, u, r in tests], **extra}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)

    jan = layout_classic("2026-01-15", JAN)
    jan.save(OUT / "cbc_jan_clear.png")
    layout_classic("2026-03-15", MAR).save(OUT / "cbc_mar_clear.pdf", "PDF", resolution=150)
    layout_other(OTHER).save(OUT / "cbc_other_layout.png")
    blur_and_darken(jan).save(OUT / "cbc_blurry_dark.jpg", quality=55)
    layout_classic("2026-01-15", MISSING).save(OUT / "cbc_missing_range.png")

    ground_truth = [
        truth("cbc_jan_clear.png", "2026-01-15", "Example Lab", JAN),
        truth("cbc_mar_clear.pdf", "2026-03-15", "Example Lab", MAR),
        truth("cbc_other_layout.png", "2026-02-15", "Sample Diagnostics Centre (Fictional)", OTHER),
        {"file": "cbc_blurry_dark.jpg", "expected_quality": "unreadable_or_low", "tests": []},
        truth("cbc_missing_range.png", "2026-01-15", "Example Lab", MISSING,
              note="Hemoglobin and Platelets have NO printed range: expect raw/low/high = null"),
    ]
    (FIXTURES / "sample_ground_truth.json").write_text(json.dumps(ground_truth, indent=2))
    print("Wrote 5 synthetic samples to", OUT)


if __name__ == "__main__":
    main()
