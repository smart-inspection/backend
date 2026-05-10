from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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

    model_config = {"from_attributes": True}

class LLMReportGenerateRequest(BaseModel):
    template_version: str = Field(default="llama3-v1", max_length=50)