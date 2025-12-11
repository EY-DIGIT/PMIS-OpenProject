"""
Meeting services for business logic operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from ..utils.service_result import ServiceResult
    from ..repositories import MeetingRepository, MeetingParticipantRepository
    from ..models.meeting import Meeting, MeetingState
    from ..models.meeting_participant import MeetingParticipant, ParticipationStatus
    from .base_service import BaseService, BaseCreateService, BaseUpdateService
except ImportError:
    from utils.service_result import ServiceResult
    from repositories import MeetingRepository, MeetingParticipantRepository
    from models.meeting import Meeting, MeetingState
    from models.meeting_participant import MeetingParticipant, ParticipationStatus
    from services.base_service import BaseService, BaseCreateService, BaseUpdateService


class MeetingCreateService(BaseCreateService):
    """Service for creating meetings"""

    def __init__(self, user, db):
        super().__init__(user)
        self.db = db
        self.meeting_repo = MeetingRepository(db)
        self.participant_repo = MeetingParticipantRepository(db)

    def call(self, params: Dict[str, Any]) -> ServiceResult:
        """
        Create a new meeting.

        Args:
            params: Meeting parameters including:
                - title: Meeting title (required)
                - project_id: Project ID (required)
                - location: Meeting location (optional)
                - start_time: Start time (optional)
                - duration: Duration in hours (default: 1.0)
                - state: Meeting state (default: open)
                - notify: Send notifications (default: True)
                - participants: List of participant dicts (optional)

        Returns:
            ServiceResult with created Meeting
        """
        # Get state enum
        state_str = params.get('state', 'open')
        try:
            state = MeetingState[state_str.upper()]
        except (KeyError, AttributeError):
            state = MeetingState.OPEN

        # Create meeting instance
        meeting = Meeting(
            title=params.get('title'),
            author_id=self.user.id,
            project_id=params.get('project_id'),
            location=params.get('location'),
            start_time=params.get('start_time'),
            duration=params.get('duration', 1.0),
            state=state,
            notify=params.get('notify', True),
        )

        # Validate
        errors = meeting.validate()
        if errors:
            return ServiceResult.failure_result(errors=errors)

        # Check authorization
        if not self.authorized(meeting):
            return ServiceResult.failure_result(
                message="Not authorized to create meetings in this project"
            )

        # Create meeting
        created_meeting = self.meeting_repo.create(meeting)

        # Create participants
        participants = params.get('participants', [])
        for p_data in participants:
            # Get participation status
            status_str = p_data.get('participation_status', 'needs-action')
            try:
                participation_status = ParticipationStatus(status_str)
            except ValueError:
                participation_status = ParticipationStatus.NEEDS_ACTION

            participant = MeetingParticipant(
                user_id=p_data.get('user_id'),
                meeting_id=created_meeting.id,
                invited=p_data.get('invited', True),
                participation_status=participation_status,
            )
            self.participant_repo.create(participant)

        self.db.commit()

        return ServiceResult.success_result(result=created_meeting)

    def authorized(self, meeting: Meeting) -> bool:
        """Check if user can create meetings"""
        # Admin can always create
        if self.user.admin:
            return True

        # Check project membership and permissions
        # TODO: Implement project-specific permission check
        return True


class MeetingUpdateService(BaseUpdateService):
    """Service for updating meetings"""

    def __init__(self, user, db):
        super().__init__(user)
        self.db = db
        self.meeting_repo = MeetingRepository(db)

    def call(self, meeting_id: int, params: Dict[str, Any]) -> ServiceResult:
        """
        Update an existing meeting.

        Args:
            meeting_id: ID of meeting to update
            params: Fields to update

        Returns:
            ServiceResult with updated Meeting
        """
        # Find meeting
        meeting = self.meeting_repo.find_by_id(meeting_id)
        if not meeting:
            return ServiceResult.failure_result(message="Meeting not found")

        # Check authorization
        if not self.authorized(meeting):
            return ServiceResult.failure_result(message="Not authorized to update this meeting")

        # Update fields
        if 'title' in params:
            meeting.title = params['title']
        if 'location' in params:
            meeting.location = params['location']
        if 'start_time' in params:
            meeting.start_time = params['start_time']
        if 'duration' in params:
            meeting.duration = params['duration']
        if 'state' in params:
            state_str = params['state']
            try:
                meeting.state = MeetingState[state_str.upper()]
            except (KeyError, AttributeError):
                pass
        if 'notify' in params:
            meeting.notify = params['notify']

        meeting.updated_at = datetime.utcnow()

        # Validate
        errors = meeting.validate()
        if errors:
            return ServiceResult.failure_result(errors=errors)

        # Update
        updated_meeting = self.meeting_repo.update(meeting)
        self.db.commit()

        return ServiceResult.success_result(result=updated_meeting)

    def authorized(self, meeting: Meeting) -> bool:
        """Check if user can update meeting"""
        if self.user.admin:
            return True

        # Author can update
        if meeting.author_id == self.user.id:
            return True

        # TODO: Check project permissions
        return False


class MeetingDeleteService(BaseService):
    """Service for deleting meetings"""

    def __init__(self, user, db):
        super().__init__(user)
        self.db = db
        self.meeting_repo = MeetingRepository(db)

    def call(self, meeting_id: int) -> ServiceResult:
        """Delete a meeting"""
        meeting = self.meeting_repo.find_by_id(meeting_id)
        if not meeting:
            return ServiceResult.failure_result(message="Meeting not found")

        if not self.authorized(meeting):
            return ServiceResult.failure_result(message="Not authorized to delete this meeting")

        self.meeting_repo.delete(meeting_id)
        self.db.commit()

        return ServiceResult.success_result(message="Meeting deleted successfully")

    def authorized(self, meeting: Meeting) -> bool:
        """Check if user can delete meeting"""
        if self.user.admin:
            return True

        if meeting.author_id == self.user.id:
            return True

        return False


class MeetingListService(BaseService):
    """Service for listing meetings"""

    def __init__(self, user, db):
        super().__init__(user)
        self.db = db
        self.meeting_repo = MeetingRepository(db)

    def call(
        self,
        project_id: Optional[int] = None,
        state: Optional[str] = None,
        upcoming: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> ServiceResult:
        """
        List meetings with filters.

        Args:
            project_id: Filter by project
            state: Filter by state
            upcoming: Show only upcoming meetings
            limit: Maximum results
            offset: Skip results

        Returns:
            ServiceResult with list of meetings and count
        """
        meetings = self.meeting_repo.find_all(
            project_id=project_id,
            state=state,
            upcoming=upcoming,
            limit=limit,
            offset=offset
        )

        total_count = self.meeting_repo.count(project_id=project_id)

        return ServiceResult.success_result(
            result={
                'meetings': meetings,
                'count': total_count,
                'limit': limit,
                'offset': offset
            }
        )
