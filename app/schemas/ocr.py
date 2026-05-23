from pydantic import BaseModel


class OCRExtractResponse(BaseModel):
    evidence_id: int
    evidence_category: str
    file_path: str
    extracted_text: str
    confidence: float | None = None


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


class OCRValidationSummary(BaseModel):
    matched: int
    mismatched: int
    not_found: int
    average_confidence: float | None = None


class OCRValidationResponse(BaseModel):
    inspection_id: int
    processed_evidences: int
    aggregated_text: str
    summary: OCRValidationSummary
    results: list[OCRValidationItem]