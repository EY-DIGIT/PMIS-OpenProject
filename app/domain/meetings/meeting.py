"""
Meeting domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ...shared.datetime import iso_utc


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
    created_by_id: str  # doc 26: UUID string
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
            "scheduled_at": iso_utc(self.scheduled_at),
            "duration_minutes": self.duration_minutes,
            "location": self.location,
            "created_by_id": self.created_by_id,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }
