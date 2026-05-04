"""
Membership domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from ...shared.datetime import iso_utc


@dataclass
class Membership:
    """
    Membership domain entity.

    Represents a user's membership in a project with associated roles.
    Follows OpenProject semantics.
    """

    id: int
    project_id: str
    user_id: str  # doc 26: UUID string
    roles: List[str]
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        """
        Convert membership to dictionary.

        Returns:
            Dictionary representation of membership
        """
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "roles": self.roles,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }

    def has_role(self, role: str) -> bool:
        """
        Check if membership has a specific role.

        Args:
            role: Role name

        Returns:
            True if membership has role
        """
        return role in self.roles

    def add_role(self, role: str) -> None:
        """
        Add a role to membership.

        Args:
            role: Role name
        """
        if role not in self.roles:
            self.roles.append(role)

    def remove_role(self, role: str) -> None:
        """
        Remove a role from membership.

        Args:
            role: Role name
        """
        if role in self.roles:
            self.roles.remove(role)
