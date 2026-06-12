from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.productivity import (
    ProductivityCreate,
    ProductivityFinishRequest,
    ProductivityResponse,
    ProductivityStartRequest,
    ProductivityUpdate,
    ProductivityByInspectorItem,
    ProductivityDashboardResponse,
    ProductivityStatusItem,
    ProductivitySummaryResponse,
)
from app.services.productivity_service import (
    create_productivity,
    finish_productivity,
    get_productivity_by_inspection,
    start_productivity,
    update_productivity,
    get_productivity_by_inspector,
    get_productivity_by_status,
    get_productivity_dashboard,
    get_productivity_summary,
)

from datetime import date
from fastapi import Query

router = APIRouter(prefix="/productivity", tags=["productivity"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ProductivityResponse, status_code=201)
def create_productivity_endpoint(payload: ProductivityCreate, db: Session = Depends(get_db)):
    try:
        return create_productivity(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/inspection/{inspection_id}", response_model=ProductivityResponse)
def get_productivity_endpoint(inspection_id: int, db: Session = Depends(get_db)):
    productivity = get_productivity_by_inspection(db, inspection_id)
    if not productivity:
        raise HTTPException(status_code=404, detail="Productivity record not found")
    return productivity


@router.put("/inspection/{inspection_id}", response_model=ProductivityResponse)
def update_productivity_endpoint(
    inspection_id: int,
    payload: ProductivityUpdate,
    db: Session = Depends(get_db),
):
    productivity = update_productivity(db, inspection_id, payload)
    if not productivity:
        raise HTTPException(status_code=404, detail="Productivity record not found")
    return productivity


@router.patch("/inspection/{inspection_id}/start", response_model=ProductivityResponse)
def start_productivity_endpoint(
    inspection_id: int,
    payload: ProductivityStartRequest,
    db: Session = Depends(get_db),
):
    try:
        return start_productivity(db, inspection_id, payload.report_started_at)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/inspection/{inspection_id}/finish", response_model=ProductivityResponse)
def finish_productivity_endpoint(
    inspection_id: int,
    payload: ProductivityFinishRequest,
    db: Session = Depends(get_db),
):
    try:
        return finish_productivity(
            db,
            inspection_id,
            payload.report_finished_at,
            payload.operational_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get("/summary", response_model=ProductivitySummaryResponse)
def get_productivity_summary_endpoint(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inspector_name: str | None = Query(default=None),
    operational_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_productivity_summary(
        db,
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
        operational_status=operational_status,
    )


@router.get("/by-inspector", response_model=list[ProductivityByInspectorItem])
def get_productivity_by_inspector_endpoint(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inspector_name: str | None = Query(default=None),
    operational_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_productivity_by_inspector(
        db,
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
        operational_status=operational_status,
    )


@router.get("/by-status", response_model=list[ProductivityStatusItem])
def get_productivity_by_status_endpoint(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inspector_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_productivity_by_status(
        db,
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
    )


@router.get("/dashboard", response_model=ProductivityDashboardResponse)
def get_productivity_dashboard_endpoint(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inspector_name: str | None = Query(default=None),
    operational_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_productivity_dashboard(
        db,
        date_from=date_from,
        date_to=date_to,
        inspector_name=inspector_name,
        operational_status=operational_status,
    )