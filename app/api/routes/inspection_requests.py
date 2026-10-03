from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, solo_admin
from app.db.models.users import User
from app.schemas.inspection_request import (
    InspectionRequestConvert,
    InspectionRequestCreate,
    InspectionRequestResponse,
)
from app.services.inspection_request_service import (
    create_inspection_request,
    eliminar_inspection_request,
    get_inspection_request_by_id,
    list_inspection_requests,
    convert_inspection_request,
)

router = APIRouter(prefix="/inspection-requests", tags=["inspection-requests"])


@router.post("/", response_model=InspectionRequestResponse, status_code=201)
def create_inspection_request_endpoint(
    payload: InspectionRequestCreate,
    db: Session = Depends(get_db),
):
    return create_inspection_request(db, payload)


@router.get("", response_model=list[InspectionRequestResponse])
def list_inspection_requests_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(solo_admin),
):
    return list_inspection_requests(db)


@router.get("/{inspection_request_id}", response_model=InspectionRequestResponse)
def get_inspection_request_endpoint(
    inspection_request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(solo_admin),
):
    inspection_request = get_inspection_request_by_id(db, inspection_request_id)
    if not inspection_request:
        raise HTTPException(status_code=404, detail="Inspection request not found")
    return inspection_request

@router.patch("/{inspection_request_id}/convert", response_model=InspectionRequestResponse)
def convert_inspection_request_endpoint(
    inspection_request_id: int,
    payload: InspectionRequestConvert,
    db: Session = Depends(get_db),
    _: User = Depends(solo_admin),
):
    try:
        return convert_inspection_request(db, inspection_request_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inspection_request_endpoint(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(solo_admin),
):
    try:
        eliminado = eliminar_inspection_request(db, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al eliminar solicitud: {exc}")
    if not eliminado:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return Response(status_code=status.HTTP_204_NO_CONTENT)