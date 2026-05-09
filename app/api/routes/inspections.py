from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.inspection import InspectionCreate, InspectionResponse
from app.services.inspection_service import create_inspection, list_inspections

router = APIRouter(prefix="/inspections", tags=["inspections"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("", response_model=InspectionResponse)
def create_inspection_endpoint(payload: InspectionCreate, db: Session = Depends(get_db)):
    return create_inspection(db, payload)

@router.get("", response_model=list[InspectionResponse])
def list_inspections_endpoint(db: Session = Depends(get_db)):
    return list_inspections(db)