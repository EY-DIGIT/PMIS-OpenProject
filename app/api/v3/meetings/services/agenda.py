"""
Meeting agenda item services.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.infrastructure.db.repositories.meeting_agenda_repository import MeetingAgendaItemRepository
from app.infrastructure.db.repositories.meeting_repository import MeetingRepository
from app.infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from app.domain.meetings.agenda_item import AgendaItem
from app.shared.service_result import ServiceResult
from app.shared.utils import normalize_string


def create_agenda_item(
    db: Session,
    meeting_id: int,
    project_id: str,
    title: str,
    position: int,
    description: Optional[str] = None,
    work_package_id: Optional[int] = None,
) -> ServiceResult[AgendaItem]:
    """
    Create an agenda item for a meeting.

    Args:
        db: Database session
        meeting_id: Meeting ID
        project_id: Project ID
        title: Agenda item title
        position: Position in agenda
        description: Agenda item description
        work_package_id: Optional work package ID

    Returns:
        ServiceResult with created agenda item or error
    """
    try:
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

        if position < 0:
            return ServiceResult.fail(
                error="Position must be non-negative.",
                error_type="validation_error"
            )

        meeting_repo = MeetingRepository(db)

        # Verify meeting exists and belongs to project
        if not meeting_repo.exists_in_project(meeting_id, project_id):
            return ServiceResult.fail(
                error=f"Meeting with ID {meeting_id} not found in project {project_id}",
                error_type="not_found"
            )

        # Verify work package if provided
        if work_package_id is not None:
            wp_repo = WorkPackageRepository(db)
            wp = wp_repo.get_by_id(work_package_id)
            if not wp or wp.project_id != project_id:
                return ServiceResult.fail(
                    error=f"Work package with ID {work_package_id} not found in project",
                    error_type="not_found"
                )

        agenda_repo = MeetingAgendaItemRepository(db)
        agenda_item = agenda_repo.create(
            meeting_id=meeting_id,
            project_id=project_id,
            title=title,
            position=position,
            description=description,
            work_package_id=work_package_id,
        )

        return ServiceResult.ok(agenda_item)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )


def get_agenda_item(
    db: Session,
    agenda_item_id: int,
) -> ServiceResult[AgendaItem]:
    """
    Get an agenda item by ID.

    Args:
        db: Database session
        agenda_item_id: Agenda item ID

    Returns:
        ServiceResult with agenda item or error
    """
    try:
        agenda_repo = MeetingAgendaItemRepository(db)
        agenda_item = agenda_repo.get_by_id(agenda_item_id)

        if not agenda_item:
            return ServiceResult.fail(
                error=f"Agenda item with ID {agenda_item_id} not found",
                error_type="not_found"
            )

        return ServiceResult.ok(agenda_item)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )


def list_agenda_items(
    db: Session,
    meeting_id: int,
) -> ServiceResult[List[AgendaItem]]:
    """
    List all agenda items in a meeting.

    Args:
        db: Database session
        meeting_id: Meeting ID

    Returns:
        ServiceResult with list of agenda items or error
    """
    try:
        agenda_repo = MeetingAgendaItemRepository(db)
        agenda_items = agenda_repo.list_by_meeting(meeting_id)
        return ServiceResult.ok(agenda_items)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )


def update_agenda_item(
    db: Session,
    agenda_item_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    position: Optional[int] = None,
    work_package_id: Optional[int] = None,
) -> ServiceResult[AgendaItem]:
    """
    Update an agenda item.

    Args:
        db: Database session
        agenda_item_id: Agenda item ID
        title: New title
        description: New description
        position: New position
        work_package_id: New work package ID

    Returns:
        ServiceResult with updated agenda item or error
    """
    try:
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

        if position is not None and position < 0:
            return ServiceResult.fail(
                error="Position must be non-negative.",
                error_type="validation_error"
            )

        agenda_repo = MeetingAgendaItemRepository(db)
        agenda_item = agenda_repo.update(
            agenda_item_id=agenda_item_id,
            title=title,
            description=description,
            position=position,
            work_package_id=work_package_id,
        )

        if not agenda_item:
            return ServiceResult.fail(
                error=f"Agenda item with ID {agenda_item_id} not found",
                error_type="not_found"
            )

        return ServiceResult.ok(agenda_item)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )


def delete_agenda_item(
    db: Session,
    agenda_item_id: int,
) -> ServiceResult[bool]:
    """
    Delete an agenda item.

    Args:
        db: Database session
        agenda_item_id: Agenda item ID

    Returns:
        ServiceResult with success or error
    """
    try:
        agenda_repo = MeetingAgendaItemRepository(db)

        deleted = agenda_repo.delete(agenda_item_id)

        if not deleted:
            return ServiceResult.fail(
                error=f"Agenda item with ID {agenda_item_id} not found",
                error_type="not_found"
            )

        return ServiceResult.ok(True)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )
