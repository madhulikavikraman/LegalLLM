# Lease Risk Analyzer

A free, fully local Python app that scans rental/lease agreement PDFs, flags risky
clauses, extracts key facts (rent, deposit, dates, parties), and generates
interactive infographics + a downloadable PDF report — no API keys, no paid services.

## Stack (100% free/open-source)
- **Extraction:** pdfplumber, pypdf, pdf2image + pytesseract (OCR fallback for scanned PDFs)
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2`
- **Vector search:** FAISS
- **Generation:** `google/flan-t5-base` (swap to `flan-t5-large` in the sidebar if you have the RAM/GPU)
- **Risk detection:** a hand-built rule engine (`core/risk_rules.py`) of ~15 common risky lease clause patterns (auto-renewal, uncapped rent hikes, non-refundable deposits, acceleration clauses, waiver of rights, unrestricted entry, etc.), scored by severity
- **UI:** Streamlit
- **Charts:** Plotly (risk gauge, severity breakdown, coverage checklist, key amounts)
- **Report export:** fpdf2 + kaleido (chart-to-image)

## Install

```bash
# System dependencies (Debian/Ubuntu) for OCR support
sudo apt-get update && sudo apt-get install -y poppler-utils tesseract-ocr

# Python dependencies
pip install -r requirements.txt
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

## Run

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`), and
upload a lease PDF in the sidebar.

## Project structure

```
lease_analyzer/
├── app.py                 # Streamlit UI — the entry point
├── core/
│   ├── extraction.py       # PDF/OCR text, parties, dates, rent/deposit extraction
│   ├── risk_rules.py        # Rule-based risky-clause detector + scoring
│   ├── rag_engine.py        # Embeddings + FAISS + local FLAN-T5 Q&A
│   ├── infographics.py      # Plotly chart builders
│   └── report.py            # PDF report generator
└── requirements.txt
```

## Notes
- First run downloads the embedding + LLM models (a few hundred MB); after that
  everything runs offline.
- `flan-t5-base` is fast on CPU; `flan-t5-large` is more accurate but slower —
  use a GPU if available.
- This tool is for informational purposes only and is **not legal advice**.
  Lease law (deposit caps, notice periods, allowable fees) varies significantly
  by state/country — always verify flagged clauses against local tenant law or
  consult a professional.
- Want more risk rules? Add entries to `RISK_RULES` in `core/risk_rules.py` —
  each just needs an id, label, severity (1-3), regex patterns, and a plain-English
  "why" explanation.
