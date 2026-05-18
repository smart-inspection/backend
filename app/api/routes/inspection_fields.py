from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.inspection_field import InspectionFieldCreate, InspectionFieldResponse, InspectionFieldUpdate
from app.services.inspection_field_service import (
    create_inspection_field,
    list_inspection_fields, update_inspection_field,
)

router = APIRouter(prefix="/inspections", tags=["inspection-fields"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/{inspection_id}/fields", response_model=InspectionFieldResponse, status_code=201)
def create_inspection_field_endpoint(
    inspection_id: int,
    payload: InspectionFieldCreate,
    db: Session = Depends(get_db)
):
    field = create_inspection_field(db, inspection_id, payload)
    if not field:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return field


@router.get("/{inspection_id}/fields", response_model=list[InspectionFieldResponse])
def list_inspection_fields_endpoint(
    inspection_id: int,
    db: Session = Depends(get_db)
):
    return list_inspection_fields(db, inspection_id)

@router.patch("/{inspection_id}/fields/{field_id}", response_model=InspectionFieldResponse)
def update_inspection_field_endpoint(
    inspection_id: int,
    field_id: int,
    payload: InspectionFieldUpdate,
    db: Session = Depends(get_db),
):
    field = update_inspection_field(db, inspection_id, field_id, payload)
    if not field:
        raise HTTPException(status_code=404, detail="Inspection field not found")
    return field

@router.put("/{inspection_id}/fields/{field_id}", response_model=InspectionFieldResponse)
def update_inspection_field_put_endpoint(
    inspection_id: int,
    field_id: int,
    payload: InspectionFieldUpdate,
    db: Session = Depends(get_db),
):
    field = update_inspection_field(db, inspection_id, field_id, payload)
    if not field:
        raise HTTPException(status_code=404, detail="Inspection field not found")
    return field