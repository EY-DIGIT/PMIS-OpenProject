"""
Meeting listing service.
"""
from typing import Tuple, List
from sqlalchemy.orm import Session
from app.infrastructure.db.repositories.meeting_repository import MeetingRepository
from app.domain.meetings.meeting import Meeting
from app.shared.service_result import ServiceResult


def list_meetings_by_project(
    db: Session,
    project_id: int,
    offset: int = 0,
    limit: int = 20,
) -> ServiceResult[Tuple[List[Meeting], int]]:
    """
    List meetings in a project.

    Args:
        db: Database session
        project_id: Project ID
        offset: Number of items to skip
        limit: Maximum number of items to return

    Returns:
        ServiceResult with (list of meetings, total count) or error
    """
    try:
        # Validate pagination
        if offset < 0:
            return ServiceResult.fail(
                error="Offset must be non-negative.",
                error_type="validation_error"
            )

        if limit < 1 or limit > 100:
            return ServiceResult.fail(
                error="Limit must be between 1 and 100.",
                error_type="validation_error"
            )

        meeting_repo = MeetingRepository(db)
        meetings, total = meeting_repo.list_by_project(
            project_id=project_id,
            offset=offset,
            limit=limit
        )

        return ServiceResult.ok((meetings, total))
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )
