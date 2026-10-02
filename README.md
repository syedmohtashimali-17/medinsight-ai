# MedInsight AI

**Intelligent Medical Report Understanding & Tracking Assistant**

MedInsight AI helps ordinary people understand and track their **CBC (Complete Blood Count)** lab reports. Upload a report image or PDF, and the app extracts the tests, compares each value against the **lab's own printed reference range**, explains the result in plain **English or Roman Urdu**, and shows how values changed across multiple reports.

> **Disclaimer:** This tool helps explain laboratory information and does not replace professional medical advice or diagnosis. It is a hackathon MVP for educational purposes, not a medical product.

---

## Why this project

- CBC reports are full of technical terms, numbers and ranges that most people cannot interpret.
- Many users are more comfortable in Urdu / Roman Urdu, but reports are in English.
- With two or more reports over time, it is hard to see what actually changed.
- Many online explanations are either too technical or, worse, diagnostic ("you have anemia"), which is unsafe.

## Features

| Feature | Description |
|---|---|
| Upload | CBC report as image (PNG/JPG) or PDF |
| Extraction | Test name, value, unit, lab reference range, date, lab name (Gemini Vision) |
| Status | Within / Below / Above / Cannot Determine, computed in plain Python against the lab's own range |
| Explanation | Short plain-language explanation in English or Roman Urdu (Urdu is best-effort) |
| Quality check | Blurry or incomplete uploads are rejected with a request for a clearer file |
| Comparison | Two-report comparison with change and direction per test |
| Trend chart | Plotly chart of a test across reports, with the lab range band shown only when the range is consistent |
| Safety layer | No diagnosis, no medication advice, no invented ranges, disclaimer on every results page |
| Demo mode | Runs fully offline from sample data, with no API calls |

## How it works

```
Upload (image/PDF)
   -> Gemini Vision extracts structured JSON (tests, values, lab ranges)
   -> Status computed deterministically in Python vs. the lab's range
   -> Gemini explains each result in the chosen language
   -> Safety filter removes any diagnostic language
   -> Streamlit shows results table + explanation cards
   -> A second report enables comparison and trend charts
```

Key design rule: **all status logic is plain Python, not an LLM**, so "Below / Above / Within range" is 100% deterministic. The AI only explains; it never decides.

## Tech stack

| Component | Choice |
|---|---|
| Language | Python 3.10+ |
| UI | Streamlit |
| AI model | Google Gemini (`gemini-2.5-flash`, free tier) via `google-genai` |
| Charts / data | Plotly, pandas |
| PDF to image | PyMuPDF (`import fitz`) |
| Config | python-dotenv |
| Hosting | Streamlit Community Cloud |

No database, no login, no backend server. Session data lives in `st.session_state`.

## Project structure

```
medinsight-ai/
├── app.py                  # Streamlit UI + integration
├── requirements.txt
├── .env.example            # GEMINI_API_KEY=, GEMINI_MODEL=
├── .gitignore
├── README.md
├── utils/
│   ├── ocr.py              # extract_report()   - Gemini Vision extraction
│   ├── ai.py               # explain_report()   - language explanations
│   ├── safety.py           # get_status(), filter_explanations()
│   └── comparison.py       # compare_reports(), build_trend_data(), trend chart, demo mode
├── data/
│   └── sample_reports/     # synthetic sample reports and JSONs
└── tests/
    └── test_comparison.py
```

## Getting started

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/syedmohtashimali-17/medinsight-ai.git
cd medinsight-ai

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### 2. Add your Gemini API key

Get a free key from [Google AI Studio](https://aistudio.google.com/app/apikey), then:

```bash
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

Open `.env` and fill in:

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Never commit `.env`. It is already listed in `.gitignore`.

### 3. Run the app

```bash
streamlit run app.py
```

### Demo mode (no API calls)

Useful for rehearsals, or if the API is down or rate limited:

```bash
streamlit run app.py -- --demo-mode
```

Each press of **Scan** loads the next sample report (January, March, then another lab), so you can show extraction, comparison and the trend chart without any network access.

### Run the tests

```bash
pip install pytest
python -m pytest tests -q
```

## Data contracts

All modules exchange plain JSON. Field names must not change without team agreement.

**A. Extraction output** (`extract_report`)

```json
{
  "report_date": "2026-01-15",
  "lab_name": "Example Lab",
  "report_type": "CBC",
  "quality": {"status": "good", "confidence": 0.94},
  "tests": [
    {
      "test_name": "Hemoglobin",
      "value": 10.2,
      "unit": "g/dL",
      "reference_range": {"low": 12, "high": 16, "raw": "12-16"}
    }
  ]
}
```

`quality.status` is one of `good`, `low`, `unreadable`. Missing values or ranges are `null`. Nothing is ever guessed.

**B. Explanation output** (`explain_report`): per test `status`, `explanation`, `safety_note`.
Status is one of `Within Range`, `Below Range`, `Above Range`, `Cannot Determine`.

**C. Comparison output** (`compare_reports`): `previous_date`, `current_date`, `changes[]`, `only_in_previous`, `only_in_current`.
Each change has `direction` of `increased`, `decreased`, `unchanged`, or `cannot_compare` (null value or unit mismatch).

## Safety rules

MedInsight AI must never:

- diagnose any condition
- prescribe or suggest medication changes
- invent values or reference ranges
- replace the lab's own printed range
- treat "above / below range" as a diagnosis

Additional safeguards:

- Low-confidence extraction is not guessed. The user is asked for a clearer upload.
- "Reported laboratory result" and "AI explanation" are shown separately in the UI.
- A "Patient notes" or "Comments" section is stripped before the explanation step to reduce prompt-injection risk.
- A banned-word filter removes diagnostic phrasing from explanations.

## Privacy

Use only **synthetic or fully de-identified** reports in this repository. Never push real patient data to GitHub.

## Deployment (Streamlit Community Cloud)

1. Push the final code to the `main` branch.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app: repo `medinsight-ai`, branch `main`, main file `app.py`.
3. Under **Advanced settings > Secrets**, add:
   ```
   GEMINI_API_KEY = "your_key_here"
   ```
4. Deploy, open the live URL, and run the full workflow once.

## Limitations and future work

This is a 52-hour hackathon MVP. Out of scope for now:

- Other report types (LFT, KFT, etc.); CBC only
- Persistent storage and user accounts (state resets on refresh)
- PDF export of results
- Pure Urdu (Nastaliq) rendering polish; Roman Urdu is the primary non-English language
- Retrieval-augmented explanations (RAG)
- EHR / FHIR / HL7 integration

## Team

Built by a 4-member team at a university AI/GenAI hackathon, October 2026.

| Role | Area |
|---|---|
| P1 | Streamlit UI |
| P2 | Report extraction (Gemini Vision) |
| P3 | AI explanations and safety layer |
| P4 | Comparison, trend charts, integration, deployment |

---

*MedInsight AI helps users understand and compare their laboratory information without replacing a doctor.*
