import re

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection
from app.domain.rules.numeric_rules import compare_numeric, find_numeric_value
from app.domain.rules.plate_rules import compare_plate, find_plate
from app.domain.rules.serial_rules import compare_serial, find_serial
from app.domain.rules.vin_rules import compare_vin, find_vin
from app.services.ocr_service import extract_text_from_evidence_record


def _normalize_generic(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", "", value.strip().upper())


def _extract_candidate(field_key: str, expected_type: str, text: str, manual_value: str | None) -> str | None:
    key = field_key.lower()
    expected = expected_type.lower()

    if "vin" in key:
        return find_vin(text)

    if "plac" in key or "plate" in key:
        return find_plate(text)

    if "serial" in key or "serie" in key:
        return find_serial(text, manual_value)

    if expected in {"number", "numeric", "integer", "float", "decimal"}:
        return find_numeric_value(text, manual_value)

    if manual_value:
        normalized_manual = _normalize_generic(manual_value)
        normalized_text = _normalize_generic(text)
        if normalized_manual and normalized_manual in normalized_text:
            return manual_value

    return None


def _compare_values(field_key: str, expected_type: str, manual_value: str | None, ocr_value: str | None) -> tuple[str, str]:
    key = field_key.lower()
    expected = expected_type.lower()

    if not ocr_value:
        return "not_found", "No se detectó valor OCR para este campo"

    if "vin" in key:
        return (
            ("matched", "VIN coincide con OCR")
            if compare_vin(manual_value, ocr_value)
            else ("mismatch", "VIN no coincide con OCR")
        )

    if "plac" in key or "plate" in key:
        return (
            ("matched", "Placa coincide con OCR")
            if compare_plate(manual_value, ocr_value)
            else ("mismatch", "Placa no coincide con OCR")
        )

    if "serial" in key or "serie" in key:
        return (
            ("matched", "Serie coincide con OCR")
            if compare_serial(manual_value, ocr_value)
            else ("mismatch", "Serie no coincide con OCR")
        )

    if expected in {"number", "numeric", "integer", "float", "decimal"}:
        return (
            ("matched", "Valor numérico coincide con OCR")
            if compare_numeric(manual_value, ocr_value)
            else ("mismatch", "Valor numérico no coincide con OCR")
        )

    left = _normalize_generic(manual_value)
    right = _normalize_generic(ocr_value)

    if left and left == right:
        return "matched", "Campo coincide con OCR"

    return "mismatch", "Campo no coincide con OCR"


def validate_inspection_ocr(db: Session, inspection_id: int) -> dict | None:
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
        return None

    image_evidences = [
        evidence for evidence in inspection.evidences
        if evidence.file_type and evidence.file_type.lower().startswith("image/")
    ]

    if not image_evidences:
        raise ValueError("La inspección no tiene evidencias de imagen para OCR")

    extracted_chunks = []
    confidence_values = []

    for evidence in image_evidences:
        if evidence.ocr_processed and evidence.ocr_extracted_text:
            text = evidence.ocr_extracted_text
            confidence = float(evidence.ocr_confidence) if evidence.ocr_confidence is not None else None
        else:
            result = extract_text_from_evidence_record(db, evidence)
            text = result["extracted_text"]
            confidence = result["confidence"]

        if text:
            extracted_chunks.append(text)
        if confidence is not None:
            confidence_values.append(confidence)

    aggregated_text = "\n".join(extracted_chunks).strip()
    average_confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else None

    results = []
    matched = 0
    mismatched = 0
    not_found = 0

    for field in inspection.fields:
        ocr_value = _extract_candidate(
            field_key=field.field_key,
            expected_type=field.expected_type,
            text=aggregated_text,
            manual_value=field.manual_value,
        )

        validation_status, validation_message = _compare_values(
            field_key=field.field_key,
            expected_type=field.expected_type,
            manual_value=field.manual_value,
            ocr_value=ocr_value,
        )

        field.ocr_value = ocr_value
        field.validation_status = validation_status
        field.validation_message = validation_message
        field.confidence = average_confidence

        if validation_status == "matched":
            matched += 1
            if ocr_value:
                field.final_value = ocr_value
        elif validation_status == "mismatch":
            mismatched += 1
            if not field.final_value:
                field.final_value = field.manual_value
        else:
            not_found += 1
            if not field.final_value:
                field.final_value = field.manual_value

        results.append(
            {
                "field_id": field.id,
                "field_key": field.field_key,
                "field_label": field.field_label,
                "manual_value": field.manual_value,
                "ocr_value": field.ocr_value,
                "final_value": field.final_value,
                "validation_status": field.validation_status,
                "validation_message": field.validation_message,
                "confidence": float(field.confidence) if field.confidence is not None else None,
            }
        )

    db.commit()

    return {
        "inspection_id": inspection.id,
        "processed_evidences": len(image_evidences),
        "aggregated_text": aggregated_text,
        "summary": {
            "matched": matched,
            "mismatched": mismatched,
            "not_found": not_found,
            "average_confidence": average_confidence,
        },
        "results": results,
    }
