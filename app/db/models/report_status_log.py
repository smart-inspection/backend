from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base

class ReportStatusLog(Base):
    __tablename__ = "report_status_logs"

    id = Column(Integer, primary_key=True, index=True)
    report_draft_id = Column(Integer, ForeignKey("report_drafts.id"), nullable=False, index=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=True, index=True)

    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=True)
    action = Column(String(50), nullable=False, index=True)

    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_name = Column(String(120), nullable=True)

    notes = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    report_draft = relationship("ReportDraft", back_populates="status_logs")