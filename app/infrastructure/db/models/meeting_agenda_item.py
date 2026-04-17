"""
Meeting Agenda Item database model.
"""
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)
from sqlalchemy import Column, Integer, String, DateTime, Index, ForeignKey, Text
from ..session import Base


class MeetingAgendaItemModel(Base):
    """Meeting Agenda Item database model."""

    __tablename__ = "meeting_agenda_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    position = Column(Integer, nullable=False, index=True)
    work_package_id = Column(Integer, ForeignKey("work_packages.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_agenda_items_meeting_id", "meeting_id"),
        Index("idx_agenda_items_project_id", "project_id"),
        Index("idx_agenda_items_work_package_id", "work_package_id"),
        Index("idx_agenda_items_position", "position"),
    )

    def __repr__(self) -> str:
        return f"<MeetingAgendaItemModel(id={self.id}, meeting_id={self.meeting_id}, position={self.position})>"
