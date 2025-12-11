"""
MeetingSection domain model for OpenProject Python port.

This module contains the domain model for meeting sections (agenda organization).
"""

from datetime import datetime
from typing import Optional, Dict, Any, List


class MeetingSection:
    """
    MeetingSection domain model representing a section of the meeting agenda.

    Sections help organize agenda items into logical groups.
    Each meeting can have a special "backlog" section for unprioritized items.

    Attributes:
        id: Unique identifier
        meeting_id: ID of the associated meeting
        title: Section title
        position: Order position in the meeting
        backlog: Whether this is the special backlog section
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    def __init__(
        self,
        id: Optional[int] = None,
        meeting_id: Optional[int] = None,
        title: Optional[str] = None,
        position: int = 1,
        backlog: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.meeting_id = meeting_id
        self.title = title
        self.position = position
        self.backlog = backlog
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

        # Associations (loaded separately)
        self.meeting = None
        self.agenda_items: List[Any] = []
        self.project = None

    def get_title(self) -> str:
        """
        Get the section title.

        Returns localized "Backlog" for backlog sections,
        or the actual title otherwise.
        """
        if self.backlog:
            return "Backlog"
        return self.title or ""

    def is_backlog(self) -> bool:
        """Check if this is the backlog section."""
        return self.backlog

    def is_untitled(self) -> bool:
        """Check if the section has no title."""
        return not self.title or not self.title.strip()

    def is_editable(self) -> bool:
        """
        Check if the section can be edited.

        Backlog sections cannot be edited.
        """
        return not self.backlog

    def get_agenda_items_sum_duration_in_minutes(self) -> int:
        """Calculate total duration of all agenda items in this section."""
        total = 0
        for item in self.agenda_items:
            if hasattr(item, 'duration_in_minutes') and item.duration_in_minutes:
                total += item.duration_in_minutes
        return total

    def get_last_position(self) -> int:
        """
        Get the next available position for agenda items in this section.

        Returns:
            The next position number (current max + 1)
        """
        if not self.agenda_items:
            return 1

        max_position = max(
            (item.position for item in self.agenda_items if hasattr(item, 'position')),
            default=0
        )
        return max_position + 1

    def validate(self) -> Dict[str, List[str]]:
        """
        Validate the section.

        Returns:
            Dict mapping field names to lists of error messages
        """
        errors = {}

        if not self.meeting_id:
            errors.setdefault("meeting_id", []).append("Meeting is required")

        # Non-backlog sections should have a title
        if not self.backlog and (not self.title or not self.title.strip()):
            errors.setdefault("title", []).append(
                "Title is required for non-backlog sections"
            )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert section to dictionary representation."""
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "title": self.get_title(),
            "position": self.position,
            "backlog": self.backlog,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
