from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.transcription import TranscriptionCreate, TranscriptionResponse, TranscriptionUpdate
from app.services.transcription_service import create_and_process_transcription, list_transcriptions_by_inspection, \
    get_transcription_by_id, update_transcription_text

router = APIRouter(prefix="/transcription", tags=["Transcription"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("", response_model=TranscriptionResponse, status_code=201)
def create_transcription_endpoint(payload: TranscriptionCreate, db: Session = Depends(get_db)) -> APIRouter:
    try:
        return create_and_process_transcription(db, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get("/inspection/{inspection_id}")
def list_transcriptions_by_inspection_endpoint(inspection_id: int, db: Session = Depends(get_db)):
    return list_transcriptions_by_inspection(db, inspection_id)

@router.get("/{transcription_id}")
def get_transcription_endpoint(transcription_id: int, db: Session = Depends(get_db)):
    transcription = get_transcription_by_id(db, transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return transcription

@router.put("/{transcription_id}", response_model=TranscriptionResponse)
def update_transcription_endpoint(
    transcription_id: int,
    payload: TranscriptionUpdate,
    db: Session = Depends(get_db)
):
    transcription = update_transcription_text(db, transcription_id, payload)
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return transcription