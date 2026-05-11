from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.db.models import Evidence, Inspection
from app.services.storage_service import save_evidence_upload


def get_inspection(db: Session, inspection_id: int) -> Inspection | None:
    return db.query(Inspection).filter(Inspection.id == inspection_id).first()


def build_file_url(file_path: str) -> str:
    normalized = file_path.replace("\\", "/").lstrip("/")
    return f"/{normalized}"


def serialize_evidence(evidence: Evidence) -> dict:
    confidence = evidence.ocr_confidence
    if isinstance(confidence, Decimal):
        confidence = float(confidence)
    elif confidence is not None:
        confidence = float(confidence)

    return {
        "id": evidence.id,
        "inspection_id": evidence.inspection_id,
        "file_path": evidence.file_path,
        "file_url": build_file_url(evidence.file_path),
        "file_type": evidence.file_type,
        "evidence_category": evidence.evidence_category,
        "caption": evidence.caption,
        "ocr_extracted_text": evidence.ocr_extracted_text,
        "ocr_confidence": confidence,
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
) -> Evidence | None:
    inspection = get_inspection(db, inspection_id)
    if not inspection:
        return None

    relative_path, content_type = save_evidence_upload(inspection_id, file)

    evidence = Evidence(
        inspection_id=inspection_id,
        file_path=relative_path,
        file_type=content_type,
        evidence_category=evidence_category,
        caption=caption,
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