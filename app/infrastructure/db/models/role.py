"""
Role database model.
"""
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, JSON
from ..session import Base


class RoleModel(Base):
    """Role database model."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    permissions = Column(JSON, default=list, nullable=False)
    builtin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_roles_name", "name"),
        Index("idx_roles_builtin", "builtin"),
    )

    def __repr__(self) -> str:
        return f"<RoleModel(id={self.id}, name='{self.name}', builtin={self.builtin})>"
