"""
Meeting API endpoints following OpenProject API v3 conventions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from api.dependencies import get_current_user, get_current_user_optional
from schemas.meeting import (
    MeetingCreate,
    MeetingUpdate,
    MeetingResponse,
    HALLink,
    HALLinks,
    MeetingStateEnum,
)
from services.meeting_service import (
    MeetingCreateService,
    MeetingUpdateService,
    MeetingDeleteService,
    MeetingListService,
)
from repositories import MeetingRepository, UserRepository
from models.user import User


router = APIRouter(prefix="/api/v3/meetings", tags=["meetings"])


def meeting_to_response(meeting, base_url: str = "http://localhost:8000") -> MeetingResponse:
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


@router.get("", response_model=List[MeetingResponse])
async def list_meetings(
    project_id: Optional[int] = Query(None, description="Filter by project"),
    state: Optional[str] = Query(None, description="Filter by state"),
    upcoming: bool = Query(False, description="Show only upcoming meetings"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    List meetings with optional filters.

    Supports filtering by:
    - project_id: Show meetings for a specific project
    - state: Filter by meeting state (open, closed, cancelled, etc.)
    - upcoming: Show only future meetings

    Returns a list of meetings in HAL+JSON format.

    Note: Authentication is optional for listing meetings.
    """
    # Get or create a default user for unauthenticated requests
    if not current_user:
        user_repo = UserRepository(db)
        current_user = user_repo.find_by_login("admin")
        if not current_user:
            # Create a system user for anonymous access
            from models.user import User as DomainUser, UserStatus
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
    return [meeting_to_response(m) for m in meetings]


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get a specific meeting by ID.

    Returns the meeting details in HAL+JSON format.

    Note: Authentication is optional for viewing meetings.
    """
    meeting_repo = MeetingRepository(db)
    meeting = meeting_repo.find_by_id(meeting_id)

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return meeting_to_response(meeting)


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    meeting_data: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new meeting.

    Required fields:
    - title: Meeting title
    - project_id: ID of the associated project

    Optional fields:
    - location: Meeting location
    - start_time: When the meeting starts
    - duration: Duration in hours (default: 1.0)
    - state: Meeting state (default: open)
    - notify: Send notifications (default: true)
    - participants: List of participant objects

    Returns the created meeting in HAL+JSON format.
    """
    service = MeetingCreateService(user=current_user, db=db)
    result = service.call(meeting_data.model_dump())

    if result.is_failure():
        raise HTTPException(status_code=400, detail=result.errors or result.message)

    return meeting_to_response(result.result)


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: int,
    meeting_data: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing meeting.

    All fields are optional. Only provided fields will be updated.

    Updatable fields:
    - title: Meeting title
    - location: Meeting location
    - start_time: When the meeting starts
    - duration: Duration in hours
    - state: Meeting state
    - notify: Send notifications flag

    Returns the updated meeting in HAL+JSON format.
    """
    service = MeetingUpdateService(user=current_user, db=db)
    result = service.call(meeting_id, meeting_data.model_dump(exclude_unset=True))

    if result.is_failure():
        if result.message == "Meeting not found":
            raise HTTPException(status_code=404, detail=result.message)
        raise HTTPException(status_code=403, detail=result.message)

    return meeting_to_response(result.result)


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a meeting.

    Requires:
    - User must be the meeting author or an administrator

    Returns 204 No Content on success.
    """
    service = MeetingDeleteService(user=current_user, db=db)
    result = service.call(meeting_id)

    if result.is_failure():
        if result.message == "Meeting not found":
            raise HTTPException(status_code=404, detail=result.message)
        raise HTTPException(status_code=403, detail=result.message)

    return None
