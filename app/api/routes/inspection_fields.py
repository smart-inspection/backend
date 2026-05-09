from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.inspection_field import InspectionFieldCreate, InspectionFieldResponse
from app.services.inspection_field_service import (
    create_inspection_field,
    list_inspection_fields,
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