from pydantic import BaseModel

class EnrichmentUpdatedFieldResponse(BaseModel):
    field_key: str
    field_label: str
    ocr_value: str | None = None
    final_value: str | None = None

class InspectionEnrichmentResponse(BaseModel):
    inspection_id: int
    evidence_id: int | None = None
    updated_fields: list[EnrichmentUpdatedFieldResponse]
    message: str