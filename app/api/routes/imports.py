from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.db.models.users import User
from app.schemas.imports import (
    docx_import_preview_response,
    historical_import_response,
)
from app.services.docx_import_service import preview_docx_report
from app.services.historical_import_service import import_historical_docx

router = APIRouter(prefix="/imports", tags=["imports"])


def _persist_temp_file(upload_file: UploadFile) -> Path:
    suffix = Path(upload_file.filename or "report.docx").suffix or ".docx"
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(upload_file.file.read())
        return Path(temp_file.name)


@router.post("/docx/preview", response_model=docx_import_preview_response)
def preview_docx_import(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .docx")

    temp_path = _persist_temp_file(file)
    try:
        return preview_docx_report(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/docx/import", response_model=historical_import_response)
def import_docx_report(
    file: UploadFile = File(...),
    generate_llm_draft: bool = Form(True),
    requested_by_email: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .docx")

    temp_path = _persist_temp_file(file)
    try:
        normalized_requested_by_email = (
            requested_by_email.strip()
            if requested_by_email and requested_by_email.strip().lower() not in {"string", "null", "undefined"}
            else current_user.email
        )

        return import_historical_docx(
            db=db,
            filepath=temp_path,
            requested_by_email=normalized_requested_by_email,
            generate_llm_draft=generate_llm_draft,
        )
    finally:
        temp_path.unlink(missing_ok=True)