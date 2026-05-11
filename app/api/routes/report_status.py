from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.report_status import (
    ReportStatusLogResponse,
    ReportStatusResponse,
    ReportStatusUpdateRequest,
)
from app.services.report_status_service import (
    change_report_status,
    get_report_or_404,
    list_report_history,
)

router = APIRouter(prefix="/reports", tags=["report-status"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/{report_draft_id}/status", response_model=ReportStatusResponse)
def get_status(report_draft_id: int, db: Session = Depends(get_db)):
    report = get_report_or_404(db, report_draft_id)
    return ReportStatusResponse(
        report_draft_id=report.id,
        status=report.status,
        status_updated_at=report.status_updated_at,
        status_updated_by=report.status_updated_by,
        last_action=report.last_action,
    )


@router.patch("/{report_draft_id}/status", response_model=ReportStatusResponse)
def update_status(
    report_draft_id: int,
    payload: ReportStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    report = change_report_status(
        db=db,
        report_draft_id=report_draft_id,
        new_status=payload.status,
        notes=payload.notes,
        actor_user_id=None,
        actor_name="system",
    )
    return ReportStatusResponse(
        report_draft_id=report.id,
        status=report.status,
        status_updated_at=report.status_updated_at,
        status_updated_by=report.status_updated_by,
        last_action=report.last_action,
    )


@router.get("/{report_draft_id}/history", response_model=list[ReportStatusLogResponse])
def get_history(
    report_draft_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return list_report_history(db, report_draft_id, limit=limit)