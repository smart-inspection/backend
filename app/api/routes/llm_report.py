from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.report_draft import LLMReportGenerateRequest, ReportDraftResponse
from app.services.llm_report_service import generate_llm_report_draft

router = APIRouter(prefix="/llm-report", tags=["llm-report"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/generate/{inspection_id}", response_model=ReportDraftResponse, status_code=201)
def generate_llm_report_endpoint(
    inspection_id: int,
    payload: LLMReportGenerateRequest,
    db: Session = Depends(get_db),
):
    try:
        return generate_llm_report_draft(db, inspection_id, payload.template_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar informe con LLM: {exc}")