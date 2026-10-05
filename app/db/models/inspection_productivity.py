from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InspectionProductivity(Base):
    __tablename__ = "inspection_productivity"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    inspector_name: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    scheduled_date: Mapped[Date | None] = mapped_column(Date, nullable=True, index=True)
    report_started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    operational_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    met_goal: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    inspection = relationship("Inspection", back_populates="productivity")