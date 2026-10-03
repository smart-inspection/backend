from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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


def _extract_client_ip(request: Request) -> str:
    """Extrae la IP real del cliente considerando proxies inversos o conexión directa."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    if request.client and request.client.host:
        return request.client.host[:45]
    return "127.0.0.1"


@router.post("", response_model=InspectionRequestResponse, status_code=201)
@router.post("/", response_model=InspectionRequestResponse, status_code=201, include_in_schema=False)
def create_inspection_request_endpoint(
    payload: InspectionRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = _extract_client_ip(request)
    consent_timestamp = datetime.now(timezone.utc) if payload.consent_accepted else None
    return create_inspection_request(
        db=db,
        payload=payload,
        client_ip=client_ip,
        consent_timestamp=consent_timestamp,
    )


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