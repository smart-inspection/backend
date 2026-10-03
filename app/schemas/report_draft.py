from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field


class ReportDraftGenerateRequest(BaseModel):
    template_version: str = Field(default="v1", max_length=50)


class ReportDraftUpdate(BaseModel):
    edited_text: str
    status: str = Field(default="edited", max_length=30)


class ReportDraftResponse(BaseModel):
    id: int
    inspection_id: int
    title: str
    template_version: str
    status: str
    generated_text: str
    edited_text: str | None = None
    source_snapshot: dict[str, Any] | None = None
    generation_time_ms: int | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def is_ai_generated(self) -> bool:
        """True si el borrador fue producido por un modelo de IA (generation_time_ms > 0)."""
        return self.generation_time_ms is not None and self.generation_time_ms > 0

    @computed_field  # type: ignore[misc]
    @property
    def disclaimer(self) -> str | None:
        """Aviso de divulgación de IA requerido por WCAG 2.2 / ISO 25010 si el contenido es generado por IA."""
        if self.is_ai_generated:
            return (
                "Este borrador fue generado asistido por inteligencia artificial. "
                "El contenido debe ser revisado y validado por un inspector certificado "
                "antes de su uso oficial."
            )
        return None

    model_config = {"from_attributes": True}


class LLMReportGenerateRequest(BaseModel):
    template_version: str = Field(default="llama3-v1", max_length=50)