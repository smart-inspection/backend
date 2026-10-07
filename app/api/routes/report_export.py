from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, todos_flexible
from app.db.models.report_draft import ReportDraft
from app.db.models.users import User
from app.services.report_export_service import (
    export_report_docx,
    export_report_pdf,
)

router = APIRouter(prefix="/report-export", tags=["report-export"])


def _build_file_response(file_path: Path, media_type: str):
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo exportado no encontrado")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{file_path.name}"'},
    )


def _resolve_draft_id(db: Session, target_id: int) -> int:
    draft = db.query(ReportDraft).filter(ReportDraft.id == target_id).first()
    if draft:
        return draft.id

    draft_by_inspection = (
        db.query(ReportDraft)
        .filter(ReportDraft.inspection_id == target_id)
        .order_by(ReportDraft.created_at.desc(), ReportDraft.id.desc())
        .first()
    )
    if draft_by_inspection:
        return draft_by_inspection.id

    return target_id


@router.get("/docx/{inspection_id}")
def export_report_docx_endpoint(
    inspection_id: int,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(todos_flexible),
):
    try:
        draft_id = _resolve_draft_id(db, inspection_id)
        file_path = Path(export_report_docx(db, draft_id))
        return _build_file_response(
            file_path,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al exportar DOCX: {str(exc)}")


@router.get("/pdf/{inspection_id}")
def export_report_pdf_endpoint(
    inspection_id: int,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(todos_flexible),
):
    try:
        draft_id = _resolve_draft_id(db, inspection_id)
        file_path = Path(export_report_pdf(db, draft_id))
        return _build_file_response(file_path, "application/pdf")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al exportar PDF: {str(exc)}")