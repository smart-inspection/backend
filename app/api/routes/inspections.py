from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, solo_admin, tecnico, todos
from app.db.models.users import User
from app.schemas.inspection import InspectionCreate, InspectionResponse
from app.services.inspection_service import (
    create_inspection,
    eliminar_inspection,
    get_inspection_by_id,
    list_inspections,
)

router = APIRouter(prefix="/inspections", tags=["inspections"])

@router.post("", response_model=InspectionResponse, status_code=201)
def create_inspection_endpoint(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(tecnico),
):
    try:
        return create_inspection(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[InspectionResponse])
def list_inspections_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(todos),
):
    return list_inspections(db)


@router.get("/{inspection_id}", response_model=InspectionResponse)
def get_inspection_endpoint(
    inspection_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(todos),
):
    inspection = get_inspection_by_id(db, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection


@router.delete("/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inspection_endpoint(
    inspection_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(solo_admin),
):
    try:
        eliminado = eliminar_inspection(db, inspection_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar inspección: {exc}",
        )
    if not eliminado:
        raise HTTPException(status_code=404, detail="Inspección no encontrada")
    return Response(status_code=status.HTTP_204_NO_CONTENT)