import json
from time import perf_counter

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import Inspection, Transcription, ReportDraft
from app.services.report_status_service import register_report_event

class DraftSections(BaseModel):
    summary: str = Field(description="Resumen ejecutivo en un párrafo")
    findings: str = Field(description="Hallazgos principales redactados")
    recommendations: str = Field(description="Recomendaciones técnicas concretas")
    conclusion: str = Field(description="Conclusión preliminar del borrador")
    final_report: str = Field(description="Informe técnico completo redactado en varios párrafos")

SECTION_FALLBACKS = {
    "summary": (
        "No fue posible construir un resumen ejecutivo completo con la información disponible. "
        "Se recomienda revisión humana del borrador."
    ),
    "findings": (
        "No se identificaron hallazgos suficientemente sustentados con la información disponible."
    ),
    "recommendations": (
        "No se identifican recomendaciones técnicas adicionales con la información disponible."
    ),
    "conclusion": (
        "No fue posible elaborar una conclusión amplia con consistencia suficiente; "
        "se recomienda revisión humana del borrador."
    ),
    "final_report": (
        "No fue posible redactar el informe completo con consistencia suficiente; "
        "se recomienda revisión humana del borrador."
    ),
}

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

def _normalize_llm_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()

def _coalesce_llm_section(key: str, value) -> str:
    normalized = _normalize_llm_text(value)
    return normalized or SECTION_FALLBACKS[key]

def _build_general_section(inspection) -> str:
    lines = [
        f"Identificador de inspección: {_pick_attr(inspection, ['inspection_code', 'code', 'identifier', 'inspection_number', 'id'])}",
        f"Cliente: {_pick_attr(inspection, ['client_name', 'customer_name', 'client'])}",
        f"Equipo: {_pick_attr(inspection, ['equipment_name', 'equipment', 'asset_name', 'equipment_type'])}",
        f"Tipo de equipo: {_pick_attr(inspection, ['equipment_type', 'equipment_name', 'equipment'])}",
        f"Fecha de inspección: {_pick_attr(inspection, ['inspection_date', 'date', 'scheduled_at'])}",
        f"Inspector responsable: {_pick_attr(inspection, ['responsible_inspector', 'inspector_name', 'inspector', 'created_by'])}",
        f"Tipo de servicio: {_pick_attr(inspection, ['service_type', 'inspection_type', 'service'])}",
        f"Ubicación: {_pick_attr(inspection, ['location'])}",
        f"Solicitado por: {_pick_attr(inspection, ['requested_by', 'client_name'])}",
        f"Estado: {_pick_attr(inspection, ['status'])}",
    ]
    return "\n".join(lines)

def _build_fields_section(fields) -> str:
    if not fields:
        return "No se registraron campos estructurados para esta inspección."

    lines = []
    for field in fields:
        label = _safe(getattr(field, "field_label", None), getattr(field, "field_key", "Campo"))
        group = _safe(getattr(field, "field_group", None), "Sin grupo")
        expected_type = _safe(getattr(field, "expected_type", None), "Sin tipo")
        value = _field_value(field)
        lines.append(f"- [{group}] {label}: {value} (tipo esperado: {expected_type})")
    return "\n".join(lines)

def _build_critical_section(fields) -> str:
    if not fields:
        return "No se identificaron campos críticos."

    critical_keywords = (
        "vin", "placa", "plate", "serie", "serial", "motor", "chasis",
        "codigo", "code", "king", "eje"
    )
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
    pending = 0

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
        else:
            pending += 1

        lines.append(
            f"- {label}: manual='{manual_value}' | ocr='{ocr_value}' | estado='{status}' | detalle='{message}'"
        )

    summary = [
        f"Coincidencias: {matched}",
        f"Discrepancias: {mismatched}",
        f"No detectados: {not_found}",
        f"Pendientes/no evaluados: {pending}",
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
        language = _safe(getattr(item, "language", None))
        model_name = _safe(getattr(item, "model_name", None))
        confidence = getattr(item, "confidence", None)
        confidence_text = f" | confianza={confidence}" if confidence is not None else ""

        blocks.append(
            "\n".join([
                f"Transcripción {idx} | idioma={language} | modelo={model_name}{confidence_text}",
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
        ocr_text = _safe(getattr(item, "ocr_extracted_text", None), "Sin OCR")
        ocr_processed = bool(getattr(item, "ocr_processed", False))
        lines.append(
            f"- [{category}] {caption} | tipo={file_type} | ruta={file_path} | ocr_procesado={ocr_processed} | ocr='{ocr_text}'"
        )
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
                "field_group": getattr(field, "field_group", None),
                "expected_type": getattr(field, "expected_type", None),
                "manual_value": getattr(field, "manual_value", None),
                "ocr_value": getattr(field, "ocr_value", None),
                "final_value": getattr(field, "final_value", None),
                "validation_status": getattr(field, "validation_status", None),
                "validation_message": getattr(field, "validation_message", None),
                "confidence": float(field.confidence) if getattr(field, "confidence", None) is not None else None,
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
                "raw_label": getattr(evidence, "raw_label", None),
                "normalized_label": getattr(evidence, "normalized_label", None),
                "evidence_slot": getattr(evidence, "evidence_slot", None),
                "component_code": getattr(evidence, "component_code", None),
                "axle_number": getattr(evidence, "axle_number", None),
                "side": getattr(evidence, "side", None),
                "is_reference": getattr(evidence, "is_reference", False),
                "ocr_extracted_text": getattr(evidence, "ocr_extracted_text", None),
                "ocr_confidence": float(evidence.ocr_confidence)
                if getattr(evidence, "ocr_confidence", None) is not None
                else None,
                "ocr_processed": bool(getattr(evidence, "ocr_processed", False)),
            }
        )

    transcription_items = []
    for transcription in transcriptions:
        transcription_items.append(
            {
                "transcription_id": transcription.id,
                "source_file_path": getattr(transcription, "source_file_path", None),
                "language": getattr(transcription, "language", None),
                "model_name": getattr(transcription, "model_name", None),
                "raw_text": getattr(transcription, "raw_text", None),
                "final_text": getattr(transcription, "final_text", None),
                "confidence": float(transcription.confidence) if transcription.confidence is not None else None,
                "processed": bool(getattr(transcription, "processed", False)),
                "edited_manually": bool(getattr(transcription, "edited_manually", False)),
            }
        )

    return {
        "inspection_id": inspection.id,
        "general_data": {
            "inspection_code": _pick_attr(inspection, ['inspection_code', 'code', 'identifier', 'inspection_number', 'id']),
            "client_name": _pick_attr(inspection, ['client_name', 'customer_name', 'client']),
            "equipment_name": _pick_attr(inspection, ['equipment_name', 'equipment', 'asset_name', 'equipment_type']),
            "equipment_type": _pick_attr(inspection, ['equipment_type', 'equipment_name', 'equipment']),
            "inspection_date": _pick_attr(inspection, ['inspection_date', 'date', 'scheduled_at']),
            "inspector_name": _pick_attr(inspection, ['responsible_inspector', 'inspector_name', 'inspector', 'created_by']),
            "service_type": _pick_attr(inspection, ['service_type', 'inspection_type', 'service']),
            "location": _pick_attr(inspection, ['location']),
            "requested_by": _pick_attr(inspection, ['requested_by', 'client_name']),
            "status": _pick_attr(inspection, ['status']),
        },
        "fields": fields,
        "evidences": evidences,
        "transcriptions": transcription_items,
    }

def _get_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout,
    )

def _generate_llama_sections(
    *,
    template_version: str,
    snapshot: dict,
    general_section: str,
    critical_section: str,
    fields_section: str,
    evidence_section: str,
    ocr_section: str,
    transcription_section: str,
    deterministic_conclusion: str,
) -> dict:
    llm = _get_llm()
    structured_llm = llm.with_structured_output(DraftSections)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Eres un ingeniero redactor de informes de inspección industrial. "
                    "Redacta en español técnico, claro y profesional. "
                    "No inventes datos. Si falta información, dilo de forma explícita. "
                    "Debes responder ajustándote exactamente al esquema estructurado solicitado. "
                    "No agregues datos no presentes en la inspección, OCR, evidencias o transcripciones. "
                    "Mantén consistencia técnica y terminología formal. "
                    "Ningún campo debe quedar vacío. "
                    "Si no hubiera suficiente sustento para recomendaciones, escribe exactamente: "
                    "'No se identifican recomendaciones técnicas adicionales con la información disponible.'. "
                    "Si faltara información para alguna otra sección, redacta una salida breve y explícita, "
                    "pero nunca devuelvas cadenas vacías."
                ),
            ),
            (
                "human",
                (
                    "Versión de plantilla: {template_version}\n\n"
                    "DATOS GENERALES:\n{general_section}\n\n"
                    "CAMPOS CRÍTICOS:\n{critical_section}\n\n"
                    "DATOS CAPTURADOS:\n{fields_section}\n\n"
                    "EVIDENCIAS:\n{evidence_section}\n\n"
                    "VALIDACIÓN OCR:\n{ocr_section}\n\n"
                    "OBSERVACIONES TRANSCRITAS:\n{transcription_section}\n\n"
                    "CONCLUSIÓN DETERMINÍSTICA DE APOYO:\n{deterministic_conclusion}\n\n"
                    "SNAPSHOT JSON:\n{snapshot_json}"
                ),
            ),
        ]
    )

    chain = prompt | structured_llm
    result = chain.invoke(
        {
            "template_version": template_version,
            "general_section": general_section,
            "critical_section": critical_section,
            "fields_section": fields_section,
            "evidence_section": evidence_section,
            "ocr_section": ocr_section,
            "transcription_section": transcription_section,
            "deterministic_conclusion": deterministic_conclusion,
            "snapshot_json": json.dumps(snapshot, ensure_ascii=False, indent=2),
        }
    )

    normalized = {
        "summary": _coalesce_llm_section("summary", getattr(result, "summary", None)),
        "findings": _coalesce_llm_section("findings", getattr(result, "findings", None)),
        "recommendations": _coalesce_llm_section("recommendations", getattr(result, "recommendations", None)),
        "conclusion": _coalesce_llm_section("conclusion", getattr(result, "conclusion", None)),
        "final_report": _coalesce_llm_section("final_report", getattr(result, "final_report", None)),
    }

    return normalized

def _render_template(inspection, transcriptions, template_version: str) -> tuple[str, dict]:
    fields = getattr(inspection, "fields", []) or []
    evidences = getattr(inspection, "evidences", []) or []

    general_section = _build_general_section(inspection)
    critical_section = _build_critical_section(fields)
    fields_section = _build_fields_section(fields)
    evidence_section = _build_evidence_section(evidences)
    ocr_section = _build_ocr_section(fields)
    transcription_section = _build_transcription_section(transcriptions)
    deterministic_conclusion = _build_conclusion(fields, transcriptions)

    snapshot = _build_snapshot(inspection, transcriptions)

    ai_sections = _generate_llama_sections(
        template_version=template_version,
        snapshot=snapshot,
        general_section=general_section,
        critical_section=critical_section,
        fields_section=fields_section,
        evidence_section=evidence_section,
        ocr_section=ocr_section,
        transcription_section=transcription_section,
        deterministic_conclusion=deterministic_conclusion,
    )

    snapshot["llm"] = {
        "provider": "ollama",
        "model": settings.ollama_model,
        "base_url": settings.ollama_base_url,
        "temperature": settings.llm_temperature,
        "sections": ai_sections,
    }

    sections = [
        "INFORME DE INSPECCIÓN - BORRADOR AUTOMÁTICO",
        f"Versión de plantilla: {template_version}",
        f"Modelo LLM: {snapshot['llm']['model']}",
        "",
        "1. RESUMEN EJECUTIVO",
        ai_sections["summary"],
        "",
        "2. CONTEXTO DE LA INSPECCIÓN",
        general_section,
        "",
        "Campos críticos identificados:",
        critical_section,
        "",
        "3. HALLAZGOS PRINCIPALES",
        ai_sections["findings"],
        "",
        "4. VALIDACIÓN OCR",
        ocr_section,
        "",
        "5. OBSERVACIONES TRANSCRITAS",
        transcription_section,
        "",
        "6. RECOMENDACIONES",
        ai_sections["recommendations"],
        "",
        "7. INFORME REDACTADO",
        ai_sections["final_report"],
        "",
        "8. CONCLUSIÓN PRELIMINAR",
        ai_sections["conclusion"],
        "",
        "ANEXO TÉCNICO - DATOS CAPTURADOS",
        fields_section,
        "",
        "ANEXO TÉCNICO - EVIDENCIAS",
        evidence_section,
    ]

    return "\n".join(sections).strip(), snapshot


def generate_report_draft(
    db: Session,
    inspection_id: int,
    template_version: str = "v1",
    user_id: int | None = None,
    user_name: str | None = None,
) -> ReportDraft:
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
        last_action="draft_generated",
    )

    db.add(draft)
    db.flush()

    register_report_event(
        db=db,
        report_draft=draft,
        action="draft_created",
        actor_user_id=user_id,
        actor_name=user_name,
        to_status=draft.status,
        metadata_json={"template_version": template_version},
    )

    register_report_event(
        db=db,
        report_draft=draft,
        action="draft_generated",
        actor_user_id=user_id,
        actor_name=user_name,
        from_status=draft.status,
        to_status=draft.status,
        metadata_json={
            "has_generated_text": bool(draft.generated_text),
            "generation_time_ms": elapsed_ms,
            "template_version": template_version,
        },
    )

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


def update_report_draft(
    db: Session,
    draft_id: int,
    edited_text: str,
    status: str = "edited",
    user_id: int | None = None,
    user_name: str | None = None,
) -> ReportDraft | None:
    draft = db.query(ReportDraft).filter(ReportDraft.id == draft_id).first()
    if not draft:
        return None

    previous_status = draft.status
    draft.edited_text = edited_text
    draft.status = status
    draft.last_action = "draft_edited"

    register_report_event(
        db=db,
        report_draft=draft,
        action="draft_edited",
        actor_user_id=user_id,
        actor_name=user_name,
        from_status=previous_status,
        to_status=draft.status,
        metadata_json={"has_edited_text": bool(draft.edited_text)},
    )

    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft