"""Activity Resource SQLAlchemy model (1-to-1 with activities)."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Numeric, Index, text,
)
from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ActivityResourceModel(Base):
    """
    Resource details for Resource-type activities.

    A partial unique index on (activity_id) WHERE deleted_at IS NULL enforces
    at most one live resource row per activity. Soft-deleted historical rows
    are allowed to coexist.
    """
    __tablename__ = "activity_resources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    resource_name = Column(String(255), nullable=False)

    onboard_date = Column(DateTime, nullable=True)
    actual_onboard_date = Column(DateTime, nullable=True)
    offboard_date = Column(DateTime, nullable=True)
    actual_offboard_date = Column(DateTime, nullable=True)

    position = Column(String(255), nullable=True)
    designation = Column(String(255), nullable=True)
    job_role = Column(String(255), nullable=True)
    qualification = Column(String(255), nullable=True)
    experience_years = Column(Numeric(4, 1), nullable=True)

    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        # Partial unique index: SQLite 3.8+ and PostgreSQL both support this.
        Index(
            "uq_activity_resources_activity_live",
            "activity_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_activity_resources_project_live", "project_id", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<ActivityResourceModel(id={self.id}, activity_id={self.activity_id})>"
