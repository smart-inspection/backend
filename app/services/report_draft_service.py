from time import perf_counter
from pathlib import Path

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, Transcription, ReportDraft


def _safe(value, default="No registrado"):
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    return str(value)


def _pick_attr(obj, candidates, default="No registrado"):
    for name in candidates:
        value = getattr(obj, name, None)
        if value is not None and str(value).strip() != "":
            return str(value)
    return default


def _field_value(field):
    for attr in ("final_value", "manual_value", "ocr_value"):
        value = getattr(field, attr, None)
        if value is not None and str(value).strip() != "":
            return str(value)
    return "No registrado"


def _build_general_section(inspection) -> str:
    lines = [
        f"Identificador de inspección: {_pick_attr(inspection, ['inspection_code', 'code', 'identifier', 'inspection_number', 'id'])}",
        f"Cliente: {_pick_attr(inspection, ['client_name', 'customer_name', 'client'])}",
        f"Equipo: {_pick_attr(inspection, ['equipment_name', 'equipment', 'asset_name'])}",
        f"Fecha de inspección: {_pick_attr(inspection, ['inspection_date', 'date', 'scheduled_at'])}",
        f"Inspector responsable: {_pick_attr(inspection, ['inspector_name', 'inspector', 'created_by'])}",
        f"Tipo de servicio: {_pick_attr(inspection, ['service_type', 'inspection_type', 'service'])}",
    ]
    return "\n".join(lines)


def _build_fields_section(fields) -> str:
    if not fields:
        return "No se registraron campos estructurados para esta inspección."

    lines = []
    for field in fields:
        label = _safe(getattr(field, "field_label", None), getattr(field, "field_key", "Campo"))
        value = _field_value(field)
        lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def _build_critical_section(fields) -> str:
    if not fields:
        return "No se identificaron campos críticos."

    critical_keywords = ("vin", "placa", "plate", "serie", "serial", "motor", "chasis")
    lines = []

    for field in fields:
        key = _safe(getattr(field, "field_key", ""), "").lower()
        label = _safe(getattr(field, "field_label", None), getattr(field, "field_key", "Campo"))
        if any(word in key for word in critical_keywords):
            lines.append(f"- {label}: {_field_value(field)}")

    return "\n".join(lines) if lines else "No se registraron campos críticos identificables."


def _build_ocr_section(fields) -> str:
    if not fields:
        return "No hay resultados OCR asociados."

    lines = []
    matched = 0
    mismatched = 0
    not_found = 0

    for field in fields:
        status = _safe(getattr(field, "validation_status", None), "not_evaluated")
        label = _safe(getattr(field, "field_label", None), getattr(field, "field_key", "Campo"))
        manual_value = _safe(getattr(field, "manual_value", None))
        ocr_value = _safe(getattr(field, "ocr_value", None))
        message = _safe(getattr(field, "validation_message", None), "Sin observación")

        if status == "matched":
            matched += 1
        elif status == "mismatch":
            mismatched += 1
        elif status == "not_found":
            not_found += 1

        lines.append(
            f"- {label}: manual='{manual_value}' | ocr='{ocr_value}' | estado='{status}' | detalle='{message}'"
        )

    summary = [
        f"Coincidencias: {matched}",
        f"Discrepancias: {mismatched}",
        f"No detectados: {not_found}",
        "",
        *lines,
    ]
    return "\n".join(summary)


def _build_transcription_section(transcriptions) -> str:
    if not transcriptions:
        return "No se registraron transcripciones asociadas."

    blocks = []
    for idx, item in enumerate(transcriptions, start=1):
        text = item.final_text or item.raw_text or "Sin contenido"
        blocks.append(
            "\n".join([
                f"Transcripción {idx}:",
                text.strip(),
            ])
        )
    return "\n\n".join(blocks)


def _build_evidence_section(evidences) -> str:
    if not evidences:
        return "No se registraron evidencias asociadas."

    lines = []
    for item in evidences:
        category = _safe(getattr(item, "evidence_category", None), "Sin categoría")
        file_type = _safe(getattr(item, "file_type", None), "Sin tipo")
        file_path = _safe(getattr(item, "file_path", None), "Sin ruta")
        caption = _safe(getattr(item, "caption", None), "Sin descripción")
        lines.append(f"- [{category}] {caption} | tipo={file_type} | ruta={file_path}")
    return "\n".join(lines)


def _build_conclusion(fields, transcriptions) -> str:
    mismatches = 0
    for field in fields or []:
        if getattr(field, "validation_status", None) == "mismatch":
            mismatches += 1

    has_transcription = bool(transcriptions)

    if mismatches > 0 and has_transcription:
        return (
            "El borrador se generó con información estructurada, resultados OCR y observaciones transcritas. "
            "Se identificaron discrepancias en algunos campos críticos, por lo que se recomienda revisión humana "
            "antes de la validación final del informe."
        )

    if mismatches > 0:
        return (
            "El borrador se generó con información estructurada y validación OCR. "
            "Se detectaron discrepancias en campos críticos, por lo que debe revisarse antes de su aprobación."
        )

    if has_transcription:
        return (
            "El borrador se generó con datos estructurados, resultados OCR disponibles y observaciones transcritas. "
            "No se identificaron discrepancias relevantes en los campos comparados."
        )

    return (
        "El borrador se generó con la información disponible en la inspección. "
        "Se recomienda complementar observaciones de campo o transcripción si se requiere mayor detalle."
    )


def _build_snapshot(inspection, transcriptions) -> dict:
    fields = []
    for field in getattr(inspection, "fields", []) or []:
        fields.append(
            {
                "field_id": getattr(field, "id", None),
                "field_key": getattr(field, "field_key", None),
                "field_label": getattr(field, "field_label", None),
                "manual_value": getattr(field, "manual_value", None),
                "ocr_value": getattr(field, "ocr_value", None),
                "final_value": getattr(field, "final_value", None),
                "validation_status": getattr(field, "validation_status", None),
                "validation_message": getattr(field, "validation_message", None),
            }
        )

    evidences = []
    for evidence in getattr(inspection, "evidences", []) or []:
        evidences.append(
            {
                "evidence_id": getattr(evidence, "id", None),
                "file_path": getattr(evidence, "file_path", None),
                "file_type": getattr(evidence, "file_type", None),
                "evidence_category": getattr(evidence, "evidence_category", None),
                "caption": getattr(evidence, "caption", None),
            }
        )

    transcription_items = []
    for transcription in transcriptions:
        transcription_items.append(
            {
                "transcription_id": transcription.id,
                "source_file_path": transcription.source_file_path,
                "language": transcription.language,
                "raw_text": transcription.raw_text,
                "final_text": transcription.final_text,
                "confidence": float(transcription.confidence) if transcription.confidence is not None else None,
            }
        )

    return {
        "inspection_id": inspection.id,
        "general_data": {
            "inspection_code": _pick_attr(inspection, ['inspection_code', 'code', 'identifier', 'inspection_number', 'id']),
            "client_name": _pick_attr(inspection, ['client_name', 'customer_name', 'client']),
            "equipment_name": _pick_attr(inspection, ['equipment_name', 'equipment', 'asset_name']),
            "inspection_date": _pick_attr(inspection, ['inspection_date', 'date', 'scheduled_at']),
            "inspector_name": _pick_attr(inspection, ['inspector_name', 'inspector', 'created_by']),
            "service_type": _pick_attr(inspection, ['service_type', 'inspection_type', 'service']),
        },
        "fields": fields,
        "evidences": evidences,
        "transcriptions": transcription_items,
    }


def _render_template(inspection, transcriptions, template_version: str) -> tuple[str, dict]:
    fields = getattr(inspection, "fields", []) or []
    evidences = getattr(inspection, "evidences", []) or []

    sections = [
        "INFORME DE INSPECCIÓN - BORRADOR AUTOMÁTICO",
        f"Versión de plantilla: {template_version}",
        "",
        "1. DATOS GENERALES",
        _build_general_section(inspection),
        "",
        "2. IDENTIFICACIÓN DE CAMPOS CRÍTICOS",
        _build_critical_section(fields),
        "",
        "3. DATOS CAPTURADOS EN INSPECCIÓN",
        _build_fields_section(fields),
        "",
        "4. EVIDENCIAS REGISTRADAS",
        _build_evidence_section(evidences),
        "",
        "5. VALIDACIÓN OCR",
        _build_ocr_section(fields),
        "",
        "6. OBSERVACIONES TRANSCRITAS",
        _build_transcription_section(transcriptions),
        "",
        "7. CONCLUSIÓN PRELIMINAR",
        _build_conclusion(fields, transcriptions),
    ]

    snapshot = _build_snapshot(inspection, transcriptions)
    return "\n".join(sections).strip(), snapshot


def generate_report_draft(db: Session, inspection_id: int, template_version: str = "v1") -> ReportDraft:
    started = perf_counter()

    inspection = (
        db.query(Inspection)
        .options(
            selectinload(Inspection.fields),
            selectinload(Inspection.evidences),
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )

    if not inspection:
        raise ValueError("Inspection not found")

    transcriptions = (
        db.query(Transcription)
        .filter(Transcription.inspection_id == inspection_id)
        .order_by(Transcription.id.asc())
        .all()
    )

    generated_text, snapshot = _render_template(inspection, transcriptions, template_version)
    elapsed_ms = int((perf_counter() - started) * 1000)

    draft = ReportDraft(
        inspection_id=inspection.id,
        title=f"Borrador de informe - Inspección {inspection.id}",
        template_version=template_version,
        status="generated",
        generated_text=generated_text,
        edited_text=None,
        source_snapshot=snapshot,
        generation_time_ms=elapsed_ms,
    )

    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def get_report_draft_by_id(db: Session, draft_id: int) -> ReportDraft | None:
    return db.query(ReportDraft).filter(ReportDraft.id == draft_id).first()


def list_report_drafts_by_inspection(db: Session, inspection_id: int) -> list[ReportDraft]:
    return (
        db.query(ReportDraft)
        .filter(ReportDraft.inspection_id == inspection_id)
        .order_by(ReportDraft.id.desc())
        .all()
    )


def update_report_draft(db: Session, draft_id: int, edited_text: str, status: str = "edited") -> ReportDraft | None:
    draft = db.query(ReportDraft).filter(ReportDraft.id == draft_id).first()
    if not draft:
        return None

    draft.edited_text = edited_text
    draft.status = status

    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
