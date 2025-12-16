"""
User domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
