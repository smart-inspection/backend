from datetime import datetime

from pydantic import BaseModel, Field

class EvidenceBase(BaseModel):
    file_path: str
    file_type: str = Field(..., max_length=100)
    evidence_category: str = Field(..., max_length=100)
    caption: str | None = None

class EvidenceCreate(EvidenceBase):
    pass

class EvidenceResponse(BaseModel):
    id: int
    inspection_id: int
    file_path: str
    file_url: str
    file_type: str = Field(..., max_length=50)
    evidence_category: str = Field(..., max_length=100)
    caption: str | None = None

    ocr_extracted_text: str | None = None
    ocr_confidence: float | None = None
    ocr_processed: bool
    ocr_last_processed_at: datetime | None = None

    uploaded_at: datetime

    model_config = {"from_attributes": True}

class EvidenceOCRResponse(BaseModel):
    evidence_id: int
    ocr_extracted_text: str | None
    ocr_confidence: float | None
    ocr_processed: bool
    ocr_last_processed_at: datetime | None