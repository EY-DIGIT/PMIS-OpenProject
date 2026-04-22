"""Activity-to-activity dependency association.

Composite PK on (source_activity_id, target_activity_id). Both sides FK into
``activities.id``. The ``project_id`` denormalization keeps "all dependency
edges in this project" queries cheap (one indexed scan).

Rules enforced at the SERVICE layer (not the DB):
- source_activity_id != target_activity_id (no self-edge)
- both source and target belong to the same project
- the directed graph stays acyclic (DFS check on each insert)
- target activity must not be soft-deleted
- when target activity is soft-deleted, all rows targeting it are removed
  (silent cascade in DependencyRepository)

Lives on whichever project (baseline OR version) owns the source activity.
On version creation, the baseline's edges are cloned with id-rewrite (see
``DependencyRepository.clone_activity_dependencies_for_version``).
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String

from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ActivityDependencyModel(Base):
    __tablename__ = "activity_dependencies"

    source_activity_id = Column(
        String(36),
        ForeignKey("activities.id"),
        primary_key=True,
        index=True,
    )
    target_activity_id = Column(
        String(36),
        ForeignKey("activities.id"),
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
        Index("idx_activity_deps_source", "source_activity_id"),
        Index("idx_activity_deps_target", "target_activity_id"),
        Index("idx_activity_deps_project", "project_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityDependencyModel(source='{self.source_activity_id}', "
            f"target='{self.target_activity_id}')>"
        )
