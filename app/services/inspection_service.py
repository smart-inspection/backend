from sqlalchemy.orm import Session

from app.db.models import Inspection
from app.schemas.inspection import InspectionCreate


def create_inspection(db: Session, payload: InspectionCreate) -> Inspection:
    inspection = Inspection(**payload.model_dump())
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


def list_inspections(db: Session) -> list[Inspection]:
    return db.query(Inspection).order_by(Inspection.id.desc()).all()


def get_inspection_by_id(db: Session, inspection_id: int) -> Inspection | None:
    return db.query(Inspection).filter(Inspection.id == inspection_id).first()