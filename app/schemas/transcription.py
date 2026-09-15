from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, computed_field

class TranscriptionCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    inspection_id: int
    evidence_id: int | None = None
    source_file_path: str
    language: str | None = Field(default="es")
    model_name: str = Field(default="base", max_length=100)

class TranscriptionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=(),
    )

    id: int
    inspection_id: int
    evidence_id: int | None = None
    source_file_path: str
    language: str | None = None
    model_name: str
    raw_text: str | None = None
    final_text: str | None = None
    confidence: float | None = None
    processed: bool
    edited_manually: bool
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def confidence_level(self) -> str:
        """Nivel semántico de confianza del modelo ASR (high/medium/low)."""
        if self.confidence is None:
            return "unknown"
        if self.confidence >= 0.90:
            return "high"
        if self.confidence >= 0.70:
            return "medium"
        return "low"

class TranscriptionUpdate(BaseModel):
    final_text: str