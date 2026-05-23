from time import perf_counter

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.core.config import settings
from app.db.models import Inspection, ReportDraft, Transcription


class LLMReportSections(BaseModel):
    title: str = Field(description="Título del informe")
    executive_summary: str = Field(description="Resumen ejecutivo breve")
    inspection_context: str = Field(description="Contexto de la inspección")
    key_findings: list[str] = Field(description="Hallazgos principales")
    ocr_validation_summary: str = Field(description="Resumen de validación OCR")
    voice_observations: str = Field(description="Resumen de observaciones por voz")
    recommendations: list[str] = Field(description="Recomendaciones técnicas")
    final_report: str = Field(description="Informe final redactado en español formal")


def _safe(value, default="No registrado"):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _pick_attr(obj, candidates, default="No registrado"):
    for name in candidates:
        value = getattr(obj, name, None)
        if value is not None and str(value).strip():
            return str(value)
    return default


def _field_value(field):
    for attr in ("final_value", "manual_value", "ocr_value"):
        value = getattr(field, attr, None)
        if value is not None and str(value).strip():
            return str(value)
    return "No registrado"


def _build_snapshot(inspection, transcriptions):
    fields_payload = []
    for field in getattr(inspection, "fields", []) or []:
        fields_payload.append(
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

    evidences_payload = []
    for evidence in getattr(inspection, "evidences", []) or []:
        evidences_payload.append(
            {
                "evidence_id": getattr(evidence, "id", None),
                "file_path": getattr(evidence, "file_path", None),
                "file_type": getattr(evidence, "file_type", None),
                "evidence_category": getattr(evidence, "evidence_category", None),
                "caption": getattr(evidence, "caption", None),
                "ocr_extracted_text": getattr(evidence, "ocr_extracted_text", None),
                "ocr_confidence": float(evidence.ocr_confidence) if getattr(evidence, "ocr_confidence", None) is not None else None,
            }
        )

    transcriptions_payload = []
    for item in transcriptions:
        transcriptions_payload.append(
            {
                "transcription_id": item.id,
                "source_file_path": item.source_file_path,
                "language": item.language,
                "raw_text": item.raw_text,
                "final_text": item.final_text,
                "confidence": float(item.confidence) if item.confidence is not None else None,
            }
        )

    return {
        "inspection_id": inspection.id,
        "general_data": {
            "inspection_code": _pick_attr(inspection, ["inspection_code", "code", "identifier", "inspection_number", "id"]),
            "client_name": _pick_attr(inspection, ["client_name", "customer_name", "client"]),
            "equipment_name": _pick_attr(inspection, ["equipment_name", "equipment", "asset_name"]),
            "inspection_date": _pick_attr(inspection, ["inspection_date", "date", "scheduled_at"]),
            "inspector_name": _pick_attr(inspection, ["inspector_name", "inspector", "created_by"]),
            "service_type": _pick_attr(inspection, ["service_type", "inspection_type", "service"]),
        },
        "fields": fields_payload,
        "evidences": evidences_payload,
        "transcriptions": transcriptions_payload,
    }


def _format_input_context(snapshot: dict) -> str:
    general = snapshot["general_data"]

    fields_text = "\n".join(
        [
            f"- {item.get('field_label') or item.get('field_key')}: "
            f"valor_final={item.get('final_value') or item.get('manual_value') or item.get('ocr_value') or 'No registrado'} | "
            f"ocr={item.get('ocr_value') or 'No registrado'} | "
            f"estado_validacion={item.get('validation_status') or 'not_evaluated'} | "
            f"detalle={item.get('validation_message') or 'Sin detalle'}"
            for item in snapshot["fields"]
        ]
    ) or "No hay campos registrados."

    evidences_text = "\n".join(
        [
            f"- categoria={item.get('evidence_category') or 'Sin categoría'} | "
            f"tipo={item.get('file_type') or 'Sin tipo'} | "
            f"descripcion={item.get('caption') or 'Sin descripción'}"
            for item in snapshot["evidences"]
        ]
    ) or "No hay evidencias registradas."

    transcriptions_text = "\n\n".join(
        [
            f"Transcripción {idx}:\n{item.get('final_text') or item.get('raw_text') or 'Sin contenido'}"
            for idx, item in enumerate(snapshot["transcriptions"], start=1)
        ]
    ) or "No hay transcripciones registradas."

    return f"""
DATOS GENERALES
- Código de inspección: {general.get("inspection_code")}
- Cliente: {general.get("client_name")}
- Equipo: {general.get("equipment_name")}
- Fecha: {general.get("inspection_date")}
- Inspector: {general.get("inspector_name")}
- Tipo de servicio: {general.get("service_type")}

CAMPOS ESTRUCTURADOS Y VALIDACIÓN
{fields_text}

EVIDENCIAS
{evidences_text}

TRANSCRIPCIONES
{transcriptions_text}
""".strip()


def _render_final_text(payload: LLMReportSections) -> str:
    findings = "\n".join([f"- {item}" for item in payload.key_findings]) or "- Sin hallazgos registrados"
    recommendations = "\n".join([f"- {item}" for item in payload.recommendations]) or "- Sin recomendaciones"

    return f"""
{payload.title}

1. RESUMEN EJECUTIVO
{payload.executive_summary}

2. CONTEXTO DE LA INSPECCIÓN
{payload.inspection_context}

3. HALLAZGOS PRINCIPALES
{findings}

4. VALIDACIÓN OCR
{payload.ocr_validation_summary}

5. OBSERVACIONES TRANSCRITAS
{payload.voice_observations}

6. RECOMENDACIONES
{recommendations}

7. INFORME REDACTADO
{payload.final_report}
""".strip()


def generate_llm_report_draft(db: Session, inspection_id: int, template_version: str = "llama3-v1") -> ReportDraft:
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

    snapshot = _build_snapshot(inspection, transcriptions)
    context_text = _format_input_context(snapshot)

    llm = ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout,
    )

    structured_llm = llm.with_structured_output(LLMReportSections)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
Eres un asistente técnico especializado en inspecciones.
Debes redactar un borrador de informe de inspección en español formal, técnico y claro.

Reglas:
- Usa únicamente la información proporcionada.
- No inventes datos.
- Si falta información, indícalo de forma explícita.
- Prioriza campos críticos, observaciones, discrepancias OCR y recomendaciones.
- La salida debe cumplir exactamente con el esquema estructurado solicitado.
                """.strip(),
            ),
            (
                "human",
                """
Genera un borrador estructurado del informe de inspección usando este contexto:

{context}

Necesito:
- título,
- resumen ejecutivo,
- contexto,
- hallazgos,
- resumen de validación OCR,
- resumen de observaciones transcritas,
- recomendaciones,
- y el informe final redactado.
                """.strip(),
            ),
        ]
    )

    chain = prompt | structured_llm
    result = chain.invoke({"context": context_text})

    final_text = _render_final_text(result)
    elapsed_ms = int((perf_counter() - started) * 1000)

    enriched_snapshot = {
        **snapshot,
        "llm": {
            "provider": "ollama",
            "model": settings.ollama_model,
            "template_version": template_version,
            "generation_time_ms": elapsed_ms,
            "structured_sections": result.model_dump(),
        },
    }

    draft = ReportDraft(
        inspection_id=inspection.id,
        title=result.title,
        template_version=template_version,
        status="generated_llm",
        generated_text=final_text,
        edited_text=None,
        source_snapshot=enriched_snapshot,
        generation_time_ms=elapsed_ms,
    )

    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft