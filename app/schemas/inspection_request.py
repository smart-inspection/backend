from datetime import date, datetime

from pydantic import BaseModel, Field


class InspectionRequestBase(BaseModel):
    company_name: str = Field(..., max_length=150)
    contact_name: str = Field(..., max_length=150)
    contact_email: str | None = Field(default=None, max_length=150)
    contact_phone: str | None = Field(default=None, max_length=50)
    requested_date: date | None = None
    location: str = Field(..., max_length=200)
    service_type: str | None = Field(default=None, max_length=100)
    equipment_type: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    status: str = Field(default="pending", max_length=50)


class InspectionRequestCreate(InspectionRequestBase):
    pass


class InspectionRequestResponse(InspectionRequestBase):
    id: int
    inspection_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class InspectionRequestConvert(BaseModel):
    inspection_id: int
    status: str = Field(default="converted", max_length=50)