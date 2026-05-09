from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceBase(BaseModel):
    file_path: str
    file_type: str = Field(..., max_length=100)
    evidence_category: str = Field(..., max_length=100)
    caption: str | None = None

class EvidenceCreate(EvidenceBase):
    pass

class EvidenceResponse(EvidenceBase):
    id: int
    inspection_id: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}
