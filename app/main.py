from fastapi import FastAPI

from app.core.config import settings
from app.db.base import Base
from app.db.models import Inspection
from app.db.session import engine
from app.api.routes.health import router as health_router
from app.api.routes.inspections import router as inspections_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(health_router, prefix=settings.health.prefix)
app.include_router(inspections_router, prefix=settings.api_v1_prefix)

@app.get("/")
def root():
    return {
        "message": settings.app_name,
        "env": settings.app_env
    }
