"""
Meeting Participant repository for database operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from ...db.models.meeting_participant import MeetingParticipantModel
from ....domain.meetings.participant import MeetingParticipant


class MeetingParticipantRepository:
    """Repository for Meeting Participant database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def _to_domain(self, model: MeetingParticipantModel) -> MeetingParticipant:
        """
        Convert database model to domain model.

        Args:
            model: Database model

        Returns:
            Domain model
        """
        return MeetingParticipant(
            id=model.id,
            meeting_id=model.meeting_id,
            user_id=model.user_id,
            created_at=model.created_at,
        )

    def create(self, meeting_id: int, user_id: int) -> MeetingParticipant:
        """
        Add a participant to a meeting.

        Args:
            meeting_id: Meeting ID
            user_id: User ID

        Returns:
            Created participant domain model
        """
        participant_model = MeetingParticipantModel(
            meeting_id=meeting_id,
            user_id=user_id,
        )

        self.db.add(participant_model)
        self.db.commit()
        self.db.refresh(participant_model)

        return self._to_domain(participant_model)

    def get_by_id(self, participant_id: int) -> Optional[MeetingParticipant]:
        """
        Get participant by ID.

        Args:
            participant_id: Participant ID

        Returns:
            Participant if found, None otherwise
        """
        model = self.db.query(MeetingParticipantModel).filter(
            MeetingParticipantModel.id == participant_id
        ).first()
        return self._to_domain(model) if model else None

    def list_by_meeting(self, meeting_id: int) -> List[MeetingParticipant]:
        """
        List all participants in a meeting.

        Args:
            meeting_id: Meeting ID

        Returns:
            List of participants
        """
        models = self.db.query(MeetingParticipantModel).filter(
            MeetingParticipantModel.meeting_id == meeting_id
        ).all()
        return [self._to_domain(m) for m in models]

    def exists(self, meeting_id: int, user_id: int) -> bool:
        """
        Check if user is a participant in meeting.

        Args:
            meeting_id: Meeting ID
            user_id: User ID

        Returns:
            True if participant exists, False otherwise
        """
        return self.db.query(
            self.db.query(MeetingParticipantModel).filter(
                MeetingParticipantModel.meeting_id == meeting_id,
                MeetingParticipantModel.user_id == user_id
            ).exists()
        ).scalar()

    def delete(self, meeting_id: int, user_id: int) -> bool:
        """
        Remove a participant from a meeting.

        Args:
            meeting_id: Meeting ID
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        model = self.db.query(MeetingParticipantModel).filter(
            MeetingParticipantModel.meeting_id == meeting_id,
            MeetingParticipantModel.user_id == user_id
        ).first()
        if not model:
            return False

        self.db.delete(model)
        self.db.commit()

        return True

    def delete_by_id(self, participant_id: int) -> bool:
        """
        Delete a participant by ID.

        Args:
            participant_id: Participant ID

        Returns:
            True if deleted, False if not found
        """
        model = self.db.query(MeetingParticipantModel).filter(
            MeetingParticipantModel.id == participant_id
        ).first()
        if not model:
            return False

        self.db.delete(model)
        self.db.commit()

        return True
