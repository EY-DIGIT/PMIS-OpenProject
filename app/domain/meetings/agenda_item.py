"""
Meeting Agenda Item domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AgendaItem:
    """
    Agenda Item domain entity.

    Represents an item on a meeting's agenda.
    Can optionally reference a Work Package.
    Must belong to the same project as the meeting.
    """

    id: int
    meeting_id: int
    project_id: int
    title: str
    description: Optional[str]
    position: int
    work_package_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """
        Convert agenda item to dictionary.

        Returns:
            Dictionary representation of agenda item
        """
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "position": self.position,
            "work_package_id": self.work_package_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
