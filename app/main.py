from pathlib import Path

from fastapi import FastAPI, Request
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
from app.api.routes.report_status import inspection_status_router
from app.api.routes.inspection_enrichment import router as inspection_enrichment_router
from app.api.routes.productivity import router as productivity_router
from app.api.routes.inspection_requests import router as inspection_requests_router
from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.api.routes.imports import router as import_router

import logging
from contextlib import asynccontextmanager
from codecarbon import OfflineEmissionsTracker

from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

tracker = OfflineEmissionsTracker(
    country_iso_code="PER",
    project_name="smart-inspection-backend",
    output_dir="./metrics/carbon",
    measure_power_secs=15,
    log_level="warning",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        tracker.start()
    except Exception as exc:
        logger.warning("No se pudo iniciar CodeCarbon tracker en lifespan: %s", exc)
    try:
        yield
    finally:
        try:
            tracker.stop()
        except Exception as exc:
            logger.warning("Error al detener CodeCarbon tracker en lifespan: %s", exc)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)


@app.middleware("http")
async def normalize_api_v1_path(request: Request, call_next):
    path = request.scope.get("path", "")
    prefix = settings.api_v1_prefix.rstrip("/")
    if path.startswith(prefix) and not path.startswith(f"{prefix}/"):
        normalized = f"{prefix}/{path[len(prefix):].lstrip('/')}"
        request.scope["path"] = normalized
        request.scope["raw_path"] = normalized.encode("latin-1")
    return await call_next(request)


Path("uploads").mkdir(parents=True, exist_ok=True)

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(users_router, prefix=settings.api_v1_prefix)
app.include_router(inspections_router, prefix=settings.api_v1_prefix)
app.include_router(inspection_fields_router, prefix=settings.api_v1_prefix)
app.include_router(evidences_router, prefix=settings.api_v1_prefix)
app.include_router(ocr_router, prefix=settings.api_v1_prefix)
app.include_router(transcription_router, prefix=settings.api_v1_prefix)
app.include_router(report_draft_router, prefix=settings.api_v1_prefix)
app.include_router(llm_report_router, prefix=settings.api_v1_prefix)
app.include_router(report_export_router, prefix=settings.api_v1_prefix)
app.include_router(report_status_router, prefix=settings.api_v1_prefix)
app.include_router(inspection_status_router, prefix=settings.api_v1_prefix)
app.include_router(inspection_enrichment_router, prefix=settings.api_v1_prefix)
app.include_router(productivity_router, prefix=settings.api_v1_prefix)
app.include_router(inspection_requests_router, prefix=settings.api_v1_prefix)
app.include_router(import_router, prefix=settings.api_v1_prefix)

app.mount(f"{settings.api_v1_prefix}/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "https://smart-inspection-gs.netlify.app",
        "https://smartinspection.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["root"])
def root():
    return {
        "message": settings.app_name,
        "env": settings.app_env
    }