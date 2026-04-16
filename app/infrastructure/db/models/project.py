"""
Project database model.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, ForeignKey, Text
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
    # New fields for enhanced project management
    # Status: Configure allowed values in app/core/constants.py -> PROJECT_STATUS_CHOICES
    status = Column(String(50), default="new", nullable=False, index=True)
    # Owner: Username of the project owner (validated against users table)
    owner = Column(String(255), nullable=True, index=True)
    # Category: Configure allowed values in app/core/constants.py -> PROJECT_CATEGORY_CHOICES
    category = Column(String(50), nullable=True, index=True)
    # Dates: Must be in the future, end_date must be after start_date
    start_date = Column(DateTime, nullable=True, index=True)
    end_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Indexes
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
    )

    def __repr__(self) -> str:
        return f"<ProjectModel(id={self.id}, identifier='{self.identifier}', name='{self.name}', status='{self.status}')>"
