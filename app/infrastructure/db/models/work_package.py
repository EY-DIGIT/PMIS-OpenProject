"""
Work Package database model.
"""
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)
from sqlalchemy import Column, Integer, String, Text, DateTime, Index, ForeignKey
from sqlalchemy.orm import relationship
from ..session import Base


class WorkPackageModel(Base):
    """Work Package database model."""

    __tablename__ = "work_packages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subject = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("work_packages.id"), nullable=True, index=True)
    type_id = Column(Integer, ForeignKey("work_package_types.id"), nullable=True, index=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(100), default="new", nullable=False, index=True)
    priority = Column(String(100), default="normal", nullable=False, index=True)
    done_ratio = Column(Integer, default=0, nullable=False)  # 0-100
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationships
    project = relationship("ProjectModel", foreign_keys=[project_id])
    parent = relationship("WorkPackageModel", remote_side=[id], foreign_keys=[parent_id])
    assignee = relationship("UserModel", foreign_keys=[assignee_id])

    # Indexes
    __table_args__ = (
        Index("idx_work_packages_project_id", "project_id"),
        Index("idx_work_packages_parent_id", "parent_id"),
        Index("idx_work_packages_type_id", "type_id"),
        Index("idx_work_packages_assignee_id", "assignee_id"),
        Index("idx_work_packages_status", "status"),
        Index("idx_work_packages_priority", "priority"),
        Index("idx_work_packages_subject", "subject"),
    )

    def __repr__(self) -> str:
        return f"<WorkPackageModel(id={self.id}, subject='{self.subject}', project_id={self.project_id})>"
