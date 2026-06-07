from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.inspection_request import (
    InspectionRequestCreate,
    InspectionRequestResponse,
)
from app.services.inspection_request_service import (
    create_inspection_request,
    get_inspection_request_by_id,
    list_inspection_requests,
)

router = APIRouter(prefix="/inspection-requests", tags=["inspection-requests"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=InspectionRequestResponse, status_code=201)
def create_inspection_request_endpoint(
    payload: InspectionRequestCreate,
    db: Session = Depends(get_db),
):
    return create_inspection_request(db, payload)


@router.get("/", response_model=list[InspectionRequestResponse])
def list_inspection_requests_endpoint(
    db: Session = Depends(get_db),
):
    return list_inspection_requests(db)


@router.get("/{inspection_request_id}", response_model=InspectionRequestResponse)
def get_inspection_request_endpoint(
    inspection_request_id: int,
    db: Session = Depends(get_db),
):
    inspection_request = get_inspection_request_by_id(db, inspection_request_id)
    if not inspection_request:
        raise HTTPException(status_code=404, detail="Inspection request not found")
    return inspection_request