"""Build a downloadable PDF summary report combining risk findings + chart images."""
import tempfile
import os
from fpdf import FPDF


class LeaseReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Lease Risk Analysis Report", ln=True, align="C")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "Generated automatically - not a substitute for legal advice", ln=True, align="C")
        self.set_text_color(0, 0, 0)
        self.ln(4)


def build_pdf_report(output_path, score, severity, parties, rent_val, deposit_val,
                      dates, findings, present, missing, figures: dict):
    pdf = LeaseReport()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, f"Overall Risk Score: {score}/100 ({severity})", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(2)
    pdf.cell(0, 7, f"Landlord: {parties.get('landlord') or 'Not found'}", ln=True)
    pdf.cell(0, 7, f"Tenant: {parties.get('tenant') or 'Not found'}", ln=True)
    pdf.cell(0, 7, f"Monthly Rent: {'$%.2f' % rent_val if rent_val else 'Not found'}", ln=True)
    pdf.cell(0, 7, f"Security Deposit: {'$%.2f' % deposit_val if deposit_val else 'Not found'}", ln=True)
    pdf.cell(0, 7, f"Key Dates: {', '.join(dates) if dates else 'Not found'}", ln=True)
    pdf.ln(4)

    tmp_dir = tempfile.mkdtemp()
    for name, fig in figures.items():
        img_path = os.path.join(tmp_dir, f"{name}.png")
        try:
            fig.write_image(img_path, width=900, height=500, scale=2)
            pdf.image(img_path, w=180)
            pdf.ln(4)
        except Exception:
            pass  # kaleido may be unavailable; report still generates text sections

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Risky Clauses Detected", ln=True)
    pdf.set_font("Helvetica", "", 10)
    if not findings:
        pdf.multi_cell(0, 6, "No high-risk clause patterns were detected by the rule engine.")
    for f in findings:
        pdf.set_font("Helvetica", "B", 11)
        sev = {3: "HIGH", 2: "MEDIUM", 1: "LOW"}[f["severity"]]
        pdf.multi_cell(0, 6, f"[{sev}] {f['label']}")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, f"Why it matters: {f['why']}")
        for m in f["matches"][:2]:
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(0, 5, f"  Clause text: \"{m[:220]}\"")
        pdf.ln(2)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Clause Coverage Checklist", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 130, 100)
    pdf.multi_cell(0, 6, "Present: " + ", ".join(present))
    pdf.set_text_color(200, 60, 40)
    pdf.multi_cell(0, 6, "Missing: " + (", ".join(missing) if missing else "None"))
    pdf.set_text_color(0, 0, 0)

    pdf.output(output_path)
    return output_path
