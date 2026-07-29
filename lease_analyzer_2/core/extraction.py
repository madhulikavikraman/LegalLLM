"""
Text, form-field, party, and date extraction from lease PDFs.
Uses only free/local tools: pdfplumber, pypdf, pdf2image + pytesseract (OCR fallback).
"""
import re
import pdfplumber
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract


def extract_visible_text(pdf_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception:
        pass
    if not text.strip():
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        except Exception:
            pass
    return text


def extract_form_fields(pdf_path: str) -> dict:
    fields = {}
    try:
        reader = PdfReader(pdf_path)
        ff = reader.get_fields()
        if ff:
            for k, v in ff.items():
                val = v.get('/V') if isinstance(v, dict) else v
                if val is not None:
                    fields[str(k).lower()] = str(val)
    except Exception:
        pass
    return fields


def ocr_pdf_pages(pdf_path: str, dpi: int = 300, max_pages: int = None):
    """Returns (page_texts, page_data). Only runs if visible text extraction is weak."""
    images = convert_from_path(pdf_path, dpi=dpi)
    if max_pages:
        images = images[:max_pages]
    page_texts, page_data = [], []
    for img in images:
        if img.mode != "RGB":
            img = img.convert("RGB")
        txt = pytesseract.image_to_string(img)
        page_texts.append(txt)
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        except Exception:
            data = None
        page_data.append(data)
    return page_texts, page_data


def needs_ocr(visible_text: str) -> bool:
    """Heuristic: if very little text was extracted, the PDF is likely scanned."""
    return len(visible_text.strip()) < 200


# ---------- Parties ----------
PARTY_FIELD_HINTS = {
    "landlord": ["landlord", "owner", "lessor", "property_owner", "lessor_name", "party1", "party_1"],
    "tenant":   ["tenant", "lessee", "renter", "resident", "tenant_name", "lessee_name", "party2", "party_2"],
}

NAME_PATTERNS = [
    r'(?:landlord|owner|lessor)[^\n]{0,30}?(?:is|:)\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)',
    r'(?:tenant|lessee|renter)[^\n]{0,30}?(?:is|:)\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)',
    r'(?:between)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*(?:,|\(|hereinafter).*?(?:and|,)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)',
    r'([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*,?\s*(?:hereinafter|referred to as)\s*["\']?(?:Landlord|Owner|Lessor)',
    r'([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*,?\s*(?:hereinafter|referred to as)\s*["\']?(?:Tenant|Lessee|Renter)',
]


def extract_parties_from_fields(fields: dict) -> dict:
    result = {"landlord": None, "tenant": None}
    for role, hints in PARTY_FIELD_HINTS.items():
        for hint in hints:
            for k, v in fields.items():
                if hint in k and v.strip() and v.strip() not in ("/", "None", ""):
                    result[role] = v.strip()
                    break
            if result[role]:
                break
    return result


def extract_parties_from_text(text: str) -> dict:
    result = {"landlord": None, "tenant": None}
    lines = text[:3000]
    for pat in NAME_PATTERNS:
        matches = re.findall(pat, lines, re.IGNORECASE)
        if matches:
            flat = [m for group in matches for m in (group if isinstance(group, tuple) else [group]) if m]
            for name in flat:
                name = name.strip()
                if not name or len(name) < 4:
                    continue
                if any(w in name.lower() for w in ["landlord", "tenant", "lessee", "lessor", "herein"]):
                    continue
                if result["landlord"] is None:
                    result["landlord"] = name
                elif result["tenant"] is None and name != result["landlord"]:
                    result["tenant"] = name
                    break
    return result


def extract_parties(text: str, fields: dict) -> dict:
    ff = extract_parties_from_fields(fields)
    ft = extract_parties_from_text(text)
    return {
        "landlord": ff["landlord"] or ft["landlord"],
        "tenant": ff["tenant"] or ft["tenant"],
    }


# ---------- Dates ----------
MONTHS = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
ORDINAL = r'(?:st|nd|rd|th)?'
DATE_PATTERNS = [
    rf'{MONTHS}\s+\d{{1,2}}{ORDINAL}[,\s]+\d{{4}}',
    rf'\d{{1,2}}{ORDINAL}\s+(?:day\s+of\s+)?{MONTHS}[,\s]+\d{{4}}',
    r'\d{1,2}/\d{1,2}/\d{2,4}',
    r'\d{4}-\d{2}-\d{2}',
]
DATE_CONTEXT_PATTERNS = [
    r'(?:commenc(?:es?|ing)|start(?:s|ing)?|begin(?:s|ning)?)[^\n]{0,60}?(' + '|'.join(DATE_PATTERNS) + r')',
    r'(?:end(?:s|ing)?|expir(?:es?|ing)|terminat(?:es?|ing))[^\n]{0,60}?(' + '|'.join(DATE_PATTERNS) + r')',
    r'(?:from)[^\n]{0,30}?(' + '|'.join(DATE_PATTERNS) + r')[^\n]{0,30}?(?:to|through|until)[^\n]{0,30}?(' + '|'.join(DATE_PATTERNS) + r')',
    r'(?:lease term|term of|period of)[^\n]{0,60}?(' + '|'.join(DATE_PATTERNS) + r')',
]


def extract_dates_from_text(text: str) -> list:
    found = []
    search_text = text[:5000]
    for pat in DATE_CONTEXT_PATTERNS:
        for m in re.finditer(pat, search_text, re.IGNORECASE):
            found.extend([g for g in m.groups() if g])
    if not found:
        for pat in DATE_PATTERNS:
            found.extend(re.findall(pat, search_text, re.IGNORECASE))
    seen, unique = set(), []
    for d in found:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique[:4]


# ---------- Rent / Deposit ----------
def normalize_number_str(s):
    if not s:
        return None
    s = re.sub(r'[$,]', '', s)
    m = re.search(r'(\d{2,6}(?:\.\d{1,2})?)', s)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def plausible_currency(val, low=300, high=20000):
    return val is not None and low <= val <= high


def find_candidates_in_ocr(page_data, page_text, keywords=("rent", "deposit")):
    candidates = []
    if page_data is None:
        for ln in page_text.splitlines():
            if any(kw in ln.lower() for kw in keywords):
                for n in re.findall(r'\$?\s?(\d{2,6}(?:\.\d{1,2})?)', ln):
                    candidates.append(("ocr_line", ln, normalize_number_str(n)))
        return candidates
    page_lines = {}
    for i, txt in enumerate(page_data['text']):
        if not txt:
            continue
        key = (page_data['block_num'][i], page_data['par_num'][i], page_data['line_num'][i])
        page_lines.setdefault(key, []).append(txt)
    for wlist in page_lines.values():
        line = " ".join(wlist)
        if any(kw in line.lower() for kw in keywords):
            for n in re.findall(r'\$?\s?(\d{2,6}(?:\.\d{1,2})?)', line):
                candidates.append(("ocr_line", line, normalize_number_str(n)))
    return candidates


def infer_rent_and_deposit(text, fields, ocr_candidates):
    candidates = {"rent": [], "deposit": []}
    for k, v in fields.items():
        nv = normalize_number_str(v)
        if nv and plausible_currency(nv):
            if "rent" in k or "price" in k:
                candidates["rent"].append(("field", k, nv, 100))
            if "deposit" in k or "security" in k:
                candidates["deposit"].append(("field", k, nv, 100))
    for i, ln in enumerate([l.strip() for l in text.splitlines() if l.strip()]):
        low = ln.lower()
        for cat, patterns in [
            ("rent", ["monthly rent", "rent amount", "rent shall be", "rent is"]),
            ("deposit", ["security deposit", "deposit shall", "deposit is"]),
        ]:
            if any(p in low for p in patterns) or (cat in low and "$" in low):
                for n in re.findall(r'\$?\s?(\d{2,6}(?:\.\d{1,2})?)', ln):
                    nv = normalize_number_str(n)
                    if nv and plausible_currency(nv):
                        candidates[cat].append(("text_line", ln[:120], nv, 60 - i // 50))
    for (pg, typ, line, val) in ocr_candidates:
        if val is None:
            continue
        low = str(line).lower()
        if "rent" in low or "monthly" in low:
            candidates["rent"].append(("ocr", f"page{pg}", val, 70 - pg))
        if "deposit" in low:
            candidates["deposit"].append(("ocr", f"page{pg}", val, 70 - pg))
    for cat in ["rent", "deposit"]:
        if candidates[cat]:
            candidates[cat].sort(key=lambda x: (x[3], x[2]), reverse=True)
    rent_val = candidates["rent"][0][2] if candidates["rent"] else None
    dep_val = candidates["deposit"][0][2] if candidates["deposit"] else None
    return rent_val, dep_val


# ---------- Clause coverage checklist ----------
CLAUSE_SIGNATURES = {
    "Parties to the Agreement":  ["landlord", "tenant", "lessor", "lessee"],
    "Property Description":      ["premises", "property located at", "address", "unit", "apartment"],
    "Term / Duration":           ["term", "lease term", "commence", "commencement", "month-to-month"],
    "Rent":                      ["monthly rent", "rent amount", "rent shall be", "rent payable"],
    "Security Deposit":          ["security deposit", "deposit shall", "deposit is"],
    "Maintenance & Repairs":     ["maintenance", "repairs", "landlord shall", "tenant shall"],
    "Utilities Responsibility":  ["utilities", "water", "electricity", "gas", "sewer", "trash"],
    "Rules & Restrictions":      ["no smoking", "no pets", "occupancy limit", "restrictions"],
    "Termination & Renewal":     ["terminate", "termination", "renewal", "notice to vacate"],
    "Late Fees / Penalties":     ["late fee", "late charge", "penalty", "grace period"],
    "Privacy & Entry Rights":    ["entry", "landlord may enter", "notice before entry"],
    "Insurance Requirements":    ["insurance", "renter's insurance", "liability insurance"],
    "Subletting Policy":         ["sublet", "subletting", "assignment", "assign"],
    "Dispute Resolution":        ["arbitration", "mediation", "dispute resolution"],
    "Governing Law":             ["governing law", "laws of the state", "jurisdiction"],
    "Signatures & Date":         ["signature", "signed", "date", "tenant signature"],
    "Parking":                   ["parking", "garage", "parking space"],
    "Furnished/Unfurnished":     ["furnished", "unfurnished", "furniture included"],
}


def deterministic_checklist(text: str):
    tl = text.lower().replace("\n", " ")
    present, missing = [], []
    for sec, phrases in CLAUSE_SIGNATURES.items():
        (present if any(ph in tl for ph in phrases) else missing).append(sec)
    return present, missing
