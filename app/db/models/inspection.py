from sqlalchemy import String, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(150), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    inspection_type: Mapped[str] = mapped_column(String(100), nullable=False)
    inspection_date: Mapped[Date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    responsible_inspector: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    fields = relationship("InspectionField", back_populates="inspection", cascade="all, delete-orphan")
    evidences = relationship("Evidence", back_populates="inspection", cascade="all, delete-orphan")