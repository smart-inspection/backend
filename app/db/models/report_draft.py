from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base

class ReportDraft(Base):
    __tablename__ = "report_drafts"

    id = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=False, index=True)

    title = Column(String(255), nullable=False, server_default="Borrador de informe")
    template_version = Column(String(50), nullable=False, server_default="v1")

    generated_text = Column(Text, nullable=True)
    edited_text = Column(Text, nullable=True)

    source_snapshot = Column(JSON, nullable=True)
    generation_time_ms = Column(Integer, nullable=True)

    status = Column(String(30), nullable=False, default="draft", server_default="draft")
    status_updated_at = Column(DateTime(timezone=True), nullable=True)
    status_updated_by = Column(Integer, nullable=True, index=True)
    last_action = Column(String(50), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    inspection = relationship("Inspection", back_populates="report_drafts")
    status_logs = relationship(
        "ReportStatusLog",
        back_populates="report_draft",
        cascade="all, delete-orphan",
        order_by="ReportStatusLog.created_at.desc()",
    )