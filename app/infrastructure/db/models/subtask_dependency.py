"""Subtask-to-subtask dependency association.

Composite PK on (source_subtask_id, target_subtask_id). Same pattern as the
activity / task dependency tables, one level deeper.

Service-layer rules:
- source != target
- both subtasks live in the same project (version)
- source.task_id MUST already depend on target.task_id (per
  ``task_dependencies``) — mirrors the activity-level rule one layer down
- target must not be soft-deleted; cascade-removed when target is deleted
- acyclic
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String

from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SubtaskDependencyModel(Base):
    __tablename__ = "subtask_dependencies"

    source_subtask_id = Column(
        String(36),
        ForeignKey("subtasks.id"),
        primary_key=True,
        index=True,
    )
    target_subtask_id = Column(
        String(36),
        ForeignKey("subtasks.id"),
        primary_key=True,
        index=True,
    )
    project_id = Column(
        String(36),
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_subtask_deps_source", "source_subtask_id"),
        Index("idx_subtask_deps_target", "target_subtask_id"),
        Index("idx_subtask_deps_project", "project_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SubtaskDependencyModel(source='{self.source_subtask_id}', "
            f"target='{self.target_subtask_id}')>"
        )
