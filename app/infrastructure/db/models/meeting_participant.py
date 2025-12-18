"""
Meeting Participant database model.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, Index, ForeignKey, UniqueConstraint
from ..session import Base


class MeetingParticipantModel(Base):
    """Meeting Participant database model."""

    __tablename__ = "meeting_participants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Unique constraint: one participation per meeting-user pair
    __table_args__ = (
        UniqueConstraint("meeting_id", "user_id", name="uq_meeting_user"),
        Index("idx_meeting_participants_meeting_id", "meeting_id"),
        Index("idx_meeting_participants_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<MeetingParticipantModel(id={self.id}, meeting_id={self.meeting_id}, user_id={self.user_id})>"
