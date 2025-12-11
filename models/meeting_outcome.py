"""
MeetingOutcome domain model for OpenProject Python port.

This module contains the domain model for meeting outcomes (decisions, actions, etc.).
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class OutcomeKind(Enum):
    """Outcome kind enumeration."""
    INFORMATION = 0
    DECISION = 1
    WORK_PACKAGE = 2


class MeetingOutcome:
    """
    MeetingOutcome domain model representing an outcome from a meeting agenda item.

    Outcomes can be:
    - Information: Notes or observations
    - Decision: Decisions made during the meeting
    - Work Package: Action items as work packages

    Attributes:
        id: Unique identifier
        meeting_agenda_item_id: ID of the associated agenda item
        work_package_id: ID of linked work package (if kind is WORK_PACKAGE)
        author_id: ID of the user who created the outcome
        notes: Outcome notes/description
        kind: Type of outcome (INFORMATION, DECISION, WORK_PACKAGE)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    def __init__(
        self,
        id: Optional[int] = None,
        meeting_agenda_item_id: Optional[int] = None,
        work_package_id: Optional[int] = None,
        author_id: Optional[int] = None,
        notes: Optional[str] = None,
        kind: OutcomeKind = OutcomeKind.INFORMATION,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.meeting_agenda_item_id = meeting_agenda_item_id
        self.work_package_id = work_package_id
        self.author_id = author_id
        self.notes = notes
        self.kind = kind
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

        # Associations (loaded separately)
        self.meeting_agenda_item = None
        self.work_package = None
        self.author = None

    def is_information(self) -> bool:
        """Check if this is an information outcome."""
        return self.kind == OutcomeKind.INFORMATION

    def is_decision(self) -> bool:
        """Check if this is a decision outcome."""
        return self.kind == OutcomeKind.DECISION

    def is_work_package(self) -> bool:
        """Check if this is a work package outcome."""
        return self.kind == OutcomeKind.WORK_PACKAGE

    def is_editable(self) -> bool:
        """
        Check if this outcome can be edited.

        Outcomes can only be edited when the meeting is in progress.
        """
        if self.meeting_agenda_item and hasattr(self.meeting_agenda_item, 'meeting'):
            meeting = self.meeting_agenda_item.meeting
            if meeting and hasattr(meeting, 'is_in_progress'):
                return meeting.is_in_progress()
        return False

    def validate(self) -> Dict[str, List[str]]:
        """
        Validate the outcome.

        Returns:
            Dict mapping field names to lists of error messages
        """
        errors = {}

        if not self.meeting_agenda_item_id:
            errors.setdefault("meeting_agenda_item_id", []).append(
                "Meeting agenda item is required"
            )

        # Information outcomes require notes
        if self.is_information() and (not self.notes or not self.notes.strip()):
            errors.setdefault("notes", []).append(
                "Notes are required for information outcomes"
            )

        # Work package outcomes require a work package
        if self.is_work_package() and not self.work_package_id:
            errors.setdefault("work_package_id", []).append(
                "Work package is required for work package outcomes"
            )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert outcome to dictionary representation."""
        return {
            "id": self.id,
            "meeting_agenda_item_id": self.meeting_agenda_item_id,
            "work_package_id": self.work_package_id,
            "author_id": self.author_id,
            "notes": self.notes,
            "kind": self.kind.name.lower(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
