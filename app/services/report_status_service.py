from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import ReportDraft, ReportStatusLog

REPORT_STATUS_DRAFT = "draft"
REPORT_STATUS_IN_REVIEW = "in_review"
REPORT_STATUS_OBSERVED = "observed"
REPORT_STATUS_FINALIZED = "finalized"

ALLOWED_TRANSITIONS = {
    REPORT_STATUS_DRAFT: {REPORT_STATUS_IN_REVIEW, REPORT_STATUS_OBSERVED},
    REPORT_STATUS_IN_REVIEW: {REPORT_STATUS_OBSERVED, REPORT_STATUS_FINALIZED},
    REPORT_STATUS_OBSERVED: {REPORT_STATUS_IN_REVIEW, REPORT_STATUS_FINALIZED},
    REPORT_STATUS_FINALIZED: set(),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_report_or_404(db: Session, report_draft_id: int) -> ReportDraft:
    report = db.query(ReportDraft).filter(ReportDraft.id == report_draft_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report draft not found")
    return report


def validate_status_transition(current_status: str, new_status: str) -> None:
    current = (current_status or REPORT_STATUS_DRAFT).strip().lower()
    target = (new_status or "").strip().lower()

    if current == target:
        return

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition: {current} -> {target}",
        )


def register_report_event(
    db: Session,
    report_draft: ReportDraft,
    action: str,
    actor_user_id: int | None = None,
    actor_name: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    notes: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> ReportStatusLog:
    log = ReportStatusLog(
        report_draft_id=report_draft.id,
        inspection_id=report_draft.inspection_id,
        from_status=from_status,
        to_status=to_status,
        action=action,
        actor_user_id=actor_user_id,
        actor_name=actor_name,
        notes=notes,
        metadata_json=metadata_json,
    )
    db.add(log)
    return log


def change_report_status(
    db: Session,
    report_draft_id: int,
    new_status: str,
    actor_user_id: int | None = None,
    actor_name: str | None = None,
    notes: str | None = None,
) -> ReportDraft:
    report = get_report_or_404(db, report_draft_id)
    current_status = (report.status or REPORT_STATUS_DRAFT).lower()
    target_status = new_status.strip().lower()

    validate_status_transition(current_status, target_status)

    if current_status != target_status:
        report.status = target_status
        report.status_updated_at = _utcnow()
        report.status_updated_by = actor_user_id
        report.last_action = "status_changed"

        register_report_event(
            db=db,
            report_draft=report,
            action="status_changed",
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            from_status=current_status,
            to_status=target_status,
            notes=notes,
        )

    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_report_history(db: Session, report_draft_id: int, limit: int = 50) -> list[ReportStatusLog]:
    get_report_or_404(db, report_draft_id)

    return (
        db.query(ReportStatusLog)
        .filter(ReportStatusLog.report_draft_id == report_draft_id)
        .order_by(ReportStatusLog.created_at.desc(), ReportStatusLog.id.desc())
        .limit(limit)
        .all()
    )