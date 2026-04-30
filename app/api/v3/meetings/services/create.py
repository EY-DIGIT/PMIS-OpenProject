"""
Meeting creation service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.core.errors import ValidationError, NotFoundError
from app.infrastructure.db.repositories.meeting_repository import MeetingRepository
from app.infrastructure.db.repositories.project_repository import ProjectRepository
from app.domain.meetings.meeting import Meeting
from app.shared.service_result import ServiceResult
from app.shared.utils import normalize_string
from datetime import datetime, timezone


def create_meeting(
    db: Session,
    project_id: str,
    title: str,
    scheduled_at: datetime,
    created_by_id: int,
    description: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    location: Optional[str] = None,
) -> ServiceResult[Meeting]:
    """
    Create a new meeting.

    Args:
        db: Database session
        project_id: Project ID
        title: Meeting title
        scheduled_at: Meeting scheduled time
        created_by_id: User ID of creator
        description: Meeting description
        duration_minutes: Meeting duration in minutes
        location: Meeting location

    Returns:
        ServiceResult with created meeting or error
    """
    # Validate inputs
    title = normalize_string(title) if title else ""

    if not title or len(title) > 255:
        return ServiceResult.fail(
            error="Invalid title. Must be 1-255 characters.",
            error_type="validation_error"
        )

    if description and len(description) > 5000:
        return ServiceResult.fail(
            error="Description too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    if location and len(location) > 255:
        return ServiceResult.fail(
            error="Location too long. Maximum 255 characters.",
            error_type="validation_error"
        )

    if duration_minutes is not None and (duration_minutes < 0 or duration_minutes > 10080):  # 10080 = 7 days
        return ServiceResult.fail(
            error="Invalid duration. Must be between 0 and 10080 minutes.",
            error_type="validation_error"
        )

    # Normalize scheduled_at to UTC-aware datetime for safe comparison/storage
    try:
        scheduled_at_utc = scheduled_at.astimezone(timezone.utc)
    except Exception:
        # If scheduled_at is naive, assume UTC and set tzinfo
        scheduled_at_utc = scheduled_at.replace(tzinfo=timezone.utc)

    if scheduled_at_utc <= datetime.now(timezone.utc):
        return ServiceResult.fail(
            error="Scheduled time must be in the future.",
            error_type="validation_error"
        )

    # Verify project exists
    project_repo = ProjectRepository(db)
    if not project_repo.exists_by_id(project_id):
        return ServiceResult.fail(
            error=f"Project with ID {project_id} does not exist",
            error_type="not_found"
        )

    # Create meeting
    try:
        meeting_repo = MeetingRepository(db)
        meeting = meeting_repo.create(
            project_id=project_id,
            title=title,
            scheduled_at=scheduled_at_utc,
            created_by_id=created_by_id,
            description=description,
            duration_minutes=duration_minutes,
            location=location,
        )
        return ServiceResult.ok(meeting)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )
