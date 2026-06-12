from datetime import datetime, timezone, date

from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, InspectionProductivity
from app.schemas.productivity import ProductivityCreate, ProductivityUpdate


GOAL_MINUTES = 20

INSPECTION_STATUS_TO_OPERATIONAL_STATUS = {
    "draft": "pending",
    "in_review": "in_progress",
    "observed": "observed",
    "finalized": "completed",
}

FILTER_STATUS_TO_OPERATIONAL_STATUS = {
    "draft": "pending",
    "pending": "pending",
    "in_review": "in_progress",
    "in_progress": "in_progress",
    "observed": "observed",
    "finalized": "completed",
    "completed": "completed",
}


def _normalize_operational_status_filter(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().lower()
    return FILTER_STATUS_TO_OPERATIONAL_STATUS.get(normalized, normalized)

def _inspection_query(db: Session):
    query = db.query(Inspection)
    relationship_attr = getattr(Inspection, "responsible_inspection", None)
    if relationship_attr is not None:
        query = query.options(selectinload(relationship_attr))
    return query

def _get_inspection(db: Session, inspection_id: int) -> Inspection | None:
    return _inspection_query(db).filter(Inspection.id == inspection_id).first()

def _resolve_related_inspector_name(inspection: Inspection) -> str | None:
    inspector = getattr(inspection, "responsible_inspector", None)
    if not inspector:
        return None

    for attr in ("full_name", "fullname", "email"):
        value = getattr(inspector, attr, None)
        if value and str(value).strip():
            return str(value).strip()

    return None

def _resolve_inspector_name(inspection: Inspection, fallback_name: str | None = None) -> str | None:
    related_name = _resolve_related_inspector_name(inspection)
    if related_name:
        return related_name

    if fallback_name and fallback_name.strip():
        return fallback_name.strip()

    return None


def sync_productivity_from_inspection_status(
    db: Session,
    inspection_id: int,
) -> InspectionProductivity | None:
    inspection = _get_inspection(db, inspection_id)
    if not inspection:
        return None

    productivity = _ensure_productivity_record(db, inspection)

    productivity.inspector_name = _resolve_inspector_name(inspection, productivity.inspector_name)
    productivity.scheduled_date = _resolve_scheduled_date(inspection)

    normalized_status = (getattr(inspection, "status", None) or "draft").strip().lower()
    productivity.operational_status = INSPECTION_STATUS_TO_OPERATIONAL_STATUS.get(
        normalized_status,
        "pending",
    )

    now = datetime.now(timezone.utc)

    if normalized_status in {"in_review", "observed", "finalized"} and not productivity.report_started_at:
        productivity.report_started_at = now

    if normalized_status == "finalized":
        productivity.report_finished_at = productivity.report_finished_at or now

    if productivity.report_started_at and productivity.report_finished_at:
        duration = productivity.report_finished_at - productivity.report_started_at
        productivity.duration_minutes = round(duration.total_seconds() / 60, 2)
        productivity.met_goal = productivity.duration_minutes <= GOAL_MINUTES

    db.add(productivity)
    db.flush()
    return productivity


def _resolve_scheduled_date(inspection: Inspection) -> date | None:
    return (
        getattr(inspection, "inspection_date", None)
        or getattr(inspection, "inspectiondate", None)
        or getattr(inspection, "scheduled_date", None)
        or getattr(inspection, "scheduleddate", None)
    )

def _ensure_productivity_record(db: Session, inspection: Inspection) -> InspectionProductivity:
    productivity = get_productivity_by_inspection(db, inspection.id)
    if productivity:
        return productivity

    productivity = InspectionProductivity(
        inspection_id=inspection.id,
        inspector_name=_resolve_related_inspector_name(inspection),
        scheduled_date=_resolve_scheduled_date(inspection),
        operational_status="pending",
    )
    db.add(productivity)
    db.flush()
    return productivity


def get_productivity_by_inspection(db: Session, inspection_id: int) -> InspectionProductivity | None:
    return (
        db.query(InspectionProductivity)
        .filter(InspectionProductivity.inspection_id == inspection_id)
        .first()
    )


def create_productivity(db: Session, payload: ProductivityCreate) -> InspectionProductivity:
    inspection = _get_inspection(db, payload.inspection_id)
    if not inspection:
        raise ValueError("Inspection not found")

    existing = get_productivity_by_inspection(db, payload.inspection_id)
    if existing:
        return existing

    productivity = InspectionProductivity(
        inspection_id=payload.inspection_id,
        inspector_name=_resolve_related_inspector_name(inspection, payload.inspector_name),
        scheduled_date=payload.scheduled_date or _resolve_scheduled_date(inspection),
        operational_status=payload.operational_status,
    )
    db.add(productivity)
    db.commit()
    db.refresh(productivity)
    return productivity


def update_productivity(
    db: Session,
    inspection_id: int,
    payload: ProductivityUpdate,
) -> InspectionProductivity | None:
    productivity = get_productivity_by_inspection(db, inspection_id)
    if not productivity:
        return None

    inspection = _get_inspection(db, inspection_id)

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(productivity, key, value)

    if inspection:
        productivity.inspector_name = _resolve_inspector_name(
            inspection,
            productivity.inspector_name,
        )
        productivity.scheduled_date = productivity.scheduled_date or _resolve_scheduled_date(inspection)

    if productivity.report_started_at and productivity.report_finished_at:
        duration = productivity.report_finished_at - productivity.report_started_at
        productivity.duration_minutes = round(duration.total_seconds() / 60, 2)
        productivity.met_goal = productivity.duration_minutes <= GOAL_MINUTES

    db.add(productivity)
    db.commit()
    db.refresh(productivity)
    return productivity


def start_productivity(
        db: Session,
        inspection_id: int,
        started_at: datetime | None = None,
) -> InspectionProductivity:
    inspection = _get_inspection(db, inspection_id)
    if not inspection:
        raise ValueError("Inspection not found")

    productivity = _ensure_productivity_record(db, inspection)

    productivity.inspector_name = _resolve_inspector_name(inspection, productivity. inspector_name)
    productivity.scheduled_date = productivity.scheduled_date or _resolve_scheduled_date(inspection)
    productivity.report_started_at = started_at or datetime.now(timezone.utc)

    if productivity.operational_status == "pending":
        productivity.operational_status = "in_progress"

    db.add(productivity)
    db.commit()
    db.refresh(productivity)
    return productivity


def finish_productivity(
    db: Session,
    inspection_id: int,
    finished_at: datetime | None = None,
    operational_status: str = "completed",
) -> InspectionProductivity:
    inspection = _get_inspection(db, inspection_id)
    if not inspection:
        raise ValueError("Inspection record not found")

    productivity = _ensure_productivity_record(db, inspection)

    now = datetime.now(timezone.utc)
    productivity.inspector_name = _resolve_inspector_name(inspection, productivity.inspector_name)
    productivity.scheduled_date = productivity.scheduled_date or _resolve_scheduled_date(inspection)
    productivity.report_started_at = finished_at or now
    productivity.operational_status = (operational_status or "completed").strip().lower()

    duration = productivity.report_finished_at - productivity.report_started_at
    productivity.duration_minutes = round(duration.total_seconds() / 60, 2)
    productivity.met_goal = productivity.duration_minutes <= GOAL_MINUTES

    db.add(productivity)
    db.commit()
    db.refresh(productivity)
    return productivity


def _apply_productivity_filters(
        query,
        date_from: datetime,
        date_to: datetime | None = None,
        inspector_name: str | None = None,
        operational_status: str | None = None,
):
    if date_from:
        query = query.filter(InspectionProductivity.scheduled_date >= date_from)

    if date_to:
        query = query.filter(InspectionProductivity.scheduled_date <= date_to)

    if inspector_name:
        query = query.filter(InspectionProductivity.inspector_name.ilike(f"%{inspector_name.strip()}%"))

    normalized_status = _normalize_operational_status_filter(operational_status)
    if normalized_status:
        query = query.filter(InspectionProductivity.operational_status == normalized_status)

    return query


def _build_productivity_filters(
    query,
    date_from: date | None = None,
    date_to: date | None = None,
    inspector_name: str | None = None,
    operational_status: str | None = None,
):
    if date_from:
        query = query.filter(InspectionProductivity.scheduled_date >= date_from)
    if date_to:
        query = query.filter(InspectionProductivity.scheduled_date <= date_to)
    if inspector_name:
        query = query.filter(InspectionProductivity.inspector_name == inspector_name)

    normalized_operational_status = _normalize_operational_status_filter(operational_status)
    if normalized_operational_status:
        query = query.filter(
            InspectionProductivity.operational_status == normalized_operational_status
        )

    return query


def get_productivity_summary(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    inspector_name: str | None = None,
    operational_status: str | None = None,
):
    query = _apply_productivity_filters(
        db.query(InspectionProductivity),
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
        operational_status=operational_status,
    )

    total_inspections, completed_reports, average_report_minutes, on_time_count = query.with_entities(
        func.count(InspectionProductivity.id),
        func.sum(case((InspectionProductivity.operational_status == "completed", 1), else_=0)),
        func.avg(InspectionProductivity.duration_minutes),
        func.sum(case((InspectionProductivity.met_goal.is_(True), 1), else_=0)),
    ).one()

    total_inspections = int(total_inspections or 0)
    completed_reports = int(completed_reports or 0)
    average_report_minutes = round(float(average_report_minutes or 0), 2)
    on_time_count = int(on_time_count or 0)
    on_time_percentage = round((on_time_count / completed_reports) * 100, 2) if completed_reports else 0.0

    return {
        "total_inspections": total_inspections,
        "completed_reports": completed_reports,
        "average_report_minutes": average_report_minutes,
        "on_time_count": on_time_count,
        "on_time_percentage": on_time_percentage,
        "goal_minutes": GOAL_MINUTES,
    }


def get_productivity_by_inspector(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    inspector_name: str | None = None,
    operational_status: str | None = None,
):
    query = _apply_productivity_filters(
        db.query(InspectionProductivity),
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
        operational_status=operational_status,
    )

    rows = (
        query.with_entities(
            func.coalesce(InspectionProductivity.inspector_name, "Sin asignar").label("inspector_name"),
            func.count(InspectionProductivity.id).label("assigned_inspections"),
            func.sum(
                case(
                    (InspectionProductivity.operational_status == "completed", 1),
                    else_=0)
            ).label("completed_reports"),
            func.avg(InspectionProductivity.duration_minutes).label("average_report_minutes"),
            func.sum(
                case(
                    (InspectionProductivity.met_goal.is_(True), 1),
                    else_=0,
                )
            ).label("on_time_count"),
        )
        .group_by(InspectionProductivity.inspector_name)
        .order_by(InspectionProductivity.inspector_name.asc())
        .all()
    )

    result = []
    for row in rows:
        completed = int(row.completed_reports or 0)
        on_time = int(row.on_time_count or 0)

        result.append(
            {
                "inspector_name": row.inspector_name,
                "assigned_inspections": int(row.assigned_inspections or 0),
                "completed_reports": completed,
                "average_report_minutes": round(float(row.average_report_minutes or 0), 2),
                "on_time_count": on_time,
                "on_time_percentage": round((on_time / completed) * 100, 2) if completed else 0.0,
            }
        )

    return result


def get_productivity_by_status(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    inspector_name: str | None = None,
):
    query = _apply_productivity_filters(
        db.query(InspectionProductivity),
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
        operational_status=None,
    )

    rows = (
        query.with_entities(
            InspectionProductivity.operational_status,
            func.count(InspectionProductivity.id).label("count"),
        )
        .group_by(InspectionProductivity.operational_status)
        .order_by(InspectionProductivity.operational_status.asc())
        .all()
    )

    return [
        {
            "operational_status": row.operational_status,
            "count": int(row.count or 0),
        }
        for row in rows
    ]


def get_productivity_dashboard(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    inspector_name: str | None = None,
    operational_status: str | None = None,
):
    return {
        "summary": get_productivity_summary(
            db,
            date_from=date_from,
            date_to=date_to,
            inspector_name=inspector_name,
            operational_status=operational_status,
        ),
        "by_inspector": get_productivity_by_inspector(
            db,
            date_from=date_from,
            date_to=date_to,
            inspector_name=inspector_name,
            operational_status=operational_status,
        ),
        "by_status": get_productivity_by_status(
            db,
            date_from=date_from,
            date_to=date_to,
            inspector_name=inspector_name,
        ),
    }