from datetime import datetime, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models import Inspection, InspectionProductivity
from app.schemas.productivity import ProductivityCreate, ProductivityUpdate


GOAL_MINUTES = 20

INSPECTION_STATUS_TO_OPERATIONAL_STATUS = {
    "draft": "pending",
    "in_review": "in_progress",
    "observed": "observed",
    "finalized": "completed",
}


def sync_productivity_from_inspection_status(
    db: Session,
    inspection_id: int,
) -> InspectionProductivity | None:
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        return None

    productivity = get_productivity_by_inspection(db, inspection_id)

    if not productivity:
        productivity = InspectionProductivity(
            inspection_id=inspection_id,
            inspector_name=getattr(inspection, "responsible_inspector", None),
            scheduled_date=getattr(inspection, "inspection_date", None),
            operational_status="pending",
        )

    normalized_status = (inspection.status or "draft").strip().lower()
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


def _resolve_inspector_name(inspection: Inspection) -> str | None:
    return (
        getattr(inspection, "responsible_inspector", None)
        or getattr(inspection, "inspector_name", None)
        or getattr(inspection, "responsibleinspector", None)
    )


def _resolve_scheduled_date(inspection: Inspection):
    return (
        getattr(inspection, "scheduled_date", None)
        or getattr(inspection, "inspection_date", None)
        or getattr(inspection, "inspectiondate", None)
    )


def get_productivity_by_inspection(db: Session, inspection_id: int) -> InspectionProductivity | None:
    return (
        db.query(InspectionProductivity)
        .filter(InspectionProductivity.inspection_id == inspection_id)
        .first()
    )


def create_productivity(db: Session, payload: ProductivityCreate) -> InspectionProductivity:
    inspection = db.query(Inspection).filter(Inspection.id == payload.inspection_id).first()
    if not inspection:
        raise ValueError("Inspection not found")

    existing = get_productivity_by_inspection(db, payload.inspection_id)
    if existing:
        return existing

    productivity = InspectionProductivity(
        inspection_id=payload.inspection_id,
        inspector_name=payload.inspector_name or inspection.responsible_inspector,
        scheduled_date=payload.scheduled_date or inspection.scheduled_date,
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

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(productivity, key, value)

    if productivity.report_started_at and productivity.report_finished_at:
        duration = productivity.report_finished_at - productivity.report_started_at
        productivity.duration_minutes = round(duration.total_seconds() / 60, 2)
        productivity.met_goal = productivity.duration_minutes <= GOAL_MINUTES

    db.add(productivity)
    db.commit()
    db.refresh(productivity)
    return productivity


def start_productivity(db: Session, inspection_id: int, started_at: datetime | None = None) -> InspectionProductivity:
    productivity = get_productivity_by_inspection(db, inspection_id)
    if not productivity:
        inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
        if not inspection:
            raise ValueError("Inspection not found")

        productivity = InspectionProductivity(
            inspection_id=inspection_id,
            inspector_name=inspection.responsible_inspector,
            scheduled_date=inspection.inspection_date,
            operational_status="in_progress",
            report_started_at=started_at or datetime.now(timezone.utc),
        )
        db.add(productivity)
        db.commit()
        db.refresh(productivity)
        return productivity

    productivity.report_started_at = started_at or datetime.now(timezone.utc)
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
    productivity = get_productivity_by_inspection(db, inspection_id)
    if not productivity:
        raise ValueError("Productivity record not found")

    if not productivity.report_started_at:
        productivity.report_started_at = datetime.now(timezone.utc)

    productivity.report_finished_at = finished_at or datetime.now(timezone.utc)
    productivity.operational_status = operational_status

    duration = productivity.report_finished_at - productivity.report_started_at
    productivity.duration_minutes = round(duration.total_seconds() / 60, 2)
    productivity.met_goal = productivity.duration_minutes <= GOAL_MINUTES

    db.add(productivity)
    db.commit()
    db.refresh(productivity)
    return productivity

from datetime import date
from sqlalchemy import func


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
    if operational_status:
        query = query.filter(InspectionProductivity.operational_status == operational_status)
    return query


def get_productivity_summary(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    inspector_name: str | None = None,
    operational_status: str | None = None,
) -> dict:
    query = db.query(InspectionProductivity)
    query = _build_productivity_filters(
        query,
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
        operational_status=operational_status,
    )

    records = query.all()
    total_inspections = len(records)
    completed = [item for item in records if item.report_finished_at is not None]
    completed_reports = len(completed)

    durations = [float(item.duration_minutes) for item in completed if item.duration_minutes is not None]
    average_report_minutes = round(sum(durations) / len(durations), 2) if durations else 0.0

    on_time_count = len([item for item in completed if item.met_goal is True])
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
) -> list[dict]:
    query = db.query(InspectionProductivity)
    query = _build_productivity_filters(
        query,
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
                    (InspectionProductivity.report_finished_at.is_not(None), 1),
                    else_=0,
                )
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
        completed_reports = int(row.completed_reports or 0)
        on_time_count = int(row.on_time_count or 0)
        on_time_percentage = round((on_time_count / completed_reports) * 100, 2) if completed_reports else 0.0

        result.append(
            {
                "inspector_name": row.inspector_name,
                "assigned_inspections": int(row.assigned_inspections or 0),
                "completed_reports": completed_reports,
                "average_report_minutes": round(float(row.average_report_minutes or 0), 2),
                "on_time_count": on_time_count,
                "on_time_percentage": on_time_percentage,
            }
        )

    return result


def get_productivity_by_status(
    db: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    inspector_name: str | None = None,
) -> list[dict]:
    query = db.query(InspectionProductivity)
    query = _build_productivity_filters(
        query,
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
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
) -> dict:
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