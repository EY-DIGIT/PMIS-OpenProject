"""
Meeting retrieval service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.infrastructure.db.repositories.meeting_repository import MeetingRepository
from app.domain.meetings.meeting import Meeting
from app.shared.service_result import ServiceResult


def get_meeting_by_id(
    db: Session,
    meeting_id: int,
) -> ServiceResult[Meeting]:
    """
    Get a meeting by ID.

    Args:
        db: Database session
        meeting_id: Meeting ID

    Returns:
        ServiceResult with meeting or error
    """
    try:
        meeting_repo = MeetingRepository(db)
        meeting = meeting_repo.get_by_id(meeting_id)

        if not meeting:
            return ServiceResult.fail(
                error=f"Meeting with ID {meeting_id} not found",
                error_type="not_found"
            )

        return ServiceResult.ok(meeting)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )
