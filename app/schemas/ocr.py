from pydantic import BaseModel, computed_field


def _confidence_level(confidence: float | None) -> str:
    """Clasifica la confianza de IA en niveles semánticos WCAG/ISO 25010."""
    if confidence is None:
        return "unknown"
    if confidence >= 0.90:
        return "high"
    if confidence >= 0.70:
        return "medium"
    return "low"


class OCRExtractResponse(BaseModel):
    evidence_id: int
    evidence_category: str
    file_path: str
    extracted_text: str
    confidence: float | None = None

    @computed_field  # type: ignore[misc]
    @property
    def confidence_level(self) -> str:
        return _confidence_level(self.confidence)


class OCRValidationItem(BaseModel):
    field_id: int
    field_key: str
    field_label: str
    manual_value: str | None = None
    ocr_value: str | None = None
    final_value: str | None = None
    validation_status: str
    validation_message: str | None = None
    confidence: float | None = None

    @computed_field  # type: ignore[misc]
    @property
    def confidence_level(self) -> str:
        return _confidence_level(self.confidence)


class OCRValidationSummary(BaseModel):
    matched: int
    mismatched: int
    not_found: int
    average_confidence: float | None = None

    @computed_field  # type: ignore[misc]
    @property
    def average_confidence_level(self) -> str:
        return _confidence_level(self.average_confidence)


class OCRValidationResponse(BaseModel):
    inspection_id: int
    processed_evidences: int
    aggregated_text: str
    summary: OCRValidationSummary
    results: list[OCRValidationItem]