"""
Work Package Type DB model.
"""
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, UniqueConstraint
from ..session import Base


class WorkPackageTypeModel(Base):
    __tablename__ = "work_package_types"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    internal_name = Column(String(100), nullable=False, unique=True, index=True)
    is_builtin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    position = Column(Integer, default=0, nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('internal_name', name='uq_work_package_types_internal_name'),
        Index('idx_work_package_types_position', 'position'),
    )

    def __repr__(self) -> str:
        return f"<WorkPackageTypeModel(id={self.id}, internal_name='{self.internal_name}')>"
