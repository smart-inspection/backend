from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.core.config import settings
from app.db.base import Base
from app.db import models
from app.db.session import engine
from app.api.routes.health import router as health_router
from app.api.routes.inspections import router as inspections_router
from app.api.routes.inspection_fields import router as inspection_fields_router
from app.api.routes.evidences import router as evidences_router
from app.api.routes.ocr import router as ocr_router
from app.api.routes.transcription import router as transcription_router
from app.api.routes.report_draft import router as report_draft_router
from app.api.routes.llm_report import router as llm_report_router
from app.api.routes.report_export import router as report_export_router
from app.api.routes.report_status import router as report_status_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug
)

Path("uploads").mkdir(parents=True, exist_ok=True)

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(inspections_router, prefix=settings.api_v1_prefix)
app.include_router(inspection_fields_router, prefix=settings.api_v1_prefix)
app.include_router(evidences_router, prefix=settings.api_v1_prefix)
app.include_router(ocr_router, prefix=settings.api_v1_prefix)
app.include_router(transcription_router, prefix=settings.api_v1_prefix)
app.include_router(report_draft_router, prefix=settings.api_v1_prefix)
app.include_router(llm_report_router, prefix=settings.api_v1_prefix)
app.include_router(report_export_router, prefix=settings.api_v1_prefix)
app.include_router(report_status_router, prefix=settings.api_v1_prefix)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/", tags=["root"])
def root():
    return {
        "message": settings.app_name,
        "env": settings.app_env
    }