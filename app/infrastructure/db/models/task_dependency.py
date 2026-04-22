"""Task-to-task dependency association.

Composite PK on (source_task_id, target_task_id). Both sides FK into
``tasks.id``. ``project_id`` is denormalized for cheap project-scope queries.

Rules enforced at the SERVICE layer:
- source_task_id != target_task_id
- both source and target belong to the same project (i.e. the same version,
  since tasks only exist on versions)
- source.activity_id MUST already depend on target.activity_id (per
  ``activity_dependencies``). This enforces the user's hierarchy rule:
  "tasks may only depend on tasks under activities that are themselves
  dependent." Without this, you'd be able to wire arbitrary task graphs that
  contradict the activity-level structure.
- target must not be soft-deleted; soft-deleted target → row auto-removed
- the directed task graph stays acyclic
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String

from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class TaskDependencyModel(Base):
    __tablename__ = "task_dependencies"

    source_task_id = Column(
        String(36),
        ForeignKey("tasks.id"),
        primary_key=True,
        index=True,
    )
    target_task_id = Column(
        String(36),
        ForeignKey("tasks.id"),
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
        Index("idx_task_deps_source", "source_task_id"),
        Index("idx_task_deps_target", "target_task_id"),
        Index("idx_task_deps_project", "project_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TaskDependencyModel(source='{self.source_task_id}', "
            f"target='{self.target_task_id}')>"
        )
