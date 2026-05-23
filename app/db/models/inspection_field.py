from sqlalchemy import String, Text, DateTime, ForeignKey, func, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InspectionField(Base):
    __tablename__ = "inspection_fields"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    field_label: Mapped[str] = mapped_column(String(150), nullable=False)
    field_group: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_type: Mapped[str] = mapped_column(String(50), nullable=False)
    manual_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    inspection = relationship("Inspection", back_populates="fields")