from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Numeric, Boolean
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