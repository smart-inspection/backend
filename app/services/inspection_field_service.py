from sqlalchemy.orm import Session

from app.db.models import Inspection, InspectionField
from app.schemas.inspection_field import InspectionFieldCreate


def create_inspection_field(
        db: Session,
        inspection_id: int,
        payload: InspectionFieldCreate
) -> InspectionField | None:
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        return None

    field = InspectionField(
        inspection_id=inspection_id,
        **payload.model_dump()
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field

def list_inspection_fields(db: Session, inspection_id: int) -> list[InspectionField]:
    return (
        db.query(InspectionField)
        .filter(InspectionField.inspection_id == inspection_id)
        .order_by(InspectionField.id.asc())
        .all()
    )