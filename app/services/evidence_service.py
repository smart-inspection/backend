from sqlalchemy.orm import Session

from app.db.models import Inspection, Evidence
from app.schemas.evidence import EvidenceCreate


def create_evidence(
        db: Session,
        inspection_id: int,
        payload: EvidenceCreate,
) -> Evidence | None:
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        return None

    evidence = Evidence(
        inspection_id=inspection_id,
        **payload.model_dump()
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence

def list_evidences(db: Session, inspection_id: int) -> list[Evidence]:
    return (
        db.query(Evidence)
        .filter(Evidence.inspection_id == inspection_id)
        .order_by(Evidence.id.asc())
        .all()
    )