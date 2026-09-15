from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, tecnico
from app.db.models.users import User
from app.schemas.inspection_enrichment import InspectionEnrichmentResponse
from app.services.inspection_enrichment_service import enrich_inspection_from_plate_technical

router = APIRouter(prefix="/inspection-enrichment", tags=["inspection-enrichment"])

@router.post(
    "/inspections/{inspection_id}/plate-technical",
    response_model=InspectionEnrichmentResponse,
)
def enrich_plate_technical_endpoint(
    inspection_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(tecnico),
):
    try:
        return enrich_inspection_from_plate_technical(db, inspection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))