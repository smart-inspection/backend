from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.report_export_service import (
    export_report_docx,
    export_report_pdf,
)

router = APIRouter(prefix="/report-export", tags=["report-export"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_file_response(file_path: Path, media_type: str):
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo exportado no encontrado")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type,
    )


@router.get("/docx/{draft_id}")
def export_report_docx_endpoint(draft_id: int, db: Session = Depends(get_db)):
    try:
        file_path = Path(export_report_docx(db, draft_id))
        return _build_file_response(
            file_path,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al exportar DOCX: {str(exc)}")


@router.get("/pdf/{draft_id}")
def export_report_pdf_endpoint(draft_id: int, db: Session = Depends(get_db)):
    try:
        file_path = Path(export_report_pdf(db, draft_id))
        return _build_file_response(file_path, "application/pdf")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al exportar PDF: {str(exc)}")