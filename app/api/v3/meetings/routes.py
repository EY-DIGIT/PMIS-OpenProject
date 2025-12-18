"""
Meetings routes - URL definitions with permission bindings.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from .controller import MeetingController
from .schemas import (
    MeetingCreateRequest,
    MeetingUpdateRequest,
    MeetingListQuery,
    ParticipantAddRequest,
    AgendaItemCreateRequest,
    AgendaItemUpdateRequest,
)
from .permissions import (
    MEETINGS_VIEW,
    MEETINGS_CREATE,
    MEETINGS_UPDATE,
    MEETINGS_DELETE,
)
from app.core.middleware.rbac import require_permission
from app.infrastructure.db.session import get_db

router = APIRouter(prefix="/meetings", tags=["meetings"])

# Meeting Endpoints

@router.post(
    "/projects/{project_id}/meetings",
    dependencies=[require_permission(MEETINGS_CREATE)],
    summary="Create meeting",
    description="Create a new meeting in a project",
    status_code=201
)
def create_meeting(
    request: Request,
    project_id: int,
    data: MeetingCreateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new meeting in a project.

    Requires: MEETINGS_CREATE permission
    """
    return MeetingController.create_meeting(request, project_id, data, db)


@router.get(
    "/projects/{project_id}/meetings",
    dependencies=[require_permission(MEETINGS_VIEW)],
    summary="List meetings",
    description="List meetings in a project",
    status_code=200
)
def list_meetings(
    request: Request,
    project_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List meetings in a project.

    Requires: MEETINGS_VIEW permission
    """
    query = MeetingListQuery(offset=offset, limit=limit)
    return MeetingController.list_meetings(request, project_id, query, db)


@router.get(
    "/meetings/{meeting_id}",
    dependencies=[require_permission(MEETINGS_VIEW)],
    summary="Get meeting",
    description="Get a meeting by ID",
    status_code=200
)
def get_meeting(
    request: Request,
    meeting_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get a meeting by ID.

    Requires: MEETINGS_VIEW permission
    """
    return MeetingController.get_meeting(request, meeting_id, db)


@router.patch(
    "/meetings/{meeting_id}",
    dependencies=[require_permission(MEETINGS_UPDATE)],
    summary="Update meeting",
    description="Update a meeting",
    status_code=200
)
def update_meeting(
    request: Request,
    meeting_id: int,
    data: MeetingUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update a meeting.

    Requires: MEETINGS_UPDATE permission
    """
    return MeetingController.update_meeting(request, meeting_id, data, db)


@router.delete(
    "/meetings/{meeting_id}",
    dependencies=[require_permission(MEETINGS_DELETE)],
    summary="Delete meeting",
    description="Delete a meeting",
    status_code=204
)
def delete_meeting(
    request: Request,
    meeting_id: int,
    db: Session = Depends(get_db)
) -> None:
    """
    Delete a meeting.

    Requires: MEETINGS_DELETE permission
    """
    MeetingController.delete_meeting(request, meeting_id, db)


# Participant Endpoints

@router.post(
    "/meetings/{meeting_id}/participants",
    dependencies=[require_permission(MEETINGS_UPDATE)],
    summary="Add participant",
    description="Add a user as a participant to a meeting",
    status_code=201
)
def add_participant(
    request: Request,
    meeting_id: int,
    data: ParticipantAddRequest,
    project_id: int = Query(..., description="Project ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add a participant to a meeting.

    Requires: MEETINGS_UPDATE permission
    """
    return MeetingController.add_participant(request, meeting_id, project_id, data, db)


@router.get(
    "/meetings/{meeting_id}/participants",
    dependencies=[require_permission(MEETINGS_VIEW)],
    summary="List participants",
    description="List participants in a meeting",
    status_code=200
)
def list_participants(
    request: Request,
    meeting_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List participants in a meeting.

    Requires: MEETINGS_VIEW permission
    """
    return MeetingController.list_participants(request, meeting_id, db)


@router.delete(
    "/meetings/{meeting_id}/participants/{user_id}",
    dependencies=[require_permission(MEETINGS_UPDATE)],
    summary="Remove participant",
    description="Remove a participant from a meeting",
    status_code=204
)
def remove_participant(
    request: Request,
    meeting_id: int,
    user_id: int,
    db: Session = Depends(get_db)
) -> None:
    """
    Remove a participant from a meeting.

    Requires: MEETINGS_UPDATE permission
    """
    MeetingController.remove_participant(request, meeting_id, user_id, db)


# Agenda Item Endpoints

@router.post(
    "/meetings/{meeting_id}/agenda_items",
    dependencies=[require_permission(MEETINGS_UPDATE)],
    summary="Create agenda item",
    description="Create an agenda item for a meeting",
    status_code=201
)
def create_agenda_item(
    request: Request,
    meeting_id: int,
    data: AgendaItemCreateRequest,
    project_id: int = Query(..., description="Project ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create an agenda item for a meeting.

    Requires: MEETINGS_UPDATE permission
    """
    return MeetingController.create_agenda_item(request, meeting_id, project_id, data, db)


@router.get(
    "/meetings/{meeting_id}/agenda_items",
    dependencies=[require_permission(MEETINGS_VIEW)],
    summary="List agenda items",
    description="List agenda items for a meeting",
    status_code=200
)
def list_agenda_items(
    request: Request,
    meeting_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List agenda items for a meeting.

    Requires: MEETINGS_VIEW permission
    """
    return MeetingController.list_agenda_items(request, meeting_id, db)


@router.get(
    "/agenda_items/{agenda_item_id}",
    dependencies=[require_permission(MEETINGS_VIEW)],
    summary="Get agenda item",
    description="Get an agenda item by ID",
    status_code=200
)
def get_agenda_item(
    request: Request,
    agenda_item_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get an agenda item by ID.

    Requires: MEETINGS_VIEW permission
    """
    return MeetingController.get_agenda_item(request, agenda_item_id, db)


@router.patch(
    "/agenda_items/{agenda_item_id}",
    dependencies=[require_permission(MEETINGS_UPDATE)],
    summary="Update agenda item",
    description="Update an agenda item",
    status_code=200
)
def update_agenda_item(
    request: Request,
    agenda_item_id: int,
    data: AgendaItemUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update an agenda item.

    Requires: MEETINGS_UPDATE permission
    """
    return MeetingController.update_agenda_item(request, agenda_item_id, data, db)


@router.delete(
    "/agenda_items/{agenda_item_id}",
    dependencies=[require_permission(MEETINGS_DELETE)],
    summary="Delete agenda item",
    description="Delete an agenda item",
    status_code=204
)
def delete_agenda_item(
    request: Request,
    agenda_item_id: int,
    db: Session = Depends(get_db)
) -> None:
    """
    Delete an agenda item.

    Requires: MEETINGS_DELETE permission
    """
    MeetingController.delete_agenda_item(request, agenda_item_id, db)

