from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, tecnico, todos
from app.db.models.users import User
from app.schemas.report_status import (
    ReportStatusLogResponse,
    ReportStatusResponse,
    ReportStatusUpdateRequest,
    StatusTransitionRequest,
    StatusTransitionResponse,
)
from app.services.productivity_service import get_productivity_by_inspection
from app.services.report_status_service import (
    change_report_status,
    get_report_or_404,
    list_report_history,
    transition_inspection_status,
)

router = APIRouter(prefix="/reports", tags=["report-status"])
inspection_status_router = APIRouter(prefix="/inspections", tags=["report-status"])

@router.get("/{report_draft_id}/status", response_model=ReportStatusResponse)
def get_status(
    report_draft_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(todos),
):
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
    current_user: User = Depends(tecnico),
):
    report = change_report_status(
        db=db,
        report_draft_id=report_draft_id,
        new_status=payload.status,
        actor=current_user,
        notes=payload.notes,
    )
    return ReportStatusResponse(
        report_draft_id=report.id,
        status=report.status,
        status_updated_at=report.status_updated_at,
        status_updated_by=report.status_updated_by,
        last_action=report.last_action,
    )


@inspection_status_router.post(
    "/{inspection_id}/status-transition",
    response_model=StatusTransitionResponse,
)
def transition_status(
    inspection_id: int,
    payload: StatusTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(tecnico),
):
    updated_report, previous_status = transition_inspection_status(
        db=db,
        inspection_id=inspection_id,
        to_status=payload.to_status,
        actor=current_user,
        notes=payload.notes,
    )
    productivity = get_productivity_by_inspection(db, inspection_id)
    return StatusTransitionResponse(
        inspection_id=inspection_id,
        report_draft_id=updated_report.id,
        from_status=previous_status,
        status=updated_report.status,
        status_updated_at=updated_report.status_updated_at,
        status_updated_by=updated_report.status_updated_by,
        last_action=updated_report.last_action,
        operational_status=productivity.operational_status if productivity else None,
    )


@router.get("/{report_draft_id}/history", response_model=list[ReportStatusLogResponse])
def get_history(
    report_draft_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(todos),
):
    return list_report_history(db, report_draft_id, limit=limit)