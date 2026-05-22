from __future__ import annotations

from fpdf import FPDF


def build_certificate_pdf(
    full_name: str,
    subscription: str | None,
    certificate_batch_label: str | None = None,
    certificate_date_text: str | None = None,
) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # Border frame to make a printable certificate-like layout.
    pdf.set_draw_color(60, 60, 60)
    pdf.set_line_width(1.2)
    pdf.rect(10, 10, 277, 190)
    pdf.set_line_width(0.3)
    pdf.rect(14, 14, 269, 182)

    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.ln(22)
    pdf.cell(0, 12, "Certificate of Completion", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 14)
    pdf.ln(4)
    pdf.cell(0, 9, "This certifies that", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 14, full_name, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 13)
    display_label = (certificate_batch_label or "").strip()
    if not display_label:
        display_label = (subscription or "").strip()
    else:
        # Improve flexibility: allow {batch_name} placeholder
        display_label = display_label.replace("{batch_name}", (subscription or "").strip())

    label = "has successfully completed the program"
    if display_label:
        label = f"has successfully completed: {display_label}"
    pdf.cell(0, 9, label, align="C", new_x="LMARGIN", new_y="NEXT")

    if (certificate_date_text or "").strip():
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, f"Date: {(certificate_date_text or '').strip()}", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(20)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Critical Care Classes", align="C")

    data = pdf.output(dest="S")
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, str):
        return data.encode("latin-1", errors="ignore")
    return bytes(data)

