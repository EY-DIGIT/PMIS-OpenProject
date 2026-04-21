"""
Project database model.
"""
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, ForeignKey, Text, text
from ..session import Base


class ProjectModel(Base):
    """Project database model."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    identifier = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    public = Column(Boolean, default=False, nullable=False)
    status_explanation = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    # Status: lowercase values. Allowed: new, draft, published, closed, suspended.
    # See app/api/v3/projects/schemas.py PROJECT_STATUS_CHOICES.
    status = Column(String(50), default="new", nullable=False, index=True)
    owner = Column(String(255), nullable=True, index=True)
    # Category: MSAP, MSIP, BSP. Immutable after create.
    category = Column(String(50), nullable=True, index=True)
    start_date = Column(DateTime, nullable=True, index=True)
    end_date = Column(DateTime, nullable=True, index=True)
    # Versions may record the project's actual end date; baselines leave it NULL.
    actual_end_date = Column(DateTime, nullable=True)

    # Versioning: a version is a row with is_version=true, version_of pointing
    # at the non-version (baseline) row it was cloned from. baseline_id mirrors
    # version_of on versions (kept as a separate column for future divergence,
    # e.g. versions of versions). NULL on non-versions.
    is_version = Column(Boolean, default=False, nullable=False, index=True)
    version_of = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    baseline_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    version_no = Column(Integer, nullable=True)

    # Audit + soft delete
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Enforces "one active version per baseline" at the DB layer.
    # Active = is_version AND status != 'suspended' AND not soft-deleted.
    __table_args__ = (
        Index("idx_projects_identifier", "identifier"),
        Index("idx_projects_name", "name"),
        Index("idx_projects_active", "active"),
        Index("idx_projects_public", "public"),
        Index("idx_projects_parent_id", "parent_id"),
        Index("idx_projects_status", "status"),
        Index("idx_projects_owner", "owner"),
        Index("idx_projects_category", "category"),
        Index("idx_projects_start_date", "start_date"),
        Index("idx_projects_end_date", "end_date"),
        Index("idx_projects_is_version", "is_version"),
        Index("idx_projects_version_of", "version_of"),
        Index("idx_projects_baseline_id", "baseline_id"),
        Index("idx_projects_deleted_at", "deleted_at"),
        Index(
            "ux_projects_active_version_per_baseline",
            "version_of",
            unique=True,
            sqlite_where=text("is_version = 1 AND status != 'suspended' AND deleted_at IS NULL"),
            postgresql_where=text("is_version = true AND status != 'suspended' AND deleted_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<ProjectModel(id={self.id}, identifier='{self.identifier}', name='{self.name}', status='{self.status}', is_version={self.is_version})>"
