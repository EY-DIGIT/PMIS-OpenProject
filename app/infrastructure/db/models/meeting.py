"""
Meeting database model.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index, ForeignKey, Text
from ..session import Base


class MeetingModel(Base):
    """Meeting database model."""

    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=True)
    location = Column(String(255), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_meetings_project_id", "project_id"),
        Index("idx_meetings_created_by_id", "created_by_id"),
        Index("idx_meetings_scheduled_at", "scheduled_at"),
        Index("idx_meetings_title", "title"),
    )

    def __repr__(self) -> str:
        return f"<MeetingModel(id={self.id}, project_id={self.project_id}, title='{self.title}')>"
