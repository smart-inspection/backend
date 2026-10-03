from datetime import datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.cryptography import EncryptedString
from app.db.base import Base


class InspectionRequest(Base):
    __tablename__ = "inspection_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(EncryptedString(255), nullable=True)
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
    consent_accepted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    consent_third_party: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    consent_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    consent_ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(
        timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(DateTime(
        timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id"), nullable=True, index=True)

    inspection = relationship("Inspection")