from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class InspectionRequestBase(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=150)
    contact_name: str = Field(..., min_length=1, max_length=150)
    contact_email: str | None = Field(default=None, max_length=150)
    contact_phone: str | None = Field(default=None, max_length=50)
    requested_date: date | None = None
    location: str = Field(..., min_length=1, max_length=200)
    service_type: str | None = Field(default=None, max_length=100)
    equipment_type: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)
    status: str = Field(default="pending", max_length=50)
    consent_accepted: bool = Field(default=False, description="Consentimiento informado aceptado")
    consent_third_party: bool = Field(default=False, description="Consentimiento para tratamiento por terceros")

    @field_validator(
        "company_name",
        "contact_name",
        "location",
        mode="before",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized_value = str(value or "").strip()

        if not normalized_value:
            raise ValueError("Este campo es obligatorio.")

        return normalized_value

    @field_validator(
        "contact_email",
        "contact_phone",
        "service_type",
        "equipment_type",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = str(value).strip()

        return normalized_value or None


class InspectionRequestCreate(InspectionRequestBase):
    pass


class InspectionRequestResponse(InspectionRequestBase):
    id: int
    consent_timestamp: datetime | None = None
    consent_ip_address: str | None = None
    inspection_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }


class InspectionRequestConvert(BaseModel):
    inspection_id: int
    status: str = Field(default="converted", max_length=50)