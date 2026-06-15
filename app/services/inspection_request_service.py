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
    db.commit()
    db.refresh(inspection_request)
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
    db.commit()
    db.refresh(inspection_request)
    return inspection_request