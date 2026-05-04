"""
Meeting participant services.
"""
from typing import List
from sqlalchemy.orm import Session
from app.infrastructure.db.repositories.meeting_participant_repository import MeetingParticipantRepository
from app.infrastructure.db.repositories.meeting_repository import MeetingRepository
from app.infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from app.domain.meetings.participant import MeetingParticipant
from app.shared.service_result import ServiceResult


def add_participant(
    db: Session,
    meeting_id: int,
    user_id: str,
    project_id: str,
) -> ServiceResult[MeetingParticipant]:
    """
    Add a participant to a meeting.

    Args:
        db: Database session
        meeting_id: Meeting ID
        user_id: User ID
        project_id: Project ID (for validation)

    Returns:
        ServiceResult with created participant or error
    """
    try:
        meeting_repo = MeetingRepository(db)
        participant_repo = MeetingParticipantRepository(db)
        project_member_repo = ProjectMemberRepository(db)

        # Verify meeting exists and belongs to project
        if not meeting_repo.exists_in_project(meeting_id, project_id):
            return ServiceResult.fail(
                error=f"Meeting with ID {meeting_id} not found in project {project_id}",
                error_type="not_found"
            )

        # Verify user is a project member
        if not project_member_repo.exists_by_project_and_user(project_id, user_id):
            return ServiceResult.fail(
                error=f"User with ID {user_id} is not a member of project {project_id}",
                error_type="forbidden"
            )

        # Check if already a participant
        if participant_repo.exists(meeting_id, user_id):
            return ServiceResult.fail(
                error=f"User with ID {user_id} is already a participant in meeting {meeting_id}",
                error_type="conflict"
            )

        # Add participant
        participant = participant_repo.create(meeting_id, user_id)
        return ServiceResult.ok(participant)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )


def list_participants(
    db: Session,
    meeting_id: int,
) -> ServiceResult[List[MeetingParticipant]]:
    """
    List all participants in a meeting.

    Args:
        db: Database session
        meeting_id: Meeting ID

    Returns:
        ServiceResult with list of participants or error
    """
    try:
        meeting_repo = MeetingRepository(db)
        participant_repo = MeetingParticipantRepository(db)

        # Verify meeting exists
        if not meeting_repo.exists_by_id(meeting_id):
            return ServiceResult.fail(
                error=f"Meeting with ID {meeting_id} does not exist",
                error_type="not_found"
            )

        participants = participant_repo.list_by_meeting(meeting_id)
        return ServiceResult.ok(participants)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )


def remove_participant(
    db: Session,
    meeting_id: int,
    user_id: str,
) -> ServiceResult[bool]:
    """
    Remove a participant from a meeting.

    Args:
        db: Database session
        meeting_id: Meeting ID
        user_id: User ID

    Returns:
        ServiceResult with success or error
    """
    try:
        participant_repo = MeetingParticipantRepository(db)

        # Delete participant
        deleted = participant_repo.delete(meeting_id, user_id)

        if not deleted:
            return ServiceResult.fail(
                error=f"Participant not found",
                error_type="not_found"
            )

        return ServiceResult.ok(True)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )
