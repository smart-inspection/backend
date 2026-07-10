from datetime import date, datetime, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.db.models import Inspection, InspectionProductivity
from app.schemas.productivity import ProductivityCreate, ProductivityUpdate

def normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)

GOAL_MINUTES = 20

VALID_OPERATIONAL_STATUSES = {
    "pending",
    "scheduled",
    "in_progress",
    "completed",
    "blocked",
    "cancelled",
}

INSPECTION_STATUS_TO_OPERATIONAL_STATUS = {
    "draft": "pending",
    "in_review": "in_progress",
    "observed": "blocked",
    "finalized": "completed",
}


def _normalize_operational_status_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalize_operational_status(value: str | None, default: str = "pending") -> str:
    normalized = _normalize_operational_status_filter(value)
    if not normalized:
        return default
    if normalized not in VALID_OPERATIONAL_STATUSES:
        raise ValueError(f"Invalid operational status: {normalized}")
    return normalized


def _get_inspection(db: Session, inspection_id: int) -> Inspection | None:
    return (
        db.query(Inspection)
        .options(selectinload(Inspection.responsible_inspector))
        .filter(Inspection.id == inspection_id)
        .first()
    )


def _resolve_related_inspector_name(
    inspection: Inspection,
    fallback_name: str | None = None,
) -> str | None:
    responsible_inspector = getattr(inspection, "responsible_inspector", None)
    if responsible_inspector and getattr(responsible_inspector, "full_name", None):
        full_name = responsible_inspector.full_name.strip()
        if full_name:
            return full_name

    if fallback_name and fallback_name.strip():
        return fallback_name.strip()

    return None


def _resolve_scheduled_date(inspection: Inspection) -> date | None:
    return (
        getattr(inspection, "inspection_date", None)
        or getattr(inspection, "inspectiondate", None)
        or getattr(inspection, "scheduled_date", None)
        or getattr(inspection, "scheduleddate", None)
    )


def _sync_productivity_from_inspection(
    productivity: InspectionProductivity,
    inspection: Inspection,
    fallback_name: str | None = None,
) -> None:
    productivity.inspector_name = _resolve_related_inspector_name(
        inspection,
        fallback_name or productivity.inspector_name,
    )
    productivity.scheduled_date = productivity.scheduled_date or _resolve_scheduled_date(inspection)


def _recalculate_productivity(
    productivity: InspectionProductivity,
) -> float | None:
    report_started_at = normalize_utc_datetime(
        productivity.report_started_at,
    )
    report_finished_at = normalize_utc_datetime(
        productivity.report_finished_at,
    )

    productivity.report_started_at = report_started_at
    productivity.report_finished_at = report_finished_at

    if report_started_at and report_finished_at:
        elapsed_seconds = (
            report_finished_at - report_started_at
        ).total_seconds()

        productivity.duration_minutes = round(
            max(elapsed_seconds, 0) / 60,
            2,
        )
        productivity.met_goal = productivity.duration_minutes <= GOAL_MINUTES

        return productivity.duration_minutes

    productivity.duration_minutes = None
    productivity.met_goal = None

    return None


def get_productivity_by_inspection(
    db: Session,
    inspection_id: int,
) -> InspectionProductivity | None:
    return (
        db.query(InspectionProductivity)
        .filter(InspectionProductivity.inspection_id == inspection_id)
        .first()
    )


def _ensure_productivity_record(
    db: Session,
    inspection: Inspection,
) -> InspectionProductivity:
    productivity = get_productivity_by_inspection(db, inspection.id)
    if productivity:
        _sync_productivity_from_inspection(productivity, inspection)
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


def create_productivity(db: Session, payload: ProductivityCreate) -> InspectionProductivity:
    inspection = _get_inspection(db, payload.inspection_id)
    if not inspection:
        raise ValueError("Inspection not found")

    existing = get_productivity_by_inspection(db, payload.inspection_id)
    if existing:
        _sync_productivity_from_inspection(existing, inspection, payload.inspector_name)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    productivity = InspectionProductivity(
        inspection_id=payload.inspection_id,
        inspector_name=_resolve_related_inspector_name(inspection, payload.inspector_name),
        scheduled_date=payload.scheduled_date or _resolve_scheduled_date(inspection),
        report_started_at=payload.report_started_at,
        report_finished_at=payload.report_finished_at,
        operational_status=_normalize_operational_status(payload.operational_status, "pending"),
        met_goal=payload.met_goal,
    )

    _recalculate_productivity(productivity)

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

    if "operational_status" in data:
        data["operational_status"] = _normalize_operational_status(
            data["operational_status"],
            productivity.operational_status or "pending",
        )

    for key, value in data.items():
        setattr(productivity, key, value)

    if inspection:
        _sync_productivity_from_inspection(
            productivity,
            inspection,
            payload.inspector_name,
        )

    _recalculate_productivity(productivity)

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
    started_timestamp = started_at or datetime.now(timezone.utc)

    _sync_productivity_from_inspection(productivity, inspection)
    productivity.report_started_at = started_timestamp

    if (
        productivity.report_finished_at is not None
        and productivity.report_finished_at < productivity.report_started_at
    ):
        productivity.report_finished_at = None

    if productivity.operational_status in {"pending", "scheduled"}:
        productivity.operational_status = "in_progress"

    _recalculate_productivity(productivity)

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
        raise ValueError("Inspection not found")

    productivity = _ensure_productivity_record(db, inspection)
    finished_timestamp = normalize_utc_datetime(
        finished_at or datetime.now(timezone.utc),
    )

    _sync_productivity_from_inspection(productivity, inspection)

    report_started_at = normalize_utc_datetime(
        productivity.report_started_at,
    )

    if report_started_at is None:
        report_started_at = finished_timestamp

    productivity.report_started_at = report_started_at
    productivity.report_finished_at = finished_timestamp

    if productivity.report_finished_at < productivity.report_started_at:
        productivity.report_finished_at = productivity.report_started_at

    productivity.operational_status = _normalize_operational_status(
        operational_status,
        "completed",
    )

    _recalculate_productivity(productivity)

    db.add(productivity)
    db.commit()
    db.refresh(productivity)

    return productivity


def _apply_productivity_filters(
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

    if inspector_name and inspector_name.strip():
        query = query.filter(
            InspectionProductivity.inspector_name.ilike(f"%{inspector_name.strip()}%")
        )

    normalized_status = _normalize_operational_status_filter(operational_status)
    if normalized_status:
        query = query.filter(
            InspectionProductivity.operational_status == normalized_status
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

    total_inspections, completed_reports, average_report_minutes, on_time_count = (
        query.with_entities(
            func.count(InspectionProductivity.id),
            func.sum(
                case(
                    (InspectionProductivity.operational_status == "completed", 1),
                    else_=0,
                )
            ),
            func.avg(InspectionProductivity.duration_minutes),
            func.sum(
                case(
                    (InspectionProductivity.met_goal.is_(True), 1),
                    else_=0,
                )
            ),
        ).one()
    )

    total_inspections = int(total_inspections or 0)
    completed_reports = int(completed_reports or 0)
    average_report_minutes = round(float(average_report_minutes or 0), 2)
    on_time_count = int(on_time_count or 0)
    on_time_percentage = (
        round((on_time_count / completed_reports) * 100, 2)
        if completed_reports
        else 0.0
    )

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
            func.coalesce(
                InspectionProductivity.inspector_name,
                "Sin asignar",
            ).label("inspector_name"),
            func.count(InspectionProductivity.id).label("assigned_inspections"),
            func.sum(
                case(
                    (InspectionProductivity.operational_status == "completed", 1),
                    else_=0,
                )
            ).label("completed_reports"),
            func.avg(InspectionProductivity.duration_minutes).label(
                "average_report_minutes"
            ),
            func.sum(
                case(
                    (InspectionProductivity.met_goal.is_(True), 1),
                    else_=0,
                )
            ).label("on_time_count"),
        )
        .group_by(InspectionProductivity.inspector_name)
        .order_by(func.coalesce(InspectionProductivity.inspector_name, "Sin asignar").asc())
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
                "average_report_minutes": round(
                    float(row.average_report_minutes or 0),
                    2,
                ),
                "on_time_count": on_time,
                "on_time_percentage": round((on_time / completed) * 100, 2)
                if completed
                else 0.0,
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

def sync_productivity_from_inspection_status(
    db: Session,
    inspection_id: int,
) -> InspectionProductivity | None:
    inspection = _get_inspection(db, inspection_id)
    if not inspection:
        return None

    productivity = _ensure_productivity_record(db, inspection)
    _sync_productivity_from_inspection(productivity, inspection)

    normalized_status = (getattr(inspection, "status", None) or "draft").strip().lower()
    mapped_status = INSPECTION_STATUS_TO_OPERATIONAL_STATUS.get(normalized_status, "pending")
    productivity.operational_status = mapped_status

    now = datetime.now(timezone.utc)

    if normalized_status in {"in_review", "observed", "finalized"} and productivity.report_started_at is None:
        productivity.report_started_at = now

    if normalized_status == "finalized" and productivity.report_finished_at is None:
        productivity.report_finished_at = now

    report_started_at = normalize_utc_datetime(
        productivity.report_started_at,
    )
    report_finished_at = normalize_utc_datetime(
        productivity.report_finished_at,
    )

    productivity.report_started_at = report_started_at
    productivity.report_finished_at = report_finished_at

    if (
            report_started_at is not None
            and report_finished_at is not None
            and report_finished_at < report_started_at
    ):
        productivity.report_finished_at = report_started_at

    _recalculate_productivity(productivity)

    db.add(productivity)
    db.flush()
    return productivity