from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, tecnico
from app.db.models.users import User
from app.schemas.ocr import OCRExtractResponse, OCRValidationResponse
from app.services.ocr_service import extract_text_from_evidence
from app.services.validation_service import validate_inspection_ocr

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/evidences/{evidence_id}/extract", response_model=OCRExtractResponse)
def extract_ocr_from_evidence_endpoint(
    evidence_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(tecnico),
):
    try:
        result = extract_text_from_evidence(db, evidence_id)
        if not result:
            raise HTTPException(status_code=404, detail="Evidence not found")
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except AttributeError as exc:
        raise HTTPException(status_code=500, detail=f"Configuración OCR inválida: {exc}")


@router.post("/inspections/{inspection_id}/validate", response_model=OCRValidationResponse)
def validate_ocr_for_inspection_endpoint(
    inspection_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(tecnico),
):
    try:
        result = validate_inspection_ocr(db, inspection_id)
        if not result:
            raise HTTPException(status_code=404, detail="Inspection not found")
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))