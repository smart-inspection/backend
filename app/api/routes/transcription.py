from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, tecnico, todos
from app.db.models.users import User
from app.schemas.transcription import TranscriptionCreate, TranscriptionResponse, TranscriptionUpdate
from app.services.transcription_service import (
    create_and_process_transcription,
    eliminar_transcripcion,
    get_transcription_by_id,
    list_transcriptions_by_inspection,
    update_transcription_text,
)

router = APIRouter(prefix="/transcription", tags=["Transcription"])

@router.post("", response_model=TranscriptionResponse, status_code=201)
def create_transcription_endpoint(
    payload: TranscriptionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(tecnico),
) -> APIRouter:
    try:
        return create_and_process_transcription(db, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get("/inspection/{inspection_id}")
def list_transcriptions_by_inspection_endpoint(
    inspection_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(todos),
):
    return list_transcriptions_by_inspection(db, inspection_id)

@router.get("/{transcription_id}")
def get_transcription_endpoint(
    transcription_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(todos),
):
    transcription = get_transcription_by_id(db, transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return transcription

@router.put("/{transcription_id}", response_model=TranscriptionResponse)
def update_transcription_endpoint(
    transcription_id: int,
    payload: TranscriptionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(tecnico),
):
    transcription = update_transcription_text(db, transcription_id, payload)
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return transcription


@router.delete("/{transcription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transcription_endpoint(
    transcription_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(tecnico),
):
    try:
        eliminado = eliminar_transcripcion(db, transcription_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al eliminar transcripción: {exc}")
    if not eliminado:
        raise HTTPException(status_code=404, detail="Transcripción no encontrada")
    return Response(status_code=status.HTTP_204_NO_CONTENT)