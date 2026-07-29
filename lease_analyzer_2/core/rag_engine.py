"""
Free, local RAG pipeline:
  - sentence-transformers/all-MiniLM-L6-v2 for embeddings
  - faiss for vector search
  - google/flan-t5-base (swap to flan-t5-large if you have the RAM/GPU) for generation
No API keys, no paid services.
"""
import re
import streamlit as st
from nltk.tokenize import sent_tokenize
from sentence_transformers import SentenceTransformer
import faiss
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

DEFAULT_MODEL = "google/flan-t5-base"  # swap for flan-t5-large if resources allow


@st.cache_resource(show_spinner=False)
def load_embedder():
    return SentenceTransformer("all-MiniLM-L6-v2")


@st.cache_resource(show_spinner=False)
def load_llm(model_name: str = DEFAULT_MODEL):
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    return tok, model


def chunk_text(text: str, max_words: int = 120):
    chunks = []
    paragraphs = re.split(r'\n{2,}', text)
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len((current + " " + para).split()) > max_words and current:
            chunks.append(current.strip())
            current = para
        else:
            current = (current + " " + para).strip()
    if current.strip():
        chunks.append(current.strip())

    final_chunks = []
    for chunk in chunks:
        if len(chunk.split()) > max_words * 1.5:
            sents = sent_tokenize(chunk)
            cur = ""
            for s in sents:
                if len((cur + " " + s).split()) > max_words and cur:
                    final_chunks.append(cur.strip())
                    cur = s
                else:
                    cur = (cur + " " + s).strip()
            if cur.strip():
                final_chunks.append(cur.strip())
        else:
            final_chunks.append(chunk)
    return final_chunks


def build_index(chunks, embedder):
    embs = embedder.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    index = faiss.IndexFlatL2(embs.shape[1])
    index.add(embs)
    return index


def retrieve(query, k, chunks, index, embedder, tok, max_tokens=500):
    qv = embedder.encode([query], convert_to_numpy=True)
    D, I = index.search(qv, k)
    top = [chunks[idx] for idx in I[0] if 0 <= idx < len(chunks)]
    truncated, total = [], 0
    for chunk in top:
        n = len(tok.tokenize(chunk))
        if total + n > max_tokens:
            break
        truncated.append(chunk)
        total += n
    return truncated


def run_llm(prompt, tok, model, max_new_tokens=300):
    inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=1024).to(model.device)
    out = model.generate(**inputs, max_new_tokens=max_new_tokens, num_beams=4, early_stopping=True)
    return tok.decode(out[0], skip_special_tokens=True).strip()


def answer_question(query, chunks, index, embedder, tok, model, k=8):
    top_chunks = retrieve(query, k=k, chunks=chunks, index=index, embedder=embedder, tok=tok, max_tokens=700)
    if not top_chunks:
        return "Not mentioned in the document."
    context = "\n\n---\n\n".join(top_chunks)
    prompt = (
        "You are a strict legal document assistant. Answer ONLY using the CONTEXT below. "
        "Pay very close attention to WHO is responsible for each item (the tenant vs the landlord) — "
        "do not include an item unless the context explicitly says the TENANT pays/is responsible for it. "
        "If the context says the landlord pays for something, do NOT list it as a tenant responsibility. "
        "If the answer is not in the context, reply: Not mentioned in the document.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {query}\n\nANSWER:"
    )
    response = run_llm(prompt, tok, model)
    if not response or "not mentioned" in response.lower():
        return "Not mentioned in the document."
    return response.splitlines()[0].strip()


def explain_clause_plainly(clause_label: str, matched_sentence: str, tok, model):
    """Ask the local LLM to restate a risky clause in plain English for the user."""
    prompt = (
        "Rewrite the following lease clause in one simple, plain-English sentence "
        "that a non-lawyer tenant would understand. Do not add legal advice, just explain what it says.\n\n"
        f"CLAUSE TYPE: {clause_label}\n"
        f"CLAUSE TEXT: {matched_sentence}\n\nPLAIN ENGLISH:"
    )
    try:
        return run_llm(prompt, tok, model, max_new_tokens=80)
    except Exception:
        return matched_sentence