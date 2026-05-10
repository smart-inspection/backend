from io import BytesIO
from pathlib import Path
from uuid import uuid4

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from sqlalchemy.orm import Session

from app.services.report_template_service import build_company_report_context
from app.db.models import ReportDraft
from app.services.report_status_service import register_report_event


EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value.strip().lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned[:80] or "reporte"


def _set_doc_font(run, bold=False, size=11):
    run.font.name = "Arial"
    run.font.bold = bold
    run.font.size = Pt(size)


def _add_heading(document: Document, text: str, level=1, center=False):
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    _set_doc_font(run, bold=True, size=16 if level == 1 else 13)
    return p


def _add_paragraph(document: Document, text: str, bold_label: str | None = None):
    p = document.add_paragraph()
    if bold_label:
        r1 = p.add_run(f"{bold_label}: ")
        _set_doc_font(r1, bold=True, size=11)
    r2 = p.add_run(text)
    _set_doc_font(r2, size=11)
    return p


def _add_two_col_methods(document: Document, methods: list[str]):
    table = document.add_table(rows=len(methods), cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for idx, method in enumerate(methods):
        cell = table.cell(idx, 0)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(method)
        _set_doc_font(run, bold=True, size=11)


def _add_identification_table(document: Document, data: dict):
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    rows = [
        ("Tipo de Equipo", data["tipo_equipo"]),
        ("Placa", data["placa"]),
        ("Marca", data["marca"]),
        ("N° de VIN", data["vin"]),
        ("Año de fabricación", data["anio_fabricacion"]),
        ("Kilometraje de referencia", data["kilometraje"]),
        ("Antigüedad", data["antiguedad"]),
        ("N° de ejes", data["numero_ejes"]),
        ("Carga útil", data["carga_util"]),
        ("Peso neto", data["peso_neto"]),
        ("Marca de King pin", data["marca_king_pin"]),
        ("Modelo de King pin", data["modelo_king_pin"]),
        ("Serie de King pin", data["serie_king_pin"]),
    ]

    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value or "No registrado"


def _add_bullets(document: Document, items: list[str]):
    for item in items:
        p = document.add_paragraph(style="List Bullet")
        run = p.add_run(item)
        _set_doc_font(run, size=11)


def _add_results_table(document: Document, rows_data: list[dict]):
    table = document.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Equipo", "Componente", "Condición", "Observaciones", "Acción Correctiva"]
    for idx, text in enumerate(headers):
        run = table.rows[0].cells[idx].paragraphs[0].add_run(text)
        _set_doc_font(run, bold=True, size=10)

    for row in rows_data:
        cells = table.add_row().cells
        cells[0].text = row["equipo"]
        cells[1].text = row["componente"]
        cells[2].text = row["condicion"]
        cells[3].text = row["observaciones"]
        cells[4].text = row["accion"]


def _add_evidence_blocks(document: Document, evidences: list[dict]):
    _add_heading(document, "RESULTADOS Y EVIDENCIAS", level=1)
    for evidence in evidences:
        _add_paragraph(document, evidence["category"], bold_label=f"Foto {evidence['index']}")
        _add_paragraph(document, evidence["caption"], bold_label="Descripción")

        if evidence["path"] and Path(evidence["path"]).exists():
            try:
                document.add_picture(evidence["path"], width=Inches(4.8))
            except Exception:
                box = document.add_paragraph("[No se pudo insertar la imagen. Revisar archivo de evidencia]")
                _set_doc_font(box.runs[0], size=11)
        else:
            box = document.add_table(rows=1, cols=1)
            box.style = "Table Grid"
            cell = box.cell(0, 0)
            cell.text = "\nESPACIO RESERVADO PARA EVIDENCIA FOTOGRÁFICA\n"
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        if evidence.get("ocr_text"):
            _add_paragraph(document, evidence["ocr_text"], bold_label="Texto OCR")
        document.add_paragraph("")


def export_report_draft_to_docx(
        db: Session,
        draft_id: int,
        user_id: int | None = None,
        user_name: str | None = None,
) -> Path:
    ctx = build_company_report_context(db, draft_id)
    header = ctx["header"]

    file_name = f"informe_empresarial_{_safe_filename(header['report_code'])}_{uuid4().hex[:8]}.docx"
    output_path = EXPORT_DIR / file_name

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    _add_heading(document, header["report_title"], level=1, center=True)
    _add_heading(document, header["report_code"], level=2, center=True)
    _add_heading(document, header["equipment_display"], level=2, center=True)

    _add_paragraph(document, header["inspection_type"], bold_label="TIPO DE INSPECCIÓN")
    _add_paragraph(document, header["inspection_date"], bold_label="FECHA DE INSPECCIÓN")
    _add_paragraph(document, " / ".join(header["methods"]), bold_label="MÉTODOS EMPLEADOS")
    _add_paragraph(document, header["general_condition"], bold_label="CONDICIÓN GENERAL DEL EQUIPO")
    _add_paragraph(document, header["location"], bold_label="UBICACIÓN")

    document.add_page_break()

    _add_heading(document, "INFORME TÉCNICO", level=1, center=True)
    _add_paragraph(document, ctx["technical_info"]["requested_by"], bold_label="SOLICITADO POR")
    _add_paragraph(document, ctx["technical_info"]["address"], bold_label="DIRECCIÓN")
    _add_paragraph(document, ctx["technical_info"]["service_responsible"], bold_label="RESPONSABLE DEL SERVICIO")
    _add_paragraph(document, ctx["technical_info"]["inspection_date_text"], bold_label="FECHA DE INSPECCIÓN")
    document.add_paragraph(ctx["technical_info"]["intro_paragraph"])

    _add_heading(document, "1. IDENTIFICACIÓN DEL EQUIPO INSPECCIONADO", level=2)
    _add_identification_table(document, ctx["identification"])

    _add_heading(document, "2. OBJETIVO", level=2)
    document.add_paragraph(ctx["objective"])

    _add_heading(document, "3. ALCANCE", level=2)
    _add_bullets(document, ctx["scope"])

    _add_heading(document, "4. PROTOCOLO EMPLEADO", level=2)
    document.add_paragraph(ctx["protocol"])

    _add_heading(document, "5. FRECUENCIA DE INSPECCIÓN", level=2)
    document.add_paragraph(ctx["frequency"])

    _add_heading(document, "6. NORMAS Y CÓDIGOS DE REFERENCIA", level=2)
    _add_bullets(document, ctx["standards"])

    _add_heading(document, "7. EQUIPOS DE INSPECCIÓN EMPLEADOS", level=2)
    _add_paragraph(document, " | ".join(ctx["inspection_equipment"]["mt"]), bold_label="Magnetic Testing (MT)")
    _add_paragraph(document, " | ".join(ctx["inspection_equipment"]["vt"]), bold_label="Visual Testing (VT)")

    _add_heading(document, "8. CRITERIOS DE INSPECCIÓN", level=2)
    _add_paragraph(document, ctx["criteria"]["accepted"], bold_label="ACEPTADO")
    _add_paragraph(document, ctx["criteria"]["rejected"], bold_label="RECHAZADO")
    _add_paragraph(document, ctx["criteria"]["retirement"], bold_label="RETIRO DE OPERACIÓN")

    _add_heading(document, "9. RESULTADOS DE LA INSPECCIÓN", level=2)
    _add_results_table(document, ctx["results"])

    _add_heading(document, "10. CONCLUSIONES", level=2)
    document.add_paragraph(ctx["conclusion"])

    _add_heading(document, "HALLAZGOS PRINCIPALES", level=2)
    document.add_paragraph(ctx["findings"])

    _add_heading(document, "VALIDACIÓN OCR", level=2)
    document.add_paragraph(ctx["ocr_summary"])

    _add_heading(document, "OBSERVACIONES TRANSCRITAS", level=2)
    document.add_paragraph(ctx["voice_summary"])

    _add_heading(document, "RECOMENDACIONES", level=2)
    document.add_paragraph(ctx["recommendations"])

    document.add_page_break()
    _add_evidence_blocks(document, ctx["evidences"])

    document.save(output_path)

    draft = db.query(ReportDraft).filter(ReportDraft.id == draft_id).first()
    if draft:
        draft.last_action = "exported_docx"
        register_report_event(
            db=db,
            report_draft=draft,
            action="exported_docx",
            actor_user_id=user_id,
            actor_name=user_name,
            from_status=draft.status,
            to_status=draft.status,
            metadata_json={"format": "docx", "file_name": file_name},
        )
        db.add(draft)
        db.commit()

    return output_path


def export_report_draft_to_pdf(
    db: Session,
    draft_id: int,
    user_id: int | None = None,
    user_name: str | None = None,
) -> Path:
    ctx = build_company_report_context(db, draft_id)
    header = ctx["header"]

    file_name = f"informe_empresarial_{_safe_filename(header['report_code'])}_{uuid4().hex[:8]}.pdf"
    output_path = EXPORT_DIR / file_name

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=16, alignment=1, spaceAfter=10)
    h_style = ParagraphStyle("HeadingX", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, spaceAfter=6, spaceBefore=10)
    body = ParagraphStyle("BodyX", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=14, spaceAfter=6)

    story = []
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)

    story.append(Paragraph(header["report_title"], title_style))
    story.append(Paragraph(header["report_code"], title_style))
    story.append(Paragraph(header["equipment_display"], title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>TIPO DE INSPECCIÓN:</b> {header['inspection_type']}", body))
    story.append(Paragraph(f"<b>FECHA DE INSPECCIÓN:</b> {header['inspection_date']}", body))
    story.append(Paragraph(f"<b>MÉTODOS EMPLEADOS:</b> {' / '.join(header['methods'])}", body))
    story.append(Paragraph(f"<b>CONDICIÓN GENERAL DEL EQUIPO:</b> {header['general_condition']}", body))
    story.append(PageBreak())

    story.append(Paragraph("INFORME TÉCNICO", title_style))
    story.append(Paragraph(f"<b>SOLICITADO POR:</b> {ctx['technical_info']['requested_by']}", body))
    story.append(Paragraph(f"<b>DIRECCIÓN:</b> {ctx['technical_info']['address']}", body))
    story.append(Paragraph(f"<b>RESPONSABLE DEL SERVICIO:</b> {ctx['technical_info']['service_responsible']}", body))
    story.append(Paragraph(f"<b>FECHA DE INSPECCIÓN:</b> {ctx['technical_info']['inspection_date_text']}", body))
    story.append(Paragraph(ctx["technical_info"]["intro_paragraph"], body))

    story.append(Paragraph("1. IDENTIFICACIÓN DEL EQUIPO INSPECCIONADO", h_style))
    id_table_data = [["Campo", "Valor"]] + [[k.replace("_", " ").title(), str(v)] for k, v in ctx["identification"].items()]
    id_table = Table(id_table_data, colWidths=[6*cm, 10*cm])
    id_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(id_table)
    story.append(Spacer(1, 8))

    for title, content in [
        ("2. OBJETIVO", ctx["objective"]),
        ("4. PROTOCOLO EMPLEADO", ctx["protocol"]),
        ("5. FRECUENCIA DE INSPECCIÓN", ctx["frequency"]),
        ("10. CONCLUSIONES", ctx["conclusion"]),
        ("HALLAZGOS PRINCIPALES", ctx["findings"]),
        ("VALIDACIÓN OCR", ctx["ocr_summary"]),
        ("OBSERVACIONES TRANSCRITAS", ctx["voice_summary"]),
        ("RECOMENDACIONES", ctx["recommendations"]),
    ]:
        story.append(Paragraph(title, h_style))
        story.append(Paragraph(content, body))

    story.append(Paragraph("3. ALCANCE", h_style))
    for item in ctx["scope"]:
        story.append(Paragraph(f"• {item}", body))

    story.append(Paragraph("6. NORMAS Y CÓDIGOS DE REFERENCIA", h_style))
    for item in ctx["standards"]:
        story.append(Paragraph(f"• {item}", body))

    story.append(Paragraph("7. EQUIPOS DE INSPECCIÓN EMPLEADOS", h_style))
    story.append(Paragraph(f"<b>MT:</b> {' | '.join(ctx['inspection_equipment']['mt'])}", body))
    story.append(Paragraph(f"<b>VT:</b> {' | '.join(ctx['inspection_equipment']['vt'])}", body))

    story.append(Paragraph("8. CRITERIOS DE INSPECCIÓN", h_style))
    story.append(Paragraph(f"<b>ACEPTADO:</b> {ctx['criteria']['accepted']}", body))
    story.append(Paragraph(f"<b>RECHAZADO:</b> {ctx['criteria']['rejected']}", body))
    story.append(Paragraph(f"<b>RETIRO DE OPERACIÓN:</b> {ctx['criteria']['retirement']}", body))

    story.append(Paragraph("9. RESULTADOS DE LA INSPECCIÓN", h_style))
    result_data = [["Equipo", "Componente", "Condición", "Observaciones", "Acción Correctiva"]]
    for row in ctx["results"]:
        result_data.append([row["equipo"], row["componente"], row["condicion"], row["observaciones"], row["accion"]])

    result_table = Table(result_data, colWidths=[3*cm, 4*cm, 2.5*cm, 4.5*cm, 3*cm])
    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(result_table)

    story.append(PageBreak())
    story.append(Paragraph("RESULTADOS Y EVIDENCIAS", title_style))
    for ev in ctx["evidences"]:
        story.append(Paragraph(f"<b>Foto {ev['index']}:</b> {ev['category']}", body))
        story.append(Paragraph(f"<b>Descripción:</b> {ev['caption']}", body))
        if ev["path"] and Path(ev["path"]).exists():
            try:
                story.append(RLImage(ev["path"], width=11*cm, height=7*cm))
            except Exception:
                placeholder = Table([["No se pudo renderizar la imagen"]], colWidths=[11*cm], rowHeights=[2*cm])
                placeholder.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
                story.append(placeholder)
        else:
            placeholder = Table([["ESPACIO RESERVADO PARA EVIDENCIA FOTOGRÁFICA"]], colWidths=[11*cm], rowHeights=[3*cm])
            placeholder.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ]))
            story.append(placeholder)

        if ev["ocr_text"]:
            story.append(Paragraph(f"<b>Texto OCR:</b> {ev['ocr_text']}", body))
        story.append(Spacer(1, 10))

    doc.build(story)

    draft = db.query(ReportDraft).filter(ReportDraft.id == draft_id).first()
    if draft:
        draft.last_action = "exported_pdf"
        register_report_event(
            db=db,
            report_draft=draft,
            action="exported_pdf",
            actor_user_id=user_id,
            actor_name=user_name,
            from_status=draft.status,
            to_status=draft.status,
            metadata_json={"format": "pdf", "file_name": file_name},
        )
        db.add(draft)
        db.commit()

    return output_path