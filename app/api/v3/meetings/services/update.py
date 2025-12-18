"""
Meeting update service.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.infrastructure.db.repositories.meeting_repository import MeetingRepository
from app.domain.meetings.meeting import Meeting
from app.shared.service_result import ServiceResult
from app.shared.utils import normalize_string


def update_meeting(
    db: Session,
    meeting_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    scheduled_at: Optional[datetime] = None,
    duration_minutes: Optional[int] = None,
    location: Optional[str] = None,
) -> ServiceResult[Meeting]:
    """
    Update a meeting.

    Args:
        db: Database session
        meeting_id: Meeting ID
        title: New title
        description: New description
        scheduled_at: New scheduled time
        duration_minutes: New duration in minutes
        location: New location

    Returns:
        ServiceResult with updated meeting or error
    """
    # Validate inputs
    if title is not None:
        title = normalize_string(title)
        if not title or len(title) > 255:
            return ServiceResult.fail(
                error="Invalid title. Must be 1-255 characters.",
                error_type="validation_error"
            )

    if description is not None and len(description) > 5000:
        return ServiceResult.fail(
            error="Description too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    if location is not None and len(location) > 255:
        return ServiceResult.fail(
            error="Location too long. Maximum 255 characters.",
            error_type="validation_error"
        )

    if duration_minutes is not None and (duration_minutes < 0 or duration_minutes > 10080):
        return ServiceResult.fail(
            error="Invalid duration. Must be between 0 and 10080 minutes.",
            error_type="validation_error"
        )

    if scheduled_at is not None:
        try:
            scheduled_at_utc = scheduled_at.astimezone(timezone.utc)
        except Exception:
            scheduled_at_utc = scheduled_at.replace(tzinfo=timezone.utc)

        if scheduled_at_utc <= datetime.now(timezone.utc):
            return ServiceResult.fail(
                error="Scheduled time must be in the future.",
                error_type="validation_error"
            )
    else:
        scheduled_at_utc = None

    try:
        meeting_repo = MeetingRepository(db)
        meeting = meeting_repo.update(
            meeting_id=meeting_id,
            title=title,
            description=description,
            scheduled_at=scheduled_at_utc,
            duration_minutes=duration_minutes,
            location=location,
        )

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
