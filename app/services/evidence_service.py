from decimal import Decimal
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.db.models import Evidence, Inspection
from app.services.evidence_label_service import resolve_evidence_label
from app.services.storage_service import save_evidence_upload

def get_inspection(db: Session, inspection_id: int) -> Inspection | None:
    return db.query(Inspection).filter(Inspection.id == inspection_id).first()

def build_file_url(filepath: str) -> str:
    normalized = filepath.replace("\\", "/").lstrip("/")
    return f"/{normalized}"

def serialize_evidence(evidence: Evidence) -> dict[str, Any]:
    ocr_confidence = evidence.ocr_confidence
    label_confidence = evidence.label_confidence

    if isinstance(ocr_confidence, Decimal):
        ocr_confidence = float(ocr_confidence)
    elif ocr_confidence is not None:
        ocr_confidence = float(ocr_confidence)

    if isinstance(label_confidence, Decimal):
        label_confidence = float(label_confidence)
    elif label_confidence is not None:
        label_confidence = float(label_confidence)

    return {
        "id": evidence.id,
        "inspection_id": evidence.inspection_id,
        "file_path": evidence.file_path,
        "file_url": build_file_url(evidence.file_path),
        "file_type": evidence.file_type,
        "evidence_category": evidence.evidence_category,
        "caption": evidence.caption,
        "raw_label": evidence.raw_label,
        "normalized_label": evidence.normalized_label,
        "evidence_slot": evidence.evidence_slot,
        "component_code": evidence.component_code,
        "axle_number": evidence.axle_number,
        "side": evidence.side,
        "is_reference": evidence.is_reference,
        "label_confidence": label_confidence,
        "metadata_json": evidence.metadata_json,
        "ocr_extracted_text": evidence.ocr_extracted_text,
        "ocr_confidence": ocr_confidence,
        "ocr_processed": evidence.ocr_processed,
        "ocr_last_processed_at": evidence.ocr_last_processed_at,
        "uploaded_at": evidence.uploaded_at,
    }

def create_evidence(
    db: Session,
    inspection_id: int,
    file: UploadFile,
    evidence_category: str,
    caption: str | None = None,
    raw_label: str | None = None,
    component_code: str | None = None,
    axle_number: int | None = None,
    side: str | None = None,
    is_reference: bool = False,
) -> Evidence | None:
    inspection = get_inspection(db, inspection_id)
    if not inspection:
        return None

    relative_path, content_type = save_evidence_upload(inspection_id, file)

    label_result = resolve_evidence_label(
        raw_label=raw_label,
        component_code=component_code,
        axle_number=axle_number,
        side=side,
        is_reference=is_reference,
    )

    evidence = Evidence(
        inspection_id=inspection_id,
        file_path=relative_path,
        file_type=content_type,
        evidence_category=evidence_category,
        caption=caption,
        raw_label=label_result.raw_label,
        normalized_label=label_result.normalized_label,
        evidence_slot=label_result.evidence_slot,
        component_code=label_result.component_code,
        axle_number=label_result.axle_number,
        side=label_result.side,
        is_reference=label_result.is_reference,
        label_confidence=label_result.label_confidence,
        metadata_json=label_result.metadata_json,
        ocr_processed=False,
    )

    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence

def list_evidences(db: Session, inspection_id: int) -> list[Evidence]:
    return (
        db.query(Evidence)
        .filter(Evidence.inspection_id == inspection_id)
        .order_by(Evidence.id.asc())
        .all()
    )

def get_evidence(db: Session, evidence_id: int) -> Evidence | None:
    return db.query(Evidence).filter(Evidence.id == evidence_id).first()