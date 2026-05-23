from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.report_draft import (
    ReportDraftGenerateRequest,
    ReportDraftResponse,
    ReportDraftUpdate,
)
from app.services.report_draft_service import (
    generate_report_draft,
    get_report_draft_by_id,
    list_report_drafts_by_inspection,
    update_report_draft,
)

router = APIRouter(prefix="/report-drafts", tags=["report-drafts"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/generate/{inspection_id}", response_model=ReportDraftResponse, status_code=201)
def generate_report_draft_endpoint(
    inspection_id: int,
    payload: ReportDraftGenerateRequest,
    db: Session = Depends(get_db),
):
    try:
        return generate_report_draft(db, inspection_id, payload.template_version)
    except ValueError as exc:
        if str(exc) == "Inspection not found":
            raise HTTPException(status_code=404, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar borrador: {exc}")

@router.get("/inspection/{inspection_id}", response_model=list[ReportDraftResponse])
def list_report_drafts_by_inspection_endpoint(inspection_id: int, db: Session = Depends(get_db)):
    return list_report_drafts_by_inspection(db, inspection_id)


@router.get("/{draft_id}", response_model=ReportDraftResponse)
def get_report_draft_endpoint(draft_id: int, db: Session = Depends(get_db)):
    draft = get_report_draft_by_id(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Report draft not found")
    return draft


@router.put("/{draft_id}", response_model=ReportDraftResponse)
def update_report_draft_endpoint(
    draft_id: int,
    payload: ReportDraftUpdate,
    db: Session = Depends(get_db),
):
    draft = update_report_draft(db, draft_id, payload.edited_text, payload.status)
    if not draft:
        raise HTTPException(status_code=404, detail="Report draft not found")
    return draft
