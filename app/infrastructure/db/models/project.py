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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_projects_identifier", "identifier"),
        Index("idx_projects_name", "name"),
        Index("idx_projects_active", "active"),
        Index("idx_projects_public", "public"),
        Index("idx_projects_parent_id", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<ProjectModel(id={self.id}, identifier='{self.identifier}', name='{self.name}')>"
