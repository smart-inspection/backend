from sqlalchemy import Date, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InspectionRequest(Base):
    __tablename__ = "inspection_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requested_date: Mapped[Date | None] = mapped_column(Date, nullable=True, index=True)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    service_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    equipment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
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