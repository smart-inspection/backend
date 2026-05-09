from sqlalchemy import String, Text, DateTime, ForeignKey, func, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReportDraft(Base):
    __tablename__ = "report_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Borrador de informe")
    template_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="generated")

    generated_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generation_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    inspection = relationship("Inspection")