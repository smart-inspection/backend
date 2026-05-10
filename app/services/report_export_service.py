from pathlib import Path
from uuid import uuid4

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.db.models import ReportDraft


EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _get_draft_or_raise(db: Session, draft_id: int) -> ReportDraft:
    draft = db.query(ReportDraft).filter(ReportDraft.id == draft_id).first()
    if not draft:
        raise ValueError("Report draft not found")
    return draft


def _get_export_text(draft: ReportDraft) -> str:
    text = draft.edited_text or draft.generated_text
    if not text or not text.strip():
        raise ValueError("El borrador no contiene texto para exportar")
    return text.strip()


def _safe_filename(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value.strip().lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned[:80] or "reporte"


def export_report_draft_to_docx(db: Session, draft_id: int) -> Path:
    draft = _get_draft_or_raise(db, draft_id)
    text = _get_export_text(draft)

    file_name = f"{_safe_filename(draft.title)}_{uuid4().hex[:8]}.docx"
    output_path = EXPORT_DIR / file_name

    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

    title = document.add_heading(draft.title, level=1)
    title.alignment = 1

    document.add_paragraph(f"ID de inspección: {draft.inspection_id}")
    document.add_paragraph(f"Versión de plantilla: {draft.template_version}")
    document.add_paragraph(f"Estado del borrador: {draft.status}")

    document.add_paragraph("")

    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue

        if block.isupper() and len(block) < 120:
            document.add_heading(block, level=2)
        else:
            document.add_paragraph(block)

    document.save(output_path)
    return output_path


def _wrap_text_for_pdf(text: str, max_width: float, font_name: str, font_size: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def export_report_draft_to_pdf(db: Session, draft_id: int) -> Path:
    draft = _get_draft_or_raise(db, draft_id)
    text = _get_export_text(draft)

    file_name = f"{_safe_filename(draft.title)}_{uuid4().hex[:8]}.pdf"
    output_path = EXPORT_DIR / file_name

    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    left_margin = 2.5 * cm
    right_margin = 2.5 * cm
    top_margin = 2.5 * cm
    bottom_margin = 2.0 * cm
    usable_width = width - left_margin - right_margin

    y = height - top_margin

    def new_page():
        nonlocal y
        pdf.showPage()
        y = height - top_margin

    pdf.setTitle(draft.title)

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left_margin, y, draft.title[:90])
    y -= 1.0 * cm

    pdf.setFont("Helvetica", 10)
    pdf.drawString(left_margin, y, f"ID de inspección: {draft.inspection_id}")
    y -= 0.5 * cm
    pdf.drawString(left_margin, y, f"Versión de plantilla: {draft.template_version}")
    y -= 0.5 * cm
    pdf.drawString(left_margin, y, f"Estado del borrador: {draft.status}")
    y -= 1.0 * cm

    for paragraph in text.split("\n"):
        paragraph = paragraph.rstrip()

        if not paragraph:
            y -= 0.35 * cm
            if y < bottom_margin:
                new_page()
            continue

        is_heading = paragraph.isupper() and len(paragraph) < 120

        if is_heading:
            pdf.setFont("Helvetica-Bold", 12)
            lines = _wrap_text_for_pdf(paragraph, usable_width, "Helvetica-Bold", 12)
            line_height = 16
        else:
            pdf.setFont("Helvetica", 10)
            lines = _wrap_text_for_pdf(paragraph, usable_width, "Helvetica", 10)
            line_height = 13

        for line in lines:
            if y < bottom_margin:
                new_page()
                pdf.setFont("Helvetica-Bold" if is_heading else "Helvetica", 12 if is_heading else 10)

            pdf.drawString(left_margin, y, line)
            y -= line_height

        y -= 4

    pdf.save()
    return output_path