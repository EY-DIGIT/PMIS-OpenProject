"""User-Role assignment (doc 21 part B)."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer

from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class UserRoleModel(Base):
    __tablename__ = "user_roles"

    user_id = Column(
        Integer, ForeignKey("users.id"), primary_key=True, nullable=False,
    )
    role_id = Column(
        Integer, ForeignKey("roles.id"), primary_key=True, nullable=False,
    )
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("idx_user_roles_user", "user_id"),
        Index("idx_user_roles_role", "role_id"),
    )
