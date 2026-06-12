from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.inspection import InspectionCreate, InspectionResponse
from app.services.inspection_service import (
    create_inspection,
    get_inspection_by_id,
    list_inspections,
)

router = APIRouter(prefix="/inspections", tags=["inspections"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=InspectionResponse, status_code=201)
def create_inspection_endpoint(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_inspection(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[InspectionResponse])
def list_inspections_endpoint(
    db: Session = Depends(get_db),
):
    return list_inspections(db)


@router.get("/{inspection_id}", response_model=InspectionResponse)
def get_inspection_endpoint(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    inspection = get_inspection_by_id(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection