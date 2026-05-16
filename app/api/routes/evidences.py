from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.evidence import EvidenceOCRResponse, EvidenceResponse
from app.services.evidence_ocr_service import process_evidence_ocr
from app.services.evidence_service import (
    create_evidence,
    get_inspection,
    list_evidences,
    serialize_evidence,
)

router = APIRouter(tags=["evidences"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/inspections/{inspection_id}/evidences", response_model=EvidenceResponse, status_code=201)
def create_evidence_endpoint(
    inspection_id: int,
    file: UploadFile = File(...),
    evidence_category: str = Form(...),
    caption: str | None = Form(None),
    raw_label: str | None = Form(None),
    component_code: str | None = Form(None),
    axle_number: int | None = Form(None),
    side: str | None = Form(None),
    is_reference: bool = Form(False),
    db: Session = Depends(get_db),
):
    try:
        evidence = create_evidence(
            db=db,
            inspection_id=inspection_id,
            file=file,
            evidence_category=evidence_category,
            caption=caption,
            raw_label=raw_label,
            component_code=component_code,
            axle_number=axle_number,
            side=side,
            is_reference=is_reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not evidence:
        raise HTTPException(status_code=404, detail="Inspection not found")

    return serialize_evidence(evidence)


@router.get("/inspections/{inspection_id}/evidences", response_model=list[EvidenceResponse])
def list_evidences_endpoint(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    inspection = get_inspection(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    evidences = list_evidences(db, inspection_id)
    return [serialize_evidence(item) for item in evidences]


@router.post("/evidences/{evidence_id}/ocr", response_model=EvidenceOCRResponse)
def run_ocr_for_evidence_endpoint(
    evidence_id: int,
    db: Session = Depends(get_db),
):
    try:
        evidence = process_evidence_ocr(db, evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    return {
        "evidence_id": evidence.id,
        "ocr_extracted_text": evidence.ocr_extracted_text,
        "ocr_confidence": float(evidence.ocr_confidence) if evidence.ocr_confidence is not None else None,
        "ocr_processed": evidence.ocr_processed,
        "ocr_last_processed_at": evidence.ocr_last_processed_at,
    }