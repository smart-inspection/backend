from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.evidence import EvidenceCreate, EvidenceResponse
from app.services.evidence_service import create_evidence, list_evidences

router = APIRouter(prefix="/inspections", tags=["evidences"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/{inspection_id}/evidences", response_model=EvidenceResponse, status_code=201)
def create_evidence_endpoint(
        inspection_id: int,
        payload: EvidenceCreate,
        db: Session = Depends(get_db)
):
    evidence = create_evidence(db, inspection_id, payload)
    if not evidence:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return evidence

@router.get("/{inspection_id}/evidences", response_model=list[EvidenceResponse])
def list_evidences_endpoint(
        inspection_id: int,
        db: Session = Depends(get_db)
):
    return list_evidences(db, inspection_id)