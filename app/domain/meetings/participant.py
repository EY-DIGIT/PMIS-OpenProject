"""
Meeting Participant domain model.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ...shared.datetime import iso_ist


@dataclass
class MeetingParticipant:
    """
    Meeting Participant domain entity.

    Represents a user's participation in a meeting.
    Participant must be a project member.
    """

    id: int
    meeting_id: int
    user_id: str  # doc 26: UUID string
    created_at: datetime

    def to_dict(self) -> dict:
        """
        Convert participant to dictionary.

        Returns:
            Dictionary representation of participant
        """
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "user_id": self.user_id,
            "created_at": iso_ist(self.created_at),
        }
