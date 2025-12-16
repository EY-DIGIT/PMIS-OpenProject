"""
Project domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Project:
    """
    Project domain entity.

    This represents the business model of a project, separate from database concerns.
    Follows OpenProject semantics.
    """

    id: int
    identifier: str
    name: str
    description: Optional[str]
    active: bool
    public: bool
    status_explanation: Optional[str]
    created_at: datetime
    updated_at: datetime
    parent_id: Optional[int] = None

    def to_dict(self) -> dict:
        """
        Convert project to dictionary.

        Returns:
            Dictionary representation of project
        """
        return {
            "id": self.id,
            "identifier": self.identifier,
            "name": self.name,
            "description": self.description,
            "active": self.active,
            "public": self.public,
            "status_explanation": self.status_explanation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "parent_id": self.parent_id,
        }

    def is_active(self) -> bool:
        """
        Check if project is active.

        Returns:
            True if project is active
        """
        return self.active

    def is_public(self) -> bool:
        """
        Check if project is public.

        Returns:
            True if project is public
        """
        return self.public

    def has_parent(self) -> bool:
        """
        Check if project has a parent.

        Returns:
            True if project has a parent
        """
        return self.parent_id is not None
