import importlib
import inspect
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.evidence import Evidence
from app.db.models.inspection import Inspection
from app.db.models.inspection_field import InspectionField
from app.db.models.report_draft import ReportDraft
from app.db.models.transcription import Transcription
from app.db.models.users import User
from app.schemas.imports import historical_import_response
from app.services.docx_import_service import extract_evidence_binaries, preview_docx_report

try:
    from app.services.evidence_ocr_service import process_evidence_ocr
except Exception:  # pragma: no cover
    process_evidence_ocr = None


def _clean_value(value: Any) -> Any:
    if isinstance(value, str):
        value = value.replace("\xa0", " ")
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"\s+([,;:.])", r"\1", value)
        value = re.sub(r"\.{2,}", ".", value)
        value = value.strip()
        return value or None
    return value


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _set_first_attr(instance: Any, candidates: list[str], value: Any) -> str | None:
    value = _clean_value(value)
    if value is None:
        return None
    for attr_name in candidates:
        if hasattr(instance, attr_name):
            setattr(instance, attr_name, value)
            return attr_name
    return None


def _get_user_by_email(db: Session, email: str | None) -> User | None:
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()

def _normalize_requested_by_email(value: str | None) -> str | None:
    value = _clean_value(value)
    if not value:
        return None

    if value.lower() in {"string", "null", "undefined"}:
        return None

    return value

FIELD_METADATA_MAP: dict[str, tuple[str, str, str]] = {
    "report_code": ("Código de informe", "identificacion", "string"),
    "plate": ("Placa", "identificacion", "string"),
    "client_name": ("Cliente", "identificacion", "string"),
    "inspector_name": ("Inspector responsable", "identificacion", "string"),
    "inspection_date": ("Fecha de inspección", "identificacion", "date"),
    "equipment_type": ("Tipo de equipo", "identificacion", "string"),
    "brand": ("Marca", "identificacion", "string"),
    "vin": ("VIN", "identificacion", "string"),
    "manufacturing_year": ("Año de fabricación", "identificacion", "number"),
    "reference_mileage": ("Kilometraje de referencia", "identificacion", "number"),
    "antiquity_years": ("Antigüedad", "identificacion", "number"),
    "axle_count": ("Número de ejes", "identificacion", "number"),
    "payload_kg": ("Carga útil (kg)", "identificacion", "number"),
    "net_weight_kg": ("Peso neto (kg)", "identificacion", "number"),
    "king_pin_brand": ("Marca de king pin", "identificacion", "string"),
    "original_conclusion": ("Conclusión original", "conclusion", "string"),
}


def _humanize_field_key(field_key: str) -> str:
    text = field_key.replace("_", " ").strip()
    if not text:
        return "Campo importado"
    return text[:1].upper() + text[1:]


def _resolve_field_metadata(field_key: str) -> tuple[str, str, str] | None:
    if field_key == "source_filename":
        return None

    metadata = FIELD_METADATA_MAP.get(field_key)
    if metadata:
        return metadata

    if field_key.startswith("result_"):
        result_key = field_key.removeprefix("result_")
        return (
            f"Resultado {_humanize_field_key(result_key)}",
            "resultados",
            "string",
        )

    return (_humanize_field_key(field_key), "importacion_historica", "string")

def _build_inspection_payload(preview) -> dict[str, Any]:
    fields = preview.extracted_fields

    inspection_code = (
        fields.get("plate")
        or fields.get("report_code")
        or preview.source_filename
    )

    return {
        "code": inspection_code,
        "client": fields.get("client_name"),
        "equipment_type": fields.get("equipment_type") or "Semirremolque",
        "inspection_type": "PERIODICA",
        "inspection_date": _parse_date(fields.get("inspection_date")),
        "location": "Importado desde informe histórico",
        "requester": fields.get("client_name"),
        "responsible_inspector": fields.get("inspector_name"),
        "status": "completed",
        "notes": f"Importado desde DOCX histórico: {preview.source_filename}",
        "plate": fields.get("plate"),
    }


def _create_inspection(db: Session, preview, requested_by_user: User | None) -> Inspection:
    payload = _build_inspection_payload(preview)

    inspection = Inspection()

    _set_first_attr(inspection, ["code", "inspection_code"], payload["code"])
    _set_first_attr(inspection, ["client_name", "clientname", "company_name"], payload["client"])
    _set_first_attr(inspection, ["equipment_type", "equipmenttype"], payload["equipment_type"])
    _set_first_attr(inspection, ["inspection_type", "inspectiontype", "type"], payload["inspection_type"])
    _set_first_attr(inspection, ["inspection_date", "inspectiondate", "scheduled_date"], payload["inspection_date"])
    _set_first_attr(inspection, ["location", "site"], payload["location"])
    _set_first_attr(inspection, ["requested_by", "requestedby", "contact_name"], payload["requester"])
    _set_first_attr(inspection, ["status"], payload["status"])
    _set_first_attr(inspection, ["notes", "description"], payload["notes"])
    _set_first_attr(inspection, ["plate", "equipment_identifier", "asset_code"], payload["plate"])

    if requested_by_user:
        _set_first_attr(inspection, ["responsible_inspector_id"], requested_by_user.id)

    db.add(inspection)
    db.flush()
    return inspection


def _create_inspection_field(
    db: Session,
    inspection_id: int,
    field_name: str,
    field_value: Any,
    source: str = "historical_docx",
) -> InspectionField | None:
    normalized_value = _clean_value(str(field_value)) if field_value is not None else None
    if normalized_value is None:
        return None

    metadata = _resolve_field_metadata(field_name)
    if metadata is None:
        return None

    field_label, field_group, expected_type = metadata

    field = InspectionField()

    _set_first_attr(field, ["inspection_id", "inspectionid"], inspection_id)
    _set_first_attr(field, ["field_key", "fieldkey"], field_name)
    _set_first_attr(field, ["field_label", "fieldlabel"], field_label)
    _set_first_attr(field, ["field_group", "fieldgroup"], field_group)
    _set_first_attr(field, ["expected_type", "expectedtype"], expected_type)
    _set_first_attr(field, ["manual_value", "manualvalue"], normalized_value)
    _set_first_attr(field, ["final_value", "finalvalue"], normalized_value)
    _set_first_attr(field, ["ocr_value", "ocrvalue"], None)
    _set_first_attr(field, ["validation_status", "validationstatus"], "imported")
    _set_first_attr(field, ["validation_message", "validationmessage"], source)
    _set_first_attr(field, ["confidence"], None)

    db.add(field)
    db.flush()
    return field


def _write_evidence_file(inspection_id: int, filename: str, content: bytes) -> str:
    target_dir = Path("uploads") / "historical_imports" / str(inspection_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(content)
    return str(target_path)


def _create_evidence_record(
    db: Session,
    inspection_id: int,
    image_preview,
    content: bytes,
) -> Evidence:
    stored_path = _write_evidence_file(inspection_id, image_preview.filename, content)
    evidence = Evidence()

    _set_first_attr(evidence, ["inspection_id"], inspection_id)
    _set_first_attr(evidence, ["file_path", "filepath", "storage_path"], stored_path)
    _set_first_attr(evidence, ["file_name", "filename", "original_filename"], image_preview.filename)
    _set_first_attr(evidence, ["content_type", "mime_type"], image_preview.content_type)
    _set_first_attr(evidence, ["raw_label"], image_preview.caption)
    _set_first_attr(evidence, ["normalized_label"], image_preview.component_code or image_preview.evidence_slot)
    _set_first_attr(evidence, ["evidence_slot"], image_preview.evidence_slot)
    _set_first_attr(evidence, ["component_code"], image_preview.component_code)
    _set_first_attr(evidence, ["axle_number"], image_preview.axle_number)
    _set_first_attr(evidence, ["side"], image_preview.side)
    _set_first_attr(evidence, ["is_reference"], False)
    _set_first_attr(evidence, ["metadata_json"], image_preview.metadata_json | {"import_reason": image_preview.reason})
    _set_first_attr(evidence, ["is_ocr_processed"], False)

    db.add(evidence)
    db.flush()
    return evidence


def _maybe_run_ocr(db: Session, evidence_id: int, image_preview) -> None:
    if process_evidence_ocr is None:
        return
    if image_preview.evidence_slot not in {"placa_tecnica", "identificacion"}:
        return
    try:
        process_evidence_ocr(db, evidence_id)
    except Exception:
        return


def _create_transcription(
    db: Session,
    inspection_id: int,
    content: str | None,
    source_file_path: str,
) -> Transcription | None:
    normalized_content = _clean_value(content)
    normalized_source_file_path = _clean_value(source_file_path)

    if not normalized_content or not normalized_source_file_path:
        return None

    transcription = Transcription()

    _set_first_attr(transcription, ["inspection_id"], inspection_id)
    _set_first_attr(transcription, ["evidence_id"], None)
    _set_first_attr(transcription, ["source_file_path"], normalized_source_file_path)
    _set_first_attr(transcription, ["language"], "es")
    _set_first_attr(transcription, ["model_name"], "historical_docx")
    _set_first_attr(transcription, ["raw_text", "content", "text", "transcription_text"], normalized_content)
    _set_first_attr(transcription, ["final_text"], normalized_content)
    _set_first_attr(transcription, ["confidence"], None)
    _set_first_attr(transcription, ["processed"], True)
    _set_first_attr(transcription, ["edited_manually"], False)

    db.add(transcription)
    db.flush()
    return transcription


def _create_report_draft(
    db: Session,
    inspection_id: int,
    content: str,
    draft_type: str,
) -> ReportDraft | None:
    if not content:
        return None

    draft = ReportDraft()
    _set_first_attr(draft, ["inspection_id"], inspection_id)
    _set_first_attr(draft, ["content", "draft_content", "text"], content)
    _set_first_attr(draft, ["draft_type", "type"], draft_type)
    _set_first_attr(draft, ["source", "origin"], "historical_docx")
    _set_first_attr(draft, ["status"], "generated")

    db.add(draft)
    db.flush()
    return draft


def _try_generate_llm_draft(db: Session, inspection_id: int, fallback_content: str) -> str:
    candidate_functions = [
        "generate_llm_report",
        "generate_report_with_llm",
        "generate_llm_draft",
        "build_llm_report",
    ]

    try:
        module = importlib.import_module("app.services.llmreportservice")
    except Exception:
        return fallback_content

    for function_name in candidate_functions:
        function = getattr(module, function_name, None)
        if not callable(function):
            continue

        try:
            signature = inspect.signature(function)
            kwargs: dict[str, Any] = {}

            for parameter_name in signature.parameters.keys():
                if parameter_name == "db":
                    kwargs["db"] = db
                elif parameter_name in {"inspection_id", "inspectionid"}:
                    kwargs[parameter_name] = inspection_id

            result = function(**kwargs)
            if isinstance(result, str) and result.strip():
                return result
            if hasattr(result, "content") and isinstance(result.content, str):
                return result.content
            if isinstance(result, dict):
                for key in ["content", "draft", "report"]:
                    if isinstance(result.get(key), str) and result.get(key).strip():
                        return result[key]
        except Exception:
            continue

    return fallback_content


def import_historical_docx(
    db: Session,
    filepath: str | Path,
    requested_by_email: str | None = None,
    generate_llm_draft: bool = True,
) -> historical_import_response:
    preview = preview_docx_report(filepath)
    binaries = extract_evidence_binaries(filepath)

    normalized_requested_by_email = _normalize_requested_by_email(requested_by_email)
    requested_by_user = _get_user_by_email(db, normalized_requested_by_email)

    inspection = _create_inspection(db, preview, requested_by_user)

    field_ids: list[int] = []

    for key, value in preview.extracted_fields.items():
        if key == "source_filename":
            continue

        field = _create_inspection_field(db, inspection.id, key, value)
        if field:
            field_ids.append(field.id)

    for result in preview.results:
        serialized_value = (
            f"condition={result.condition or '--'} | "
            f"observations={result.observations or '--'} | "
            f"action_required={result.action_required or '--'}"
        )
        result_key = (
            f"result_{result.component.lower().replace(' ', '_').replace('/', '_')}"
        )
        field = _create_inspection_field(
            db,
            inspection.id,
            result_key,
            serialized_value,
        )
        if field:
            field_ids.append(field.id)

    if preview.conclusion:
        field = _create_inspection_field(
            db,
            inspection.id,
            "original_conclusion",
            preview.conclusion,
        )
        if field:
            field_ids.append(field.id)

    evidence_ids: list[int] = []
    for image in preview.images:
        if image.classification != "evidence":
            continue
        content = binaries.get(image.filename)
        if not content:
            continue

        evidence = _create_evidence_record(db, inspection.id, image, content)
        evidence_ids.append(evidence.id)
        _maybe_run_ocr(db, evidence.id, image)

    transcription_id = None
    transcription = _create_transcription(
        db,
        inspection.id,
        preview.synthetic_transcription,
        str(filepath),
    )
    if transcription:
        transcription_id = transcription.id

    draft_ids: list[int] = []
    base_draft = _create_report_draft(db, inspection.id, preview.draft_base or "", "historical_base")
    if base_draft:
        draft_ids.append(base_draft.id)

    if generate_llm_draft:
        llm_content = _try_generate_llm_draft(db, inspection.id, preview.draft_base or "")
        llm_draft = _create_report_draft(db, inspection.id, llm_content, "historical_llm")
        if llm_draft:
            draft_ids.append(llm_draft.id)

    db.commit()

    return historical_import_response(
        source_filename=preview.source_filename,
        inspection_id=inspection.id,
        inspection_field_ids=field_ids,
        evidence_ids=evidence_ids,
        transcription_id=transcription_id,
        report_draft_ids=draft_ids,
        warnings=preview.warnings,
        summary={
            "detected_fields": len([value for value in preview.extracted_fields.values() if value]),
            "detected_results": len(preview.results),
            "detected_images": len(preview.images),
            "imported_evidences": len(evidence_ids),
        },
    )