from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field

class EvidenceBase(BaseModel):
    file_path: str
    file_type: str = Field(..., max_length=100)
    evidence_category: str = Field(..., max_length=100)
    caption: str | None = None

    raw_label: str | None = Field(default=None, max_length=120)
    normalized_label: str | None = Field(default=None, max_length=120)
    evidence_slot: str | None = Field(default=None, max_length=120)
    component_code: str | None = Field(default=None, max_length=80)
    axle_number: int | None = None
    side: str | None = Field(default=None, max_length=20)
    is_reference: bool = False
    label_confidence: float | None = None
    metadata_json: dict[str, Any] | None = None

class EvidenceCreate(EvidenceBase):
    pass

class EvidenceUpdate(BaseModel):
    evidence_category: str | None = Field(default=None, max_length=100)
    caption: str | None = None
    raw_label: str | None = Field(default=None, max_length=120)
    component_code: str | None = Field(default=None, max_length=80)
    axle_number: int | None = None
    side: str | None = Field(default=None, max_length=20)
    is_reference: bool | None = None
    ocr_extracted_text: str | None = None
    ocr_confidence: float | None = None

class EvidenceResponse(BaseModel):
    id: int
    inspection_id: int
    file_path: str
    file_url: str
    file_type: str = Field(..., max_length=50)
    evidence_category: str = Field(..., max_length=100)
    caption: str | None = None

    raw_label: str | None = None
    normalized_label: str | None = None
    evidence_slot: str | None = None
    component_code: str | None = None
    axle_number: int | None = None
    side: str | None = None
    is_reference: bool
    label_confidence: float | None = None
    metadata_json: dict[str, Any] | None = None

    ocr_extracted_text: str | None = None
    ocr_confidence: float | None = None
    ocr_processed: bool
    ocr_last_processed_at: datetime | None = None
    uploaded_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def accessible_alt_text(self) -> str:
        """Texto alternativo WCAG 2.2 AA generado dinámicamente para lectores de pantalla."""
        partes: list[str] = []
        if self.evidence_slot:
            partes.append(f"Slot: {self.evidence_slot.replace('_', ' ').title()}")
        if self.evidence_category:
            partes.append(f"Categoría: {self.evidence_category}")
        if self.component_code:
            partes.append(f"Componente: {self.component_code}")
        if self.axle_number is not None:
            lado = f" {self.side}" if self.side else ""
            partes.append(f"Eje {self.axle_number}{lado}")
        if self.caption:
            partes.append(self.caption)
        return ". ".join(partes) if partes else "Evidencia fotográfica de inspección técnica"

    model_config = {"from_attributes": True}

class EvidenceOCRResponse(BaseModel):
    evidence_id: int
    ocr_extracted_text: str | None
    ocr_confidence: float | None
    ocr_processed: bool
    ocr_last_processed_at: datetime | None