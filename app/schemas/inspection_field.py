from datetime import datetime

from pydantic import BaseModel, Field

class InspectionFieldBase(BaseModel):
    field_key: str = Field(..., max_length=100)
    field_label: str = Field(..., max_length=150)
    field_group: str = Field(..., max_length=100)
    expected_type: str = Field(..., max_length=50)
    manual_value: str | None = None
    ocr_value: str | None = None
    final_value: str | None = None
    validation_status: str = "pending"
    validation_message: str | None = None
    confidence: float | None = None

class InspectionFieldCreate(InspectionFieldBase):
    pass

class InspectionFieldResponse(InspectionFieldBase):
    id: int
    inspection_id: int
    updated_at: datetime

    model_config = {"from_attributes": True}