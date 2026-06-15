from datetime import date, datetime

from pydantic import BaseModel, Field, ConfigDict


class ProductivityBase(BaseModel):
    inspector_name: str | None = Field(
        default=None,
        max_length=150,
        description="Nombre del inspector resuelto desde el usuario responsable de la inspección.",
    )
    scheduled_date: date | None = None
    report_started_at: datetime | None = None
    report_finished_at: datetime | None = None
    duration_minutes: float | None = None
    operational_status: str = Field(default="pending", max_length=50)
    met_goal: bool | None = None


class ProductivityCreate(BaseModel):
    inspection_id: int
    inspector_name: str | None = Field(
        default=None,
        max_length=150,
        description="Campo opcional solo para compatibilidad. El servicio prioriza el usuario responsable relacionado."
    )
    scheduled_date: date | None = None
    operational_status: str = Field(default="pending", max_length=50)


class ProductivityStartRequest(BaseModel):
    report_started_at: datetime | None = None


class ProductivityFinishRequest(BaseModel):
    report_finished_at: datetime | None = None
    operational_status: str = Field(default="completed", max_length=50)


class ProductivityUpdate(BaseModel):
    inspector_name: str | None = Field(
        default=None,
        max_length=150,
        description="Campo de compatibilidad. El valor final se sincroniza desde la inspección cuando exista usuario responsable.",
    )
    scheduled_date: date | None = None
    report_started_at: datetime | None = None
    report_finished_at: datetime | None = None
    duration_minutes: float | None = None
    operational_status: str | None = Field(default=None, max_length=50)
    met_goal: bool | None = None


class ProductivityResponse(ProductivityBase):
    id: int
    inspection_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProductivitySummaryResponse(BaseModel):
    total_inspections: int
    completed_reports: int
    average_report_minutes: float
    on_time_count: int
    on_time_percentage: float
    goal_minutes: int = 20


class ProductivityByInspectorItem(BaseModel):
    inspector_name: str
    assigned_inspections: int
    completed_reports: int
    average_report_minutes: float
    on_time_count: int
    on_time_percentage: float


class ProductivityStatusItem(BaseModel):
    operational_status: str
    count: int


class ProductivityDashboardResponse(BaseModel):
    summary: ProductivitySummaryResponse
    by_inspector: list[ProductivityByInspectorItem]
    by_status: list[ProductivityStatusItem]