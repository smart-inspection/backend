from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class ReportStatusUpdateRequest(BaseModel):
    status: str = Field(..., examples=["in_review"])
    notes: str | None = None


class StatusTransitionRequest(BaseModel):
    to_status: str = Field(..., examples=["in_review"])
    notes: str | None = Field(default=None, max_length=5000)


class ReportStatusResponse(BaseModel):
    report_draft_id: int
    status: str
    status_updated_at: datetime | None = None
    status_updated_by: int | None = None
    last_action: str | None = None

    model_config = ConfigDict(from_attributes=True)

class StatusTransitionResponse(ReportStatusResponse):
    inspection_id: int
    from_status: str | None = None
    operational_status: str | None = None


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

    model_config = ConfigDict(from_attributes=True)


class ReportStatusTransitionLogItem(BaseModel):
    id: int
    previous_status: str | None = None
    new_status: str | None = None
    changed_by_user_id: int | None = None
    user_full_name: str | None = None
    comment: str | None = None
    created_at: datetime
    inspection_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None
    actor_user_id: int | None = None
    actor_name: str | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AvailableTransitionsResponse(BaseModel):
    inspection_id: int
    current_status: str
    available_transitions: list[str]


class TransitionActionRequest(BaseModel):
    new_status: str = Field(..., examples=["in_review"])
    comment: str | None = Field(default=None, max_length=5000)
    to_status: str | None = None
    notes: str | None = None


class TransitionActionResponse(BaseModel):
    inspection_id: int
    current_status: str
    status: str
    log: ReportStatusTransitionLogItem


class ReportStatusOverviewItem(BaseModel):
    inspection_id: int
    code: str
    client_name: str
    inspector_name: str
    created_at: datetime
    current_status: str
    last_status_update: datetime | None = None
    total_transitions: int

    model_config = ConfigDict(from_attributes=True)