"""
Meeting deletion service.
"""
from sqlalchemy.orm import Session
from app.infrastructure.db.repositories.meeting_repository import MeetingRepository
from app.infrastructure.db.repositories.meeting_participant_repository import MeetingParticipantRepository
from app.infrastructure.db.repositories.meeting_agenda_repository import MeetingAgendaItemRepository
from app.shared.service_result import ServiceResult


def delete_meeting(
    db: Session,
    meeting_id: int,
) -> ServiceResult[bool]:
    """
    Delete a meeting and all associated participants and agenda items.

    Args:
        db: Database session
        meeting_id: Meeting ID

    Returns:
        ServiceResult with success or error
    """
    try:
        meeting_repo = MeetingRepository(db)

        # Check if meeting exists
        if not meeting_repo.exists_by_id(meeting_id):
            return ServiceResult.fail(
                error=f"Meeting with ID {meeting_id} not found",
                error_type="not_found"
            )

        # Delete agenda items
        agenda_repo = MeetingAgendaItemRepository(db)
        agenda_items = agenda_repo.list_by_meeting(meeting_id)
        for agenda_item in agenda_items:
            agenda_repo.delete(agenda_item.id)

        # Delete participants
        participant_repo = MeetingParticipantRepository(db)
        participants = participant_repo.list_by_meeting(meeting_id)
        for participant in participants:
            participant_repo.delete_by_id(participant.id)

        # Delete meeting
        deleted = meeting_repo.delete(meeting_id)

        if not deleted:
            return ServiceResult.fail(
                error=f"Failed to delete meeting with ID {meeting_id}",
                error_type="database_error"
            )

        return ServiceResult.ok(True)
    except Exception as e:
        return ServiceResult.fail(
            error=str(e),
            error_type="database_error"
        )
