from typing import Any

from pydantic import BaseModel, Field


class imported_image_preview(BaseModel):
    sequence: int
    filename: str
    content_type: str | None = None
    size_bytes: int
    sha1: str
    caption: str | None = None
    classification: str
    evidence_slot: str | None = None
    component_code: str | None = None
    side: str | None = None
    axle_number: int | None = None
    reason: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class parsed_result_row(BaseModel):
    component: str
    condition: str | None = None
    observations: str | None = None
    action_required: str | None = None


class docx_import_preview_response(BaseModel):
    source_filename: str
    report_code: str | None = None
    extracted_fields: dict[str, str | None] = Field(default_factory=dict)
    results: list[parsed_result_row] = Field(default_factory=list)
    images: list[imported_image_preview] = Field(default_factory=list)
    conclusion: str | None = None
    synthetic_transcription: str | None = None
    draft_base: str | None = None
    warnings: list[str] = Field(default_factory=list)


class historical_import_response(BaseModel):
    source_filename: str
    inspection_id: int | None = None
    inspection_field_ids: list[int] = Field(default_factory=list)
    evidence_ids: list[int] = Field(default_factory=list)
    transcription_id: int | None = None
    report_draft_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class historical_batch_import_item(BaseModel):
    source_filename: str
    success: bool
    inspection_id: int | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class historical_batch_import_response(BaseModel):
    total_files: int
    imported_files: int
    failed_files: int
    items: list[historical_batch_import_item] = Field(default_factory=list)