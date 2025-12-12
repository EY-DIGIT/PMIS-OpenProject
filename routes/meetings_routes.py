"""
Meeting routes - URL routing with authorization at route level.

This module defines FastAPI routes with authorization checks applied
via middleware/dependencies before calling controllers.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

try:
    from ..database import get_db
    from ..models.user import User
    from ..api.dependencies import get_current_user, get_current_user_optional
    from ..middleware.rbac import Permission, require_manage_meetings
    from ..controllers.meetings_controller import MeetingsController
    from ..schemas.meeting import MeetingCreate, MeetingUpdate, MeetingResponse
except ImportError:
    from database import get_db
    from models.user import User
    from api.dependencies import get_current_user, get_current_user_optional
    from middleware.rbac import Permission, require_manage_meetings
    from controllers.meetings_controller import MeetingsController
    from schemas.meeting import MeetingCreate, MeetingUpdate, MeetingResponse


router = APIRouter(prefix="/api/v3/meetings", tags=["meetings"])


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

    No authorization required - public endpoint.
    """
    return MeetingsController.list_meetings(
        db=db,
        current_user=current_user,
        project_id=project_id,
        state=state,
        upcoming=upcoming,
        limit=limit,
        offset=offset,
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Get a specific meeting by ID.

    No authorization required - public endpoint.
    """
    return MeetingsController.get_meeting(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    meeting_data: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new meeting.

    Requires authentication.
    Authorization checked at route level - user must be authenticated.
    """
    return MeetingsController.create_meeting(
        db=db,
        meeting_data=meeting_data,
        current_user=current_user,
    )


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: int,
    meeting_data: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing meeting.

    Requires authentication.
    Authorization (author/admin check) handled by service layer.
    """
    return MeetingsController.update_meeting(
        db=db,
        meeting_id=meeting_id,
        meeting_data=meeting_data,
        current_user=current_user,
    )


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a meeting.

    Requires authentication.
    Authorization (author/admin check) handled by service layer.
    """
    MeetingsController.delete_meeting(
        db=db,
        meeting_id=meeting_id,
        current_user=current_user,
    )
    return None
