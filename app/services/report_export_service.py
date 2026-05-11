from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.report_template_service import build_company_report_context

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT_DIR = Path("output/reports")

def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default

def _normalize_filename(value: str) -> str:
    text = _safe_text(value, "reporte")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "reporte"

def _ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def _existing_image(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if path.exists() and path.is_file():
        return str(path)
    return None

def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]

def _set_cell_text(cell, text: str, *, bold: bool = False, size: int = 10, align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    run = p.add_run(_safe_text(text, "--"))
    run.bold = bold
    run.font.name = "Arial"
    run.font.size = Pt(size)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

def _shade_cell(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)

def _set_cell_border(cell, **kwargs):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()

    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)

    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        edge_data = kwargs.get(edge)
        if not edge_data:
            continue

        tag = f"w:{edge}"
        element = tc_borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            tc_borders.append(element)

        for key in ["val", "sz", "space", "color"]:
            if key in edge_data:
                element.set(qn(f"w:{key}"), str(edge_data[key]))

def _apply_table_borders(table, color: str = "000000", size: int = 8):
    for row in table.rows:
        for cell in row.cells:
            _set_cell_border(
                cell,
                top={"val": "single", "sz": size, "color": color},
                bottom={"val": "single", "sz": size, "color": color},
                left={"val": "single", "sz": size, "color": color},
                right={"val": "single", "sz": size, "color": color},
            )

def _add_page_number_fields(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    run = paragraph.add_run()
    run.font.name = "Arial"
    run.font.size = Pt(8)

    fld_page_begin = OxmlElement("w:fldChar")
    fld_page_begin.set(qn("w:fldCharType"), "begin")

    instr_page = OxmlElement("w:instrText")
    instr_page.set(qn("xml:space"), "preserve")
    instr_page.text = " PAGE "

    fld_page_end = OxmlElement("w:fldChar")
    fld_page_end.set(qn("w:fldCharType"), "end")

    run._r.append(fld_page_begin)
    run._r.append(instr_page)
    run._r.append(fld_page_end)

    run2 = paragraph.add_run(" de ")
    run2.font.name = "Arial"
    run2.font.size = Pt(8)

    run3 = paragraph.add_run()
    run3.font.name = "Arial"
    run3.font.size = Pt(8)

    fld_total_begin = OxmlElement("w:fldChar")
    fld_total_begin.set(qn("w:fldCharType"), "begin")

    instr_total = OxmlElement("w:instrText")
    instr_total.set(qn("xml:space"), "preserve")
    instr_total.text = " NUMPAGES "

    fld_total_end = OxmlElement("w:fldChar")
    fld_total_end.set(qn("w:fldCharType"), "end")

    run3._r.append(fld_total_begin)
    run3._r.append(instr_total)
    run3._r.append(fld_total_end)

def _configure_document(document: Document):
    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.6)
    section.left_margin = Cm(1.6)
    section.right_margin = Cm(1.6)
    section.header_distance = Cm(0.8)
    section.footer_distance = Cm(0.7)

    styles = document.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(10.5)

    for style_name in ["Title", "Subtitle", "Heading 1", "Heading 2", "Heading 3"]:
        if style_name in styles:
            styles[style_name].font.name = "Arial"

def _add_paragraph(
    document_or_cell,
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    size: int = 10,
    align=WD_ALIGN_PARAGRAPH.LEFT,
    color: str | None = None,
    space_after: int = 4,
    space_before: int = 0,
):
    p = document_or_cell.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    run = p.add_run(_safe_text(text, ""))
    run.bold = bold
    run.italic = italic
    run.underline = underline
    run.font.name = "Arial"
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    return p

def _add_divider(document):
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    p_pr = p._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "8")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)

def _add_footer_docx(document: Document, context: dict[str, Any]):
    footer_data = context["footer"]
    section = document.sections[0]
    footer = section.footer

    p1 = footer.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p1.add_run(footer_data["company_line"])
    r1.font.name = "Arial"
    r1.font.size = Pt(8)

    p2 = footer.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(footer_data["address_line"])
    r2.font.name = "Arial"
    r2.font.size = Pt(8)

    p3 = footer.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r3 = p3.add_run(footer_data["contact_line"])
    r3.font.name = "Arial"
    r3.font.size = Pt(8)

    p4 = footer.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r4 = p4.add_run(footer_data["website_line"])
    r4.font.name = "Arial"
    r4.font.size = Pt(8)
    r4.underline = True

    p5 = footer.add_paragraph()
    _add_page_number_fields(p5)

def _add_cover_docx(document: Document, context: dict[str, Any]):
    header = context["header"]
    branding = context["branding"]

    logo_path = _existing_image(header.get("logo_path"))
    if logo_path:
        p_logo = document.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p_logo.add_run()
        run.add_picture(logo_path, width=Inches(2.2))

    _add_paragraph(
        document,
        branding["report_title"],
        bold=True,
        size=16,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=2,
        space_before=2,
    )
    _add_paragraph(
        document,
        branding["report_code_display"],
        bold=True,
        size=11,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=2,
    )
    _add_paragraph(
        document,
        branding["report_subtitle"],
        bold=True,
        size=11,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=8,
    )

    _add_paragraph(
        document,
        branding["equipment_display"],
        bold=True,
        underline=True,
        size=11,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=6,
    )

    _add_paragraph(document, f"TIPO DE INSPECCIÓN: {header['inspection_type']}", bold=True, size=10, align=WD_ALIGN_PARAGRAPH.LEFT)
    _add_paragraph(document, f"FECHA DE INSPECCIÓN: {header['inspection_date']}", bold=True, size=10, align=WD_ALIGN_PARAGRAPH.LEFT)
    _add_paragraph(document, f"MÉTODOS EMPLEADOS: {header['methods_display']}", bold=True, size=10, align=WD_ALIGN_PARAGRAPH.LEFT)
    _add_paragraph(document, f"CONDICIÓN GENERAL DEL EQUIPO: {header['general_condition']}", bold=True, size=10, align=WD_ALIGN_PARAGRAPH.LEFT)

    _add_paragraph(
        document,
        _safe_text(header.get("location", ""), "").upper(),
        bold=True,
        size=10,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=10,
        space_before=10,
    )

    document.add_page_break()

def _add_technical_intro_docx(document: Document, context: dict[str, Any]):
    tech = context["technical_info"]

    _add_paragraph(document, "INFORME TÉCNICO", bold=True, underline=True, size=13, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)

    p = document.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    r1 = p.add_run("SOLICITADO POR: ")
    r1.bold = True
    r1.font.name = "Arial"
    r1.font.size = Pt(10.5)
    r2 = p.add_run(tech["requested_by"])
    r2.font.name = "Arial"
    r2.font.size = Pt(10.5)

    p = document.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    r1 = p.add_run("DIRECCIÓN: ")
    r1.bold = True
    r1.font.name = "Arial"
    r1.font.size = Pt(10.5)
    r2 = p.add_run(tech["address"])
    r2.font.name = "Arial"
    r2.font.size = Pt(10.5)

    p = document.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    r1 = p.add_run("RESPONSABLE DEL SERVICIO: ")
    r1.bold = True
    r1.font.name = "Arial"
    r1.font.size = Pt(10.5)
    r2 = p.add_run(tech["service_responsible"])
    r2.font.name = "Arial"
    r2.font.size = Pt(10.5)

    p = document.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r1 = p.add_run("FECHA DE INSPECCIÓN: ")
    r1.bold = True
    r1.font.name = "Arial"
    r1.font.size = Pt(10.5)
    r2 = p.add_run(tech["inspection_date_long"])
    r2.font.name = "Arial"
    r2.font.size = Pt(10.5)

    _add_divider(document)
    _add_paragraph(document, tech["intro_paragraph"], size=10.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=10)

def _add_heading_docx(document: Document, title: str):
    _add_paragraph(document, title, bold=True, size=11.5, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=6, space_after=6)

def _add_identification_docx(document: Document, context: dict[str, Any]):
    data = context["identification"]

    _add_heading_docx(document, "1. IDENTIFICACIÓN DEL EQUIPO INSPECCIONADO")

    lines = [
        ("Tipo de Equipo", data["tipo_equipo"]),
        ("N° de placa", data["placa"]),
        ("Marca", data["marca"]),
        ("N° de VIN", data["vin"]),
        ("Año de fabricación", data["anio_fabricacion"]),
        ("Kilometraje de Referencia", data["kilometraje"]),
        ("Antigüedad", data["antiguedad"]),
        ("N° de Ejes", data["numero_ejes"]),
        ("Carga Útil", data["carga_util"]),
        ("Peso Neto", data["peso_neto"]),
        ("Marca de King pin", data["marca_king_pin"]),
        ("Modelo de King Pin", data["modelo_king_pin"]),
        ("N° de Serie de King pin", data["serie_king_pin"]),
    ]

    for label, value in lines:
        p = document.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(f"{label}: ")
        r1.bold = True
        r1.font.name = "Arial"
        r1.font.size = Pt(10.5)
        r2 = p.add_run(_safe_text(value, "--"))
        r2.font.name = "Arial"
        r2.font.size = Pt(10.5)

def _add_bullets_docx(document: Document, items: list[str]):
    for item in items:
        p = document.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(_safe_text(item, "--"))
        run.font.name = "Arial"
        run.font.size = Pt(10.5)

def _add_frequency_table_docx(document: Document, context: dict[str, Any]):
    _add_heading_docx(document, "5. FRECUENCIA DE INSPECCIÓN")

    rows = context["frequency_table"]
    equipment_type = _safe_text(context["identification"]["tipo_equipo"], "EQUIPO").upper()

    table = document.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    headers = [equipment_type, "Método de Inspección", "Frecuencia (*)", "Porcentaje"]
    for i, text in enumerate(headers):
        cell = table.rows[0].cells[i]
        _set_cell_text(cell, text, bold=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
        _shade_cell(cell, "EDEDED")

    for row in rows:
        r = table.add_row().cells
        _set_cell_text(r[0], row["component"], size=10)
        _set_cell_text(r[1], row["method"], size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_text(r[2], row["frequency"], size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_text(r[3], row["percentage"], size=10, align=WD_ALIGN_PARAGRAPH.CENTER)

    _apply_table_borders(table)
    _add_paragraph(document, context["frequency"], size=10, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=6)

def _add_equipment_table_docx(document: Document, context: dict[str, Any]):
    _add_heading_docx(document, "7. EQUIPOS DE INSPECCIÓN EMPLEADOS")

    equipment = context["inspection_equipment"]
    mt_items = equipment["mt"]
    vt_items = equipment["vt"]
    max_rows = max(len(mt_items), len(vt_items)) + 1

    table = document.add_table(rows=max_rows, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    _set_cell_text(table.rows[0].cells[0], equipment["mt_title"], bold=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_cell_text(table.rows[0].cells[1], equipment["vt_title"], bold=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
    _shade_cell(table.rows[0].cells[0], "EDEDED")
    _shade_cell(table.rows[0].cells[1], "EDEDED")

    for i in range(max_rows - 1):
        _set_cell_text(table.rows[i + 1].cells[0], mt_items[i] if i < len(mt_items) else "", size=10)
        _set_cell_text(table.rows[i + 1].cells[1], vt_items[i] if i < len(vt_items) else "", size=10)

    _apply_table_borders(table)

def _add_criteria_docx(document: Document, context: dict[str, Any]):
    _add_heading_docx(document, "8. CRITERIOS DE INSPECCIÓN")
    criteria = context["criteria"]

    p1 = document.add_paragraph()
    p1.paragraph_format.space_after = Pt(6)
    r1 = p1.add_run("ACEPTADO: ")
    r1.bold = True
    r1.italic = True
    r1.font.name = "Arial"
    r1.font.size = Pt(10.5)
    r1.font.color.rgb = RGBColor(0x1B, 0x9E, 0x5A)
    r2 = p1.add_run(criteria["accepted"])
    r2.font.name = "Arial"
    r2.font.size = Pt(10.5)

    p2 = document.add_paragraph()
    p2.paragraph_format.space_after = Pt(4)
    r1 = p2.add_run("RECHAZADO: ")
    r1.bold = True
    r1.italic = True
    r1.font.name = "Arial"
    r1.font.size = Pt(10.5)
    r1.font.color.rgb = RGBColor(0x1F, 0x77, 0xB4)
    r2 = p2.add_run(criteria["rejected"])
    r2.font.name = "Arial"
    r2.font.size = Pt(10.5)

    for item in criteria.get("rejected_items", []):
        p = document.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(item)
        run.italic = True
        run.font.name = "Arial"
        run.font.size = Pt(10.5)

    p3 = document.add_paragraph()
    p3.paragraph_format.space_before = Pt(6)
    r1 = p3.add_run("RETIRO DE LA OPERACIÓN: ")
    r1.bold = True
    r1.italic = True
    r1.font.name = "Arial"
    r1.font.size = Pt(10.5)
    r1.font.color.rgb = RGBColor(0xD4, 0xA3, 0x00)
    r2 = p3.add_run(criteria["retirement"])
    r2.italic = True
    r2.font.name = "Arial"
    r2.font.size = Pt(10.5)

def _add_results_table_docx(document: Document, context: dict[str, Any]):
    _add_heading_docx(document, "9. RESULTADOS DE LA INSPECCIÓN")

    rows = context["results"]
    table = document.add_table(rows=1, cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    headers = ["Equipo", "Componente", "Condición", "Observaciones", "Acción Correctiva"]
    for i, text in enumerate(headers):
        cell = table.rows[0].cells[i]
        _set_cell_text(cell, text, bold=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER)
        _shade_cell(cell, "EDEDED")

    for row in rows:
        r = table.add_row().cells
        _set_cell_text(r[0], row["equipo"], size=9.5)
        _set_cell_text(r[1], row["componente"], size=9.5)
        _set_cell_text(r[2], row["condicion"], size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_text(r[3], row["observaciones"], size=9.5)
        _set_cell_text(r[4], row["accion"], size=9.5)

    _apply_table_borders(table)

def _add_evidences_docx(document: Document, context: dict[str, Any]):
    evidences = context["evidences"]
    if not evidences:
        return

    document.add_page_break()
    _add_paragraph(document, "RESULTADOS", bold=True, underline=True, size=13, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    for chunk in _chunked(evidences, 2):
        table = document.add_table(rows=2, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"

        for col_index in range(2):
            if col_index >= len(chunk):
                _set_cell_text(table.rows[0].cells[col_index], "", size=9)
                _set_cell_text(table.rows[1].cells[col_index], "", size=9)
                continue

            evidence = chunk[col_index]
            image_path = _existing_image(evidence.get("path"))
            top_cell = table.rows[0].cells[col_index]
            bottom_cell = table.rows[1].cells[col_index]

            top_cell.text = ""
            p = top_cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

            if image_path:
                run = p.add_run()
                try:
                    run.add_picture(image_path, width=Inches(2.75))
                except Exception:
                    run.add_text("[Imagen no disponible]")
            else:
                p.add_run("[Imagen no disponible]")

            caption = evidence.get("display_title") or evidence.get("caption") or f"Foto {evidence.get('index', '')}"
            _set_cell_text(bottom_cell, caption, bold=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)

        _apply_table_borders(table)
        document.add_paragraph()

def _build_docx_document(context: dict[str, Any]) -> Document:
    document = Document()
    _configure_document(document)
    _add_footer_docx(document, context)

    signature_path = _existing_image(context["technical_info"].get("signature_path"))

    _add_cover_docx(document, context)
    _add_technical_intro_docx(document, context)

    _add_identification_docx(document, context)

    _add_heading_docx(document, "2. OBJETIVO")
    _add_paragraph(document, context["objective"], size=10.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    _add_heading_docx(document, "3. ALCANCE")
    _add_bullets_docx(document, context["scope"])

    _add_heading_docx(document, "4. PROTOCOLO EMPLEADO")
    _add_paragraph(document, context["protocol"], size=10.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    _add_frequency_table_docx(document, context)

    _add_heading_docx(document, "6. NORMAS Y CÓDIGOS DE REFERENCIA")
    _add_bullets_docx(document, context["standards"])

    _add_equipment_table_docx(document, context)
    _add_criteria_docx(document, context)
    _add_results_table_docx(document, context)

    _add_heading_docx(document, "10. CONCLUSIONES")
    _add_paragraph(document, context["conclusion"], size=10.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    if signature_path:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(signature_path, width=Inches(1.8))

        _add_paragraph(
            document,
            context["technical_info"]["service_responsible"],
            bold=True,
            size=10,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            space_after=1,
        )
        _add_paragraph(
            document,
            "RESPONSABLE DEL SERVICIO",
            size=9,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            space_after=8,
        )

    _add_evidences_docx(document, context)
    return document

def _pdf_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="PdfTitleCenter",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfCodeCenter",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            alignment=TA_JUSTIFY,
            textColor=colors.black,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfBodyLeft",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfSmallCenter",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=3,
        )
    )
    return styles

def _rl_paragraph(text: str, style, *, allow_markup: bool = False):
    text = _safe_text(text, "--")
    if allow_markup:
        text = text.replace("&", "&amp;")
    else:
        text = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
    return Paragraph(text, style)

def _rl_table(data, widths, header_fill="#EDEDED", body_fill_1="#FFFFFF", body_fill_2="#F7F7F7", fontsize=8.6):
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_fill)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), fontsize),
                ("LEADING", (0, 0), (-1, -1), fontsize + 2),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor(body_fill_1), colors.HexColor(body_fill_2)]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table

def _pdf_footer(canvas, doc, context: dict[str, Any]):
    footer = context["footer"]
    width, _ = A4

    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(width / 2, 1.6 * cm, footer["company_line"])
    canvas.drawCentredString(width / 2, 1.25 * cm, footer["address_line"])
    canvas.drawCentredString(width / 2, 0.92 * cm, footer["contact_line"])
    canvas.drawCentredString(width / 2, 0.59 * cm, footer["website_line"])
    canvas.drawRightString(width - 1.6 * cm, 0.32 * cm, f"{canvas.getPageNumber()}")
    canvas.restoreState()

def _build_pdf_story(context: dict[str, Any]):
    styles = _pdf_styles()
    story = []

    header = context["header"]
    branding = context["branding"]
    tech = context["technical_info"]
    identification = context["identification"]

    signature_path = _existing_image(context["technical_info"].get("signature_path"))

    logo_path = _existing_image(header.get("logo_path"))
    if logo_path:
        story.append(RLImage(logo_path, width=4.8 * cm, height=2.1 * cm))
        story.append(Spacer(1, 0.15 * cm))

    story.append(_rl_paragraph(branding["report_title"], styles["PdfTitleCenter"]))
    story.append(_rl_paragraph(branding["report_code_display"], styles["PdfCodeCenter"]))
    story.append(_rl_paragraph(branding["report_subtitle"], styles["PdfCodeCenter"]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(_rl_paragraph(f"<u>{branding['equipment_display']}</u>", styles["PdfCodeCenter"], allow_markup=True))

    story.append(_rl_paragraph(f"<b>TIPO DE INSPECCIÓN:</b> {header['inspection_type']}", styles["PdfBodyLeft"],
                               allow_markup=True))
    story.append(_rl_paragraph(f"<b>FECHA DE INSPECCIÓN:</b> {header['inspection_date']}", styles["PdfBodyLeft"],
                               allow_markup=True))
    story.append(_rl_paragraph(f"<b>MÉTODOS EMPLEADOS:</b> {header['methods_display']}", styles["PdfBodyLeft"],
                               allow_markup=True))
    story.append(
        _rl_paragraph(f"<b>CONDICIÓN GENERAL DEL EQUIPO:</b> {header['general_condition']}", styles["PdfBodyLeft"],
                      allow_markup=True))
    story.append(Spacer(1, 0.35 * cm))
    story.append(_rl_paragraph(header["location"], styles["PdfSmallCenter"]))
    story.append(PageBreak())

    story.append(_rl_paragraph("<u><b>INFORME TÉCNICO</b></u>", styles["PdfTitleCenter"], allow_markup=True))
    story.append(
        _rl_paragraph(f"<b>SOLICITADO POR:</b> {tech['requested_by']}", styles["PdfBodyLeft"], allow_markup=True))
    story.append(_rl_paragraph(f"<b>DIRECCIÓN:</b> {tech['address']}", styles["PdfBodyLeft"], allow_markup=True))
    story.append(_rl_paragraph(f"<b>RESPONSABLE DEL SERVICIO:</b> {tech['service_responsible']}", styles["PdfBodyLeft"],
                               allow_markup=True))
    story.append(_rl_paragraph(f"<b>FECHA DE INSPECCIÓN:</b> {tech['inspection_date_long']}", styles["PdfBodyLeft"],
                               allow_markup=True))
    story.append(Spacer(1, 0.1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.7, color=colors.black))
    story.append(Spacer(1, 0.15 * cm))
    story.append(_rl_paragraph(tech["intro_paragraph"], styles["PdfBody"]))

    story.append(_rl_paragraph("1. IDENTIFICACIÓN DEL EQUIPO INSPECCIONADO", styles["PdfSection"]))
    ident_lines = [
        f"<b>Tipo de Equipo:</b> {identification['tipo_equipo']}",
        f"<b>N° de placa:</b> {identification['placa']}",
        f"<b>Marca:</b> {identification['marca']}",
        f"<b>N° de VIN:</b> {identification['vin']}",
        f"<b>Año de fabricación:</b> {identification['anio_fabricacion']}",
        f"<b>Kilometraje de Referencia:</b> {identification['kilometraje']}",
        f"<b>Antigüedad:</b> {identification['antiguedad']}",
        f"<b>N° de Ejes:</b> {identification['numero_ejes']}",
        f"<b>Carga Útil:</b> {identification['carga_util']}",
        f"<b>Peso Neto:</b> {identification['peso_neto']}",
        f"<b>Marca de King pin:</b> {identification['marca_king_pin']}",
        f"<b>Modelo de King Pin:</b> {identification['modelo_king_pin']}",
        f"<b>N° de Serie de King pin:</b> {identification['serie_king_pin']}",
    ]
    for line in ident_lines:
        story.append(_rl_paragraph(line, styles["PdfBodyLeft"], allow_markup=True))

    story.append(_rl_paragraph("2. OBJETIVO", styles["PdfSection"]))
    story.append(_rl_paragraph(context["objective"], styles["PdfBody"]))

    story.append(_rl_paragraph("3. ALCANCE", styles["PdfSection"]))
    for item in context["scope"]:
        story.append(_rl_paragraph(f"- {item}", styles["PdfBodyLeft"]))

    story.append(_rl_paragraph("4. PROTOCOLO EMPLEADO", styles["PdfSection"]))
    story.append(_rl_paragraph(context["protocol"], styles["PdfBody"]))

    story.append(_rl_paragraph("5. FRECUENCIA DE INSPECCIÓN", styles["PdfSection"]))
    freq_data = [[
        _safe_text(context["identification"]["tipo_equipo"], "EQUIPO").upper(),
        "Método de Inspección",
        "Frecuencia (*)",
        "Porcentaje",
    ]]
    for row in context["frequency_table"]:
        freq_data.append([row["component"], row["method"], row["frequency"], row["percentage"]])

    story.append(_rl_table(freq_data, [5.8 * cm, 4.4 * cm, 3.4 * cm, 2.8 * cm], fontsize=8.3))
    story.append(Spacer(1, 0.12 * cm))
    story.append(_rl_paragraph(context["frequency"], styles["PdfBody"]))

    story.append(_rl_paragraph("6. NORMAS Y CÓDIGOS DE REFERENCIA", styles["PdfSection"]))
    for item in context["standards"]:
        story.append(_rl_paragraph(f"• {item}", styles["PdfBodyLeft"]))

    story.append(_rl_paragraph("7. EQUIPOS DE INSPECCIÓN EMPLEADOS", styles["PdfSection"]))
    equipment = context["inspection_equipment"]
    max_rows = max(len(equipment["mt"]), len(equipment["vt"]))
    eq_data = [[equipment["mt_title"], equipment["vt_title"]]]
    for i in range(max_rows):
        eq_data.append([
            equipment["mt"][i] if i < len(equipment["mt"]) else "",
            equipment["vt"][i] if i < len(equipment["vt"]) else "",
        ])
    story.append(_rl_table(eq_data, [8.0 * cm, 8.0 * cm], fontsize=8.5))

    story.append(_rl_paragraph("8. CRITERIOS DE INSPECCIÓN", styles["PdfSection"]))
    criteria = context["criteria"]
    story.append(_rl_paragraph(
        f"<font color='#1B9E5A'><b><i>ACEPTADO:</i></b></font> {criteria['accepted']}",
        styles["PdfBodyLeft"],
        allow_markup=True,
    ))
    story.append(_rl_paragraph(
        f"<font color='#1F77B4'><b><i>RECHAZADO:</i></b></font> {criteria['rejected']}",
        styles["PdfBodyLeft"],
        allow_markup=True,
    ))
    for item in criteria.get("rejected_items", []):
        story.append(_rl_paragraph(f"• <i>{item}</i>", styles["PdfBodyLeft"], allow_markup=True))
    story.append(_rl_paragraph(
        f"<font color='#D4A300'><b><i>RETIRO DE LA OPERACIÓN:</i></b></font> <i>{criteria['retirement']}</i>",
        styles["PdfBodyLeft"],
        allow_markup=True,
    ))

    story.append(_rl_paragraph("9. RESULTADOS DE LA INSPECCIÓN", styles["PdfSection"]))
    results_data = [["Equipo", "Componente", "Condición", "Observaciones", "Acción Correctiva"]]
    for row in context["results"]:
        results_data.append([
            row["equipo"],
            row["componente"],
            row["condicion"],
            row["observaciones"],
            row["accion"],
        ])
    story.append(_rl_table(results_data, [3.0 * cm, 3.8 * cm, 2.2 * cm, 4.0 * cm, 3.0 * cm], fontsize=7.8))

    story.append(_rl_paragraph("10. CONCLUSIONES", styles["PdfSection"]))
    story.append(_rl_paragraph(context["conclusion"], styles["PdfBody"]))

    if signature_path:
        story.append(Spacer(1, 0.4 * cm))
        story.append(RLImage(signature_path, width=4.0 * cm, height=2.0 * cm))
        story.append(_rl_paragraph(f"<b>{tech['service_responsible']}</b>", styles["PdfSmallCenter"], allow_markup=True))
        story.append(_rl_paragraph("RESPONSABLE DEL SERVICIO", styles["PdfSmallCenter"]))

    evidences = context["evidences"]
    if evidences:
        story.append(PageBreak())
        story.append(_rl_paragraph("<u><b>RESULTADOS</b></u>", styles["PdfTitleCenter"], allow_markup=True))

        for chunk in _chunked(evidences, 2):
            block = []
            image_row = []
            caption_row = []

            for evidence in chunk:
                img_path = _existing_image(evidence.get("path"))
                if img_path:
                    image_row.append(RLImage(img_path, width=7.3 * cm, height=5.2 * cm))
                else:
                    image_row.append(_rl_paragraph("Imagen no disponible", styles["PdfSmallCenter"]))

                caption = evidence.get("display_title") or evidence.get("caption") or f"Foto {evidence.get('index', '')}"
                caption_row.append(_rl_paragraph(f"<b>{caption}</b>", styles["PdfSmallCenter"], allow_markup=True))

            if len(image_row) == 1:
                image_row.append("")
                caption_row.append("")

            table = Table([image_row, caption_row], colWidths=[8.0 * cm, 8.0 * cm])
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(KeepTogether([table, Spacer(1, 0.2 * cm)]))

    return story

def export_report_docx(db: Session, draft_id: int, output_path: str | Path | None = None) -> str:
    context = build_company_report_context(db, draft_id)

    if output_path is None:
        report_code = _normalize_filename(context["header"]["report_code_display"])
        output_path = OUTPUT_DIR / f"{report_code}.docx"

    output_path = _ensure_parent(Path(output_path))
    document = _build_docx_document(context)
    document.save(str(output_path))
    return str(output_path)

def export_report_pdf(db: Session, draft_id: int, output_path: str | Path | None = None) -> str:
    context = build_company_report_context(db, draft_id)

    if output_path is None:
        report_code = _normalize_filename(context["header"]["report_code_display"])
        output_path = OUTPUT_DIR / f"{report_code}.pdf"

    output_path = _ensure_parent(Path(output_path))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2.0 * cm,
        title=context["header"]["report_title"],
        author=context["company"]["name"],
    )

    story = _build_pdf_story(context)
    doc.build(
        story,
        onFirstPage=lambda canvas, d: _pdf_footer(canvas, d, context),
        onLaterPages=lambda canvas, d: _pdf_footer(canvas, d, context),
    )
    return str(output_path)

def export_report_files(db: Session, draft_id: int, output_dir: str | Path | None = None) -> dict[str, str]:
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    context = build_company_report_context(db, draft_id)
    report_code = _normalize_filename(context["header"]["report_code_display"])

    docx_path = output_dir / f"{report_code}.docx"
    pdf_path = output_dir / f"{report_code}.pdf"

    export_report_docx(db, draft_id, docx_path)
    export_report_pdf(db, draft_id, pdf_path)

    return {
        "docx": str(docx_path),
        "pdf": str(pdf_path),
    }