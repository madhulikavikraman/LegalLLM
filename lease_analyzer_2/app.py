"""
Lease Risk Analyzer — free & local RAG app.

Run with:
    streamlit run app.py

Everything runs on free, open-source models:
  - Embeddings: sentence-transformers/all-MiniLM-L6-v2
  - Generation: Qwen/Qwen2.5-7B-Instruct (local, no API key)
  - OCR fallback: pytesseract + poppler
"""
import os
import tempfile
import streamlit as st
import nltk

from core.extraction import (
    extract_visible_text, extract_form_fields, ocr_pdf_pages, needs_ocr,
    extract_parties, extract_dates_from_text, infer_rent_and_deposit,
    deterministic_checklist, find_candidates_in_ocr,
)
from core.risk_rules import scan_risky_clauses, risk_score, severity_label
from core.rag_engine import load_embedder, load_llm, chunk_text, build_index, answer_question, explain_clause_plainly
from core import infographics as ig
from core.report import build_pdf_report

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

st.set_page_config(page_title="Lease Risk Analyzer", page_icon="📄", layout="wide")

# ---------- Sidebar ----------
st.sidebar.title("📄 Lease Risk Analyzer")
st.sidebar.caption("Free & local — no API keys, no data leaves your machine.")
uploaded = st.sidebar.file_uploader("Upload a lease/rental agreement (PDF)", type=["pdf"])
run_ocr_always = st.sidebar.checkbox("Force OCR (for scanned PDFs)", value=False)
model_choice = st.sidebar.selectbox(
    "Local LLM (bigger = slower, more accurate)",
    ["Qwen/Qwen2.5-7B-Instruct", "google/flan-t5-large"],
    index=0,
)
st.sidebar.markdown("---")
st.sidebar.caption("⚠️ This tool gives general information only, not legal advice. Consult a local tenant-rights organization or attorney for anything binding.")

st.title("Lease / Rental Agreement Risk Analyzer")
st.write("Upload a lease PDF to get a plain-English risk score, flagged risky clauses, key facts (rent, deposit, dates, parties), and a downloadable report — all generated locally.")

if uploaded is None:
    st.info("👆 Upload a PDF in the sidebar to get started.")
    st.stop()

# ---------- Pipeline (cached per file) ----------
@st.cache_data(show_spinner=False)
def process_pdf(file_bytes, force_ocr):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        pdf_path = tmp.name

    visible_text = extract_visible_text(pdf_path)
    form_fields = extract_form_fields(pdf_path)

    ocr_texts, ocr_page_data = [], []
    if force_ocr or needs_ocr(visible_text):
        ocr_texts, ocr_page_data = ocr_pdf_pages(pdf_path)

    ocr_combined = "\n".join(ocr_texts)
    full_text = (visible_text + "\n\n" + ocr_combined).strip()

    ocr_candidates = []
    for i, pdata in enumerate(ocr_page_data):
        page_txt = ocr_texts[i] if i < len(ocr_texts) else ""
        for c in find_candidates_in_ocr(pdata, page_txt):
            ocr_candidates.append((i, c[0], c[1], c[2]))

    parties = extract_parties(full_text, form_fields)
    dates = extract_dates_from_text(full_text)
    rent_val, deposit_val = infer_rent_and_deposit(visible_text or full_text, form_fields, ocr_candidates)
    present, missing = deterministic_checklist(full_text)
    findings = scan_risky_clauses(full_text)
    score = risk_score(findings)
    severity = severity_label(score)

    os.unlink(pdf_path)
    return dict(
        full_text=full_text, parties=parties, dates=dates, rent_val=rent_val,
        deposit_val=deposit_val, present=present, missing=missing,
        findings=findings, score=score, severity=severity,
    )


with st.spinner("Extracting text, running OCR fallback if needed, and scanning for risky clauses..."):
    data = process_pdf(uploaded.getvalue(), run_ocr_always)

if len(data["full_text"].strip()) < 50:
    st.error("Couldn't extract meaningful text from this PDF. Try enabling 'Force OCR' in the sidebar.")
    st.stop()

# ---------- Top-level dashboard ----------
col1, col2 = st.columns([1, 1.3])
with col1:
    st.plotly_chart(ig.risk_gauge(data["score"], data["severity"]), use_container_width=True)
with col2:
    st.plotly_chart(ig.severity_breakdown_chart(data["findings"]), use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(ig.rent_deposit_chart(data["rent_val"], data["deposit_val"]), use_container_width=True)
with col4:
    st.plotly_chart(ig.risky_clause_bar(data["findings"]), use_container_width=True)

st.plotly_chart(ig.clause_coverage_chart(data["present"], data["missing"]), use_container_width=True)

# ---------- Key facts ----------
st.subheader("Key Facts")
fc1, fc2, fc3, fc4 = st.columns(4)
fc1.metric("Monthly Rent", f"${data['rent_val']:,.0f}" if data["rent_val"] else "Not found")
fc2.metric("Security Deposit", f"${data['deposit_val']:,.0f}" if data["deposit_val"] else "Not found")
fc3.metric("Landlord", data["parties"].get("landlord") or "Not found")
fc4.metric("Tenant", data["parties"].get("tenant") or "Not found")
if data["dates"]:
    st.caption("Key dates found: " + ", ".join(data["dates"]))

# ---------- Risky clauses detail ----------
st.subheader("🚩 Risky Clauses Detected")
if not data["findings"]:
    st.success("No high-risk clause patterns were detected by the rule engine.")
else:
    sev_emoji = {3: "🔴", 2: "🟠", 1: "🟡"}
    tok, model = None, None
    explain_toggle = st.checkbox("Generate plain-English explanations with local LLM (slower)", value=False)
    if explain_toggle:
        with st.spinner(f"Loading {model_choice}..."):
            tok, model = load_llm(model_choice)
    for f in data["findings"]:
        with st.expander(f"{sev_emoji[f['severity']]} {f['label']}  —  {['Low','Medium','High'][f['severity']-1] if f['severity']<=1 else {1:'Low',2:'Medium',3:'High'}[f['severity']]} severity"):
            st.write(f"**Why it matters:** {f['why']}")
            st.write("**Matched clause text:**")
            for m in f["matches"]:
                st.markdown(f"> {m}")
            if explain_toggle and tok is not None:
                plain = explain_clause_plainly(f["label"], f["matches"][0], tok, model)
                st.info(f"**In plain English:** {plain}")

# ---------- Clause coverage ----------
st.subheader("✅ Standard Clause Coverage")
cc1, cc2 = st.columns(2)
cc1.write("**Present:**")
cc1.write(", ".join(data["present"]) or "None")
cc2.write("**Missing:**")
cc2.write(", ".join(data["missing"]) or "None")

# ---------- RAG Q&A ----------
st.subheader("💬 Ask Questions About This Lease")
st.caption("Powered by a local retrieval-augmented FLAN-T5 model — answers are grounded only in the uploaded document.")

with st.spinner("Preparing search index (first time only)..."):
    embedder = load_embedder()
    chunks = chunk_text(data["full_text"])
    index = build_index(chunks, embedder)

preset_questions = [
    "What are the rules about pets?",
    "What happens if rent is paid late?",
    "How much notice must the landlord give before entering?",
    "Is subletting allowed?",
    "What utilities is the tenant responsible for?",
    "What are the conditions for getting the security deposit back?",
]
q = st.selectbox("Quick questions:", ["(choose one)"] + preset_questions)
custom_q = st.text_input("...or type your own question:")
final_q = custom_q.strip() or (q if q != "(choose one)" else "")

if final_q:
    if st.button("Get Answer"):
        with st.spinner(f"Loading {model_choice} and generating answer..."):
            tok, model = load_llm(model_choice)
            answer = answer_question(final_q, chunks, index, embedder, tok, model)
        st.markdown(f"**Q: {final_q}**")
        st.markdown(f"A: {answer}")

# ---------- PDF report export ----------
st.subheader("📥 Export Report")
if st.button("Generate PDF Report"):
    with st.spinner("Building report..."):
        figs = {
            "risk_gauge": ig.risk_gauge(data["score"], data["severity"]),
            "severity": ig.severity_breakdown_chart(data["findings"]),
            "rent_deposit": ig.rent_deposit_chart(data["rent_val"], data["deposit_val"]),
            "risky_bar": ig.risky_clause_bar(data["findings"]),
            "coverage": ig.clause_coverage_chart(data["present"], data["missing"]),
        }
        out_path = os.path.join(tempfile.gettempdir(), "lease_risk_report.pdf")
        build_pdf_report(
            out_path, data["score"], data["severity"], data["parties"],
            data["rent_val"], data["deposit_val"], data["dates"],
            data["findings"], data["present"], data["missing"], figs,
        )
    with open(out_path, "rb") as f:
        st.download_button("Download PDF Report", f, file_name="lease_risk_report.pdf", mime="application/pdf")
