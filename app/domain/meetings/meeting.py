"""
Meeting domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Meeting:
    """
    Meeting domain entity.

    Represents a meeting associated with a project.
    This is the business model, separate from database concerns.
    """

    id: int
    project_id: str
    title: str
    description: Optional[str]
    scheduled_at: datetime
    duration_minutes: Optional[int]
    location: Optional[str]
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        """
        Convert meeting to dictionary.

        Returns:
            Dictionary representation of meeting
        """
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "duration_minutes": self.duration_minutes,
            "location": self.location,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
