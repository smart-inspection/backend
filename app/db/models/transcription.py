from sqlalchemy import String, Text, DateTime, ForeignKey, func, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transcription(Base):
    __tablename__ = "transcriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), nullable=False, index=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidences.id"), nullable=True, index=True)

    source_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="base")

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    edited_manually: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    inspection = relationship("Inspection")
    evidence = relationship("Evidence")