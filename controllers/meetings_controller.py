"""
Meetings Controller - Handles meeting-related requests.

This controller acts as an intermediary between routes and services,
handling request/response formatting and service orchestration.
"""

from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user import User
from models.meeting import Meeting
from services.meetings import (
    MeetingCreateService,
    MeetingUpdateService,
    MeetingDeleteService,
    MeetingListService,
)
from repositories import MeetingRepository
from schemas.meeting import (
    MeetingCreate,
    MeetingUpdate,
    MeetingResponse,
    HALLink,
    HALLinks,
    MeetingStateEnum,
)


class MeetingsController:
    """Controller for meeting operations"""

    @staticmethod
    def meeting_to_response(meeting: Meeting, base_url: str = "http://localhost:8000") -> MeetingResponse:
        """Convert Meeting domain model to API response"""
        return MeetingResponse(
            id=meeting.id,
            title=meeting.title,
            author_id=meeting.author_id,
            project_id=meeting.project_id,
            location=meeting.location,
            start_time=meeting.start_time,
            duration=meeting.duration,
            state=MeetingStateEnum(meeting.state.name.lower()),
            lock_version=meeting.lock_version,
            recurring_meeting_id=meeting.recurring_meeting_id,
            template=meeting.template,
            notify=meeting.notify,
            uid=meeting.uid,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
            _links=HALLinks(
                self=HALLink(href=f"{base_url}/api/v3/meetings/{meeting.id}"),
            ),
        )

    @staticmethod
    def list_meetings(
        db: Session,
        current_user: Optional[User],
        project_id: Optional[int] = None,
        state: Optional[str] = None,
        upcoming: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> List[MeetingResponse]:
        """
        List meetings with optional filters.

        Args:
            db: Database session
            current_user: Current user (may be None for public access)
            project_id: Filter by project
            state: Filter by state
            upcoming: Show only upcoming meetings
            limit: Maximum results
            offset: Skip results

        Returns:
            List of meeting responses
        """
        # Get or create a default user for unauthenticated requests
        if not current_user:
            from ..repositories import UserRepository
            from ..models.user import UserStatus
            user_repo = UserRepository(db)
            current_user = user_repo.find_by_login("admin")
            if not current_user:
                # Create a system user for anonymous access
                from ..models.user import User as DomainUser
                current_user = DomainUser(
                    id=0,
                    login="system",
                    firstname="System",
                    lastname="User",
                    mail="system@example.com",
                    status=UserStatus.ACTIVE,
                    admin=True
                )

        service = MeetingListService(user=current_user, db=db)
        result = service.call(
            project_id=project_id,
            state=state,
            upcoming=upcoming,
            limit=limit,
            offset=offset,
        )

        if result.is_failure():
            raise HTTPException(status_code=400, detail=result.errors or result.message)

        meetings = result.result['meetings']
        return [MeetingsController.meeting_to_response(m) for m in meetings]

    @staticmethod
    def get_meeting(
        db: Session,
        meeting_id: int,
        current_user: Optional[User] = None
    ) -> MeetingResponse:
        """
        Get a specific meeting by ID.

        Args:
            db: Database session
            meeting_id: Meeting ID
            current_user: Current user (optional)

        Returns:
            Meeting response

        Raises:
            HTTPException: If meeting not found
        """
        meeting_repo = MeetingRepository(db)
        meeting = meeting_repo.find_by_id(meeting_id)

        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        return MeetingsController.meeting_to_response(meeting)

    @staticmethod
    def create_meeting(
        db: Session,
        meeting_data: MeetingCreate,
        current_user: User
    ) -> MeetingResponse:
        """
        Create a new meeting.

        Args:
            db: Database session
            meeting_data: Meeting creation data
            current_user: Current authenticated user

        Returns:
            Created meeting response

        Raises:
            HTTPException: If creation fails
        """
        service = MeetingCreateService(user=current_user, db=db)
        result = service.call(meeting_data.model_dump())

        if result.is_failure():
            raise HTTPException(status_code=400, detail=result.errors or result.message)

        return MeetingsController.meeting_to_response(result.result)

    @staticmethod
    def update_meeting(
        db: Session,
        meeting_id: int,
        meeting_data: MeetingUpdate,
        current_user: User
    ) -> MeetingResponse:
        """
        Update an existing meeting.

        Args:
            db: Database session
            meeting_id: Meeting ID to update
            meeting_data: Meeting update data
            current_user: Current authenticated user

        Returns:
            Updated meeting response

        Raises:
            HTTPException: If update fails or meeting not found
        """
        service = MeetingUpdateService(user=current_user, db=db)
        result = service.call(meeting_id, meeting_data.model_dump(exclude_unset=True))

        if result.is_failure():
            if result.message == "Meeting not found":
                raise HTTPException(status_code=404, detail=result.message)
            raise HTTPException(status_code=403, detail=result.message)

        return MeetingsController.meeting_to_response(result.result)

    @staticmethod
    def delete_meeting(
        db: Session,
        meeting_id: int,
        current_user: User
    ) -> None:
        """
        Delete a meeting.

        Args:
            db: Database session
            meeting_id: Meeting ID to delete
            current_user: Current authenticated user

        Raises:
            HTTPException: If deletion fails or meeting not found
        """
        service = MeetingDeleteService(user=current_user, db=db)
        result = service.call(meeting_id)

        if result.is_failure():
            if result.message == "Meeting not found":
                raise HTTPException(status_code=404, detail=result.message)
            raise HTTPException(status_code=403, detail=result.message)
