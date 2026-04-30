"""
User domain model.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class User:
    """
    User domain entity.

    This represents the business model of a user, separate from database concerns.
    """

    id: int
    login: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    admin: bool
    status: str
    created_at: datetime
    updated_at: datetime

    # Vendor association (single per user). Both id + name carried so the
    # API response can embed a slim vendor object without a second query.
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None

    # Division enum + free-text override when 'others'.
    division: Optional[str] = None
    division_other: Optional[str] = None

    # Soft-delete fields.
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None

    # Mapped projects — populated by the repo on explicit calls (list +
    # get-by-id paths). Each entry is a slim project dict the response
    # builder embeds. Closed/completed/soft-deleted projects are
    # filtered out at the repo layer.
    projects: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """
        Convert user to dictionary.

        Returns:
            Dictionary representation of user
        """
        return {
            "id": self.id,
            "login": self.login,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "admin": self.admin,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "division": self.division,
            "division_other": self.division_other,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "deleted_by": self.deleted_by,
            "projects": list(self.projects or []),
        }

    @property
    def full_name(self) -> str:
        """
        Get full name of user.

        Returns:
            Full name or login if name not available
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.login

    def is_active(self) -> bool:
        """
        Check if user is active.

        Returns:
            True if user is active
        """
        return self.status == "active"

    def is_deleted(self) -> bool:
        return self.deleted_at is not None
