from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, tecnico
from app.db.models.users import User
from app.schemas.report_draft import LLMReportGenerateRequest, ReportDraftResponse
from app.services.llm_report_service import generate_llm_report_draft

router = APIRouter(prefix="/llm-report", tags=["llm-report"])

@router.post("/generate/{inspection_id}", response_model=ReportDraftResponse, status_code=201)
def generate_llm_report_endpoint(
    inspection_id: int,
    payload: LLMReportGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(tecnico),
):
    try:
        return generate_llm_report_draft(db, inspection_id, payload.template_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al generar informe con LLM: {exc}")