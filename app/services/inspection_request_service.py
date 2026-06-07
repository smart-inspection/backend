from sqlalchemy.orm import Session

from app.db.models import InspectionRequest
from app.schemas.inspection_request import InspectionRequestCreate


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