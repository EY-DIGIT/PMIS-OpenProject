"""
MeetingParticipant domain model for OpenProject Python port.

This module contains the domain model for meeting participants.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class ParticipationStatus(Enum):
    """Participation status enumeration (based on iCal PARTSTAT)."""
    NEEDS_ACTION = "needs-action"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    DELEGATED = "delegated"
    UNKNOWN = "unknown"  # for existing participants


class MeetingParticipant:
    """
    MeetingParticipant domain model representing a participant in a meeting.

    Attributes:
        id: Unique identifier
        user_id: ID of the user participant
        meeting_id: ID of the associated meeting
        email: Participant email
        name: Participant name
        invited: Whether the participant was invited
        attended: Whether the participant attended
        participation_status: Current participation status
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    def __init__(
        self,
        id: Optional[int] = None,
        user_id: Optional[int] = None,
        meeting_id: Optional[int] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
        invited: bool = False,
        attended: bool = False,
        participation_status: ParticipationStatus = ParticipationStatus.NEEDS_ACTION,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.meeting_id = meeting_id
        self.email = email
        self.name = name
        self.invited = invited
        self.attended = attended
        self.participation_status = participation_status
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

        # Associations (loaded separately)
        self.user = None
        self.meeting = None

    def get_name(self) -> str:
        """
        Get the participant name.

        Returns the user's name if available, or the stored name,
        or "deleted" if neither is available.
        """
        if self.user and hasattr(self.user, 'name'):
            return self.user.name
        return self.name or "deleted"

    def get_email(self) -> str:
        """
        Get the participant email.

        Returns the user's email if available, or the stored email,
        or "deleted" if neither is available.
        """
        if self.user and hasattr(self.user, 'mail'):
            return self.user.mail
        return self.email or "deleted"

    def is_invited(self) -> bool:
        """Check if the participant was invited."""
        return self.invited

    def is_attended(self) -> bool:
        """Check if the participant attended."""
        return self.attended

    def has_accepted(self) -> bool:
        """Check if the participant has accepted the invitation."""
        return self.participation_status == ParticipationStatus.ACCEPTED

    def has_declined(self) -> bool:
        """Check if the participant has declined the invitation."""
        return self.participation_status == ParticipationStatus.DECLINED

    def is_tentative(self) -> bool:
        """Check if the participant's status is tentative."""
        return self.participation_status == ParticipationStatus.TENTATIVE

    def validate(self) -> Dict[str, List[str]]:
        """
        Validate the participant.

        Returns:
            Dict mapping field names to lists of error messages
        """
        errors = {}

        if not self.user_id:
            errors.setdefault("user_id", []).append("User is required")

        if not self.meeting_id:
            errors.setdefault("meeting_id", []).append("Meeting is required")

        return errors

    def copy_attributes(self) -> Dict[str, Any]:
        """
        Get attributes for copying this participant.

        Excludes: id, meeting_id, attended, timestamps
        """
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "invited": self.invited,
            "participation_status": self.participation_status,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert participant to dictionary representation."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "meeting_id": self.meeting_id,
            "email": self.get_email(),
            "name": self.get_name(),
            "invited": self.invited,
            "attended": self.attended,
            "participation_status": self.participation_status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __str__(self) -> str:
        """String representation of the participant."""
        return self.get_name()

    def __lt__(self, other: 'MeetingParticipant') -> bool:
        """Comparison for sorting participants."""
        return self.get_name().lower() < other.get_name().lower()
