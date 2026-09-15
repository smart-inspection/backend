from sqlalchemy.orm import Session

from app.db import Inspection
from app.db.models import InspectionRequest
from app.schemas.inspection_request import InspectionRequestCreate, InspectionRequestConvert


def create_inspection_request(
    db: Session,
    payload: InspectionRequestCreate,
) -> InspectionRequest:
    inspection_request = InspectionRequest(**payload.model_dump())
    db.add(inspection_request)
    try:
        db.commit()
        db.refresh(inspection_request)
    except Exception:
        db.rollback()
        raise
    return inspection_request


def list_inspection_requests(db: Session) -> list[InspectionRequest]:
    return (
        db.query(InspectionRequest)
        .order_by(InspectionRequest.id.desc())
        .all()
    )


def get_inspection_request_by_id(
    db: Session,
    inspection_request_id: int,
) -> InspectionRequest | None:
    return (
        db.query(InspectionRequest)
        .filter(InspectionRequest.id == inspection_request_id)
        .first()
    )

def convert_inspection_request(
    db: Session,
    inspection_request_id: int,
    payload: InspectionRequestConvert,
) -> InspectionRequest:
    inspection_request = get_inspection_request_by_id(db, inspection_request_id)
    if not inspection_request:
        raise ValueError("Inspection request not found")

    inspection = (
        db.query(Inspection)
        .filter(Inspection.id == payload.inspection_id)
        .first()
    )
    if not inspection:
        raise ValueError("Inspection not found")

    inspection_request.inspection_id = payload.inspection_id
    inspection_request.status = payload.status.strip().lower() if payload.status else "converted"

    db.add(inspection_request)
    try:
        db.commit()
        db.refresh(inspection_request)
    except Exception:
        db.rollback()
        raise
    return inspection_request


def eliminar_inspection_request(db: Session, request_id: int) -> bool:
    """
    Elimina una solicitud de inspección.
    Retorna True si fue eliminada, False si no existía.
    """
    request = get_inspection_request_by_id(db, request_id)
    if not request:
        return False
    try:
        db.delete(request)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True