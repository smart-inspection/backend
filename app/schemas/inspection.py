from datetime import date, datetime
from pydantic import BaseModel, Field

class InspectionBase(BaseModel):
    code: str = Field(..., max_length=50)
    client_name: str = Field(..., max_length=150)
    equipment_type: str = Field(..., max_length=100)
    inspection_type: str = Field(..., max_length=100)
    inspection_date: date
    location: str | None = None
    requested_by: str | None = None
    responsible_inspector: str | None = None
    status: str = "draft"

class InspectionCreate(InspectionBase):
    pass

class InspectionResponse(InspectionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}