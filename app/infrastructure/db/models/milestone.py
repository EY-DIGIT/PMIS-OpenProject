"""Milestone SQLAlchemy model."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Index,
)
from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class MilestoneModel(Base):
    """Milestones under a project. No type, no actual_* dates."""
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("idx_milestones_project_live", "project_id", "deleted_at"),
        Index("idx_milestones_project_position", "project_id", "position"),
    )

    def __repr__(self) -> str:
        return f"<MilestoneModel(id={self.id}, project_id={self.project_id}, name='{self.name}')>"
