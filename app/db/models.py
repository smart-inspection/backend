from sqlalchemy import String, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Inspection(Base):
    __tablename__ = 'inspection'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[int] = mapped_column(String(50), unique=True, nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(150), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    inspection_type: Mapped[str] = mapped_column(String(100), nullable=False)
    inspection_date: Mapped[str] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    responsible_inspector: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
