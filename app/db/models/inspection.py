from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(150), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    inspection_type: Mapped[str] = mapped_column(String(100), nullable=False)
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(150), nullable=True)

    responsible_inspector_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    responsible_inspector = relationship("User", foreign_keys=[responsible_inspector_id])
    fields = relationship("InspectionField", back_populates="inspection", cascade="all, delete-orphan")
    evidences = relationship("Evidence", back_populates="inspection", cascade="all, delete-orphan")
    report_drafts = relationship("ReportDraft", back_populates="inspection")
    productivity = relationship(
        "InspectionProductivity",
        back_populates="inspection",
        uselist=False,
        cascade="all, delete-orphan",
    )