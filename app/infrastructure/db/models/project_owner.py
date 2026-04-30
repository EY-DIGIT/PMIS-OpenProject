"""Project owner master.

Whitelist of users who are allowed to be set as a project's ``owner``.
Today the project's ``owner`` column is just a free-text login string with
a check that the user exists. With this master, project create / upsert
also validates that the chosen login is **active in the project_owners
catalog**, so governance can curate which staff are allowed to own
projects without giving everyone create-project capability.

Schema:
- ``id``           : auto-increment surrogate.
- ``user_id``      : FK -> users.id. The owner is always backed by a
                     real user account, so we don't duplicate name/email.
- ``display_name`` : optional override label for UI dropdowns when the
                     stored user's first/last name is too informal.
- ``active``       : flips off without deleting (history-safe).
- ``created_at`` / ``updated_at`` : audit timestamps.

Unique constraint on ``user_id``: a single user can only appear once in
the catalog (active or inactive). Toggle ``active`` to remove.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String,
    UniqueConstraint,
)

from ..session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ProjectOwnerModel(Base):
    __tablename__ = "project_owners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    display_name = Column(String(255), nullable=True)
    active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_project_owners_user_id"),
        Index("idx_project_owners_active_user", "active", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectOwnerModel(id={self.id}, user_id={self.user_id}, "
            f"active={self.active})>"
        )
