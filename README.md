# LegalLLM
LLM-based system that uses RAG pipelines to detect risky/predatory clauses in rental/lease documents (IN-PROGRESS)

# LeaseGuard — AI-Powered Lease Agreement Analyzer
> **In Progress** — actively being developed as part of USC's GRIDS Club

A document intelligence pipeline that parses rental/lease agreements and flags missing clauses, extracts key financial terms, and answers natural language questions about the document.

---

## What It Does

- **Clause coverage check** — deterministically verifies presence of 18 standard lease sections (rent, security deposit, termination, entry rights, subletting policy, etc.)
- **Financial term extraction** — extracts rent and security deposit amounts using confidence-ranked candidate scoring across multiple sources
- **Freeform Q&A** — answers natural language questions about the lease, grounded strictly to retrieved context with a hard fallback if the answer isn't in the document

---

## Architecture

```
PDF Input
   │
   ├── pdfplumber (text layer extraction)
   ├── pypdf fallback
   └── Tesseract OCR fallback (scanned/image-based PDFs)
         │
         ▼
   Text + Form Fields
         │
         ├── Deterministic checklist (keyword matching → clause presence)
         ├── Heuristic extractor (rent/deposit with ranked candidate scoring)
         └── Semantic retrieval (FAISS + all-MiniLM-L6-v2)
                  │
                  ▼
            Flan-T5-small (context-grounded generation)
                  │
                  ▼
            Answer / Clause Report
```

---

## Stack

| Component | Tool |
|---|---|
| PDF extraction | `pdfplumber`, `pypdf`, `pdf2image` |
| OCR | `Tesseract`, `pytesseract` |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2) |
| Vector search | `FAISS` |
| Language model | `Flan-T5-small` (google/flan-t5-small) |
| Tokenization | `nltk` |

---

## Known Limitations / Ongoing Work

- **Model quality** — Flan-T5-small is a ceiling for nuanced legal reasoning; evaluating larger open-source alternatives (Mistral-7B, Llama 3.2)
- **Chunking** — current word-count-based chunking breaks clause context across boundaries; experimenting with clause-aware splitting
- **No UI yet** — currently runs as a notebook; a lightweight FastAPI + Streamlit interface is planned

---

## Status

This project is part of ongoing work at **USC GRIDS Club**.
Facing slight errors in the model understanding of lease text. Trying different models/prompts
