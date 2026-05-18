from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Numeric, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class Evidence(Base):
    __tablename__ = "evidences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id"),
        nullable=False,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_category: Mapped[str] = mapped_column(String(100), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_label: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    normalized_label: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    evidence_slot: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    component_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    axle_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    side: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    is_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    label_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    ocr_extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ocr_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ocr_last_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    inspection = relationship("Inspection", back_populates="evidences")