from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportStatusUpdateRequest(BaseModel):
    status: str = Field(..., examples=["in_review"])
    notes: str | None = None


class ReportStatusResponse(BaseModel):
    report_draft_id: int
    status: str
    status_updated_at: datetime | None = None
    status_updated_by: int | None = None
    last_action: str | None = None


class ReportStatusLogResponse(BaseModel):
    id: int
    report_draft_id: int
    inspection_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None
    action: str
    actor_user_id: int | None = None
    actor_name: str | None = None
    notes: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    class Config:
        from_attributes = True