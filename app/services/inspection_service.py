from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, InspectionProductivity, User
from app.schemas.inspection import InspectionCreate

VALID_INSPECTION_STATUSES = {"draft", "in_review", "observed", "finalized"}


def _resolve_inspector_name(user: User | None) -> str | None:
    if not user or not user.full_name:
        return None

    full_name = user.full_name.strip()
    return full_name or None


def update_inspection_status(db: Session, inspection_id: int, new_status: str) -> Inspection | None:
    inspection = get_inspection_by_id(db, inspection_id)
    if not inspection:
        return None

    normalized_status = (new_status or "").strip().lower()
    if normalized_status not in VALID_INSPECTION_STATUSES:
        raise ValueError(f"Invalid inspection status: {normalized_status}")

    inspection.status = normalized_status
    inspection.updated_at = datetime.now(timezone.utc)

    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


def create_inspection(db: Session, payload: InspectionCreate) -> Inspection:
    responsible_user = None
    if payload.responsible_inspector_id is not None:
        responsible_user = (
            db.query(User)
            .filter(User.id == payload.responsible_inspector_id)
            .first()
        )
        if not responsible_user:
            raise ValueError("Responsible inspector not found")

    inspection = Inspection(**payload.model_dump())
    db.add(inspection)
    db.flush()

    productivity = InspectionProductivity(
        inspection_id=inspection.id,
        inspector_name=_resolve_inspector_name(responsible_user),
        scheduled_date=inspection.inspection_date,
        operational_status="pending",
    )
    db.add(productivity)

    db.commit()

    created = get_inspection_by_id(db, inspection.id)
    if created:
        return created

    db.refresh(inspection)
    return inspection


def list_inspections(db: Session) -> list[Inspection]:
    return (
        db.query(Inspection)
        .options(selectinload(Inspection.responsible_inspector))
        .order_by(Inspection.id.desc())
        .all()
    )


def get_inspection_by_id(db: Session, inspection_id: int) -> Inspection | None:
    return (
        db.query(Inspection)
        .options(selectinload(Inspection.responsible_inspector))
        .filter(Inspection.id == inspection_id)
        .first()
    )