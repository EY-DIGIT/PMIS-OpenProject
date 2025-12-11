"""
MeetingAgendaItem domain model for OpenProject Python port.

This module contains the domain model for meeting agenda items.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class AgendaItemType(Enum):
    """Agenda item type enumeration."""
    SIMPLE = 0
    WORK_PACKAGE = 1


class MeetingAgendaItem:
    """
    MeetingAgendaItem domain model representing an item on the meeting agenda.

    Agenda items can be:
    - Simple items with a title and notes
    - Work package references for discussing specific work items

    Attributes:
        id: Unique identifier
        meeting_id: ID of the associated meeting
        author_id: ID of the user who created the item
        presenter_id: ID of the user presenting this item (optional)
        meeting_section_id: ID of the section containing this item
        work_package_id: ID of linked work package (if type is WORK_PACKAGE)
        title: Agenda item title
        notes: Agenda item notes/description
        position: Order position within the section
        duration_in_minutes: Duration allocated for this item (0-1440)
        item_type: Type of agenda item (SIMPLE or WORK_PACKAGE)
        lock_version: Optimistic locking version
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    MIN_DURATION = 0
    MAX_DURATION = 1440  # 24 hours in minutes

    def __init__(
        self,
        id: Optional[int] = None,
        meeting_id: Optional[int] = None,
        author_id: Optional[int] = None,
        presenter_id: Optional[int] = None,
        meeting_section_id: Optional[int] = None,
        work_package_id: Optional[int] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        position: int = 1,
        duration_in_minutes: Optional[int] = None,
        item_type: AgendaItemType = AgendaItemType.SIMPLE,
        lock_version: int = 0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.meeting_id = meeting_id
        self.author_id = author_id
        self.presenter_id = presenter_id
        self.meeting_section_id = meeting_section_id
        self.work_package_id = work_package_id
        self.title = title
        self.notes = notes
        self.position = position
        self.duration_in_minutes = duration_in_minutes
        self.item_type = item_type
        self.lock_version = lock_version
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

        # Associations (loaded separately)
        self.meeting = None
        self.meeting_section = None
        self.work_package = None
        self.author = None
        self.presenter = None
        self.project = None
        self.outcomes: List[Any] = []

    def get_display_title(self) -> str:
        """
        Get the appropriate title to display.

        For work package items, returns the work package subject.
        For simple items, returns the title.
        """
        if self.is_work_package_type() and self.work_package:
            return getattr(self.work_package, 'subject', self.title or "")
        return self.title or ""

    def is_simple_type(self) -> bool:
        """Check if this is a simple agenda item."""
        return self.item_type == AgendaItemType.SIMPLE

    def is_work_package_type(self) -> bool:
        """Check if this is a work package agenda item."""
        return self.item_type == AgendaItemType.WORK_PACKAGE

    def is_linked_to_work_package(self) -> bool:
        """Check if this item is linked to a work package."""
        return self.work_package_id is not None

    def is_work_package_visible(self) -> bool:
        """Check if the linked work package is visible."""
        return self.work_package is not None

    def is_work_package_deleted(self) -> bool:
        """Check if the linked work package was deleted."""
        return self.is_linked_to_work_package() and not self.is_work_package_visible()

    def is_in_backlog(self) -> bool:
        """Check if this item is in the backlog section."""
        if self.meeting_section:
            return getattr(self.meeting_section, 'backlog', False)
        return False

    def is_editable(self) -> bool:
        """
        Check if this item can be edited.

        Items cannot be edited if they reference a deleted work package.
        """
        if self.is_work_package_type() and self.is_work_package_deleted():
            return False
        return True

    def validate(self) -> Dict[str, List[str]]:
        """
        Validate the agenda item.

        Returns:
            Dict mapping field names to lists of error messages
        """
        errors = {}

        if not self.meeting_id and not self.meeting:
            errors.setdefault("meeting_id", []).append("Meeting is required")

        # Simple items require a title
        if self.is_simple_type() and (not self.title or not self.title.strip()):
            errors.setdefault("title", []).append(
                "Title is required for simple agenda items"
            )

        # Work package items require a work package
        if self.is_work_package_type() and not self.work_package_id:
            errors.setdefault("work_package_id", []).append(
                "Work package is required for work package agenda items"
            )

        # Duration validation
        if self.duration_in_minutes is not None:
            if self.duration_in_minutes < self.MIN_DURATION:
                errors.setdefault("duration_in_minutes", []).append(
                    f"Duration must be at least {self.MIN_DURATION} minutes"
                )
            elif self.duration_in_minutes > self.MAX_DURATION:
                errors.setdefault("duration_in_minutes", []).append(
                    f"Duration must be at most {self.MAX_DURATION} minutes"
                )

        return errors

    def copy_attributes(self) -> Dict[str, Any]:
        """
        Get attributes for copying this item.

        Excludes: id, meeting_id, meeting_section_id, position, timestamps
        """
        return {
            "author_id": self.author_id,
            "presenter_id": self.presenter_id,
            "work_package_id": self.work_package_id,
            "title": self.title,
            "notes": self.notes,
            "duration_in_minutes": self.duration_in_minutes,
            "item_type": self.item_type,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert agenda item to dictionary representation."""
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "author_id": self.author_id,
            "presenter_id": self.presenter_id,
            "meeting_section_id": self.meeting_section_id,
            "work_package_id": self.work_package_id,
            "title": self.get_display_title(),
            "notes": self.notes,
            "position": self.position,
            "duration_in_minutes": self.duration_in_minutes,
            "item_type": self.item_type.name.lower(),
            "lock_version": self.lock_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
