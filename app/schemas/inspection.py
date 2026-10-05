from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class InspectionBase(BaseModel):
    code: str
    client_name: str
    equipment_type: str
    inspection_type: str
    inspection_date: date
    location: str | None = None
    requested_by: str | None = None
    responsible_inspector_id: int | None = None
    status: str = "draft"


class InspectionCreate(InspectionBase):
    pass


class InspectionResponse(InspectionBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)