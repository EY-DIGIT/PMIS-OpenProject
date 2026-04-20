"""Subtask SQLAlchemy model (parent: task)."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Index, CheckConstraint,
)
from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SubtaskModel(Base):
    """Subtasks under a task. Has type + optional actual dates."""
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    type = Column(String(20), nullable=False)

    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    actual_start_date = Column(DateTime, nullable=True)
    actual_end_date = Column(DateTime, nullable=True)

    position = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('standard', 'resource', 'transactional')",
            name="ck_subtasks_type",
        ),
        Index("idx_subtasks_task_live", "task_id", "deleted_at"),
        Index("idx_subtasks_task_position", "task_id", "position"),
        Index("idx_subtasks_project_live", "project_id", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<SubtaskModel(id={self.id}, task_id={self.task_id}, name='{self.name}')>"
