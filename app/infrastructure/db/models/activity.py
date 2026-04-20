"""Activity SQLAlchemy model."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Index, CheckConstraint,
)
from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ActivityModel(Base):
    """Activities under a milestone. Has type + optional actual dates."""
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # Denormalized project_id for cheap "everything under project X" queries.
    # Service layer guarantees it matches milestone.project_id on every write.
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    milestone_id = Column(Integer, ForeignKey("milestones.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # type is enforced in the schema layer + CHECK constraint for belt-and-suspenders.
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
            name="ck_activities_type",
        ),
        Index("idx_activities_milestone_live", "milestone_id", "deleted_at"),
        Index("idx_activities_milestone_position", "milestone_id", "position"),
        Index("idx_activities_project_live", "project_id", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<ActivityModel(id={self.id}, milestone_id={self.milestone_id}, name='{self.name}', type='{self.type}')>"
