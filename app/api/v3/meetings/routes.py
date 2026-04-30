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
from ....core.errors import NotFoundError
from ....core.middleware.rbac import require_permission
from ....infrastructure.db.repositories.project_repository import ProjectRepository
from ....infrastructure.db.session import get_db

# Create two routers: one for project-scoped routes, one for standalone meeting routes
projects_router = APIRouter(prefix="/projects", tags=["meetings"])
meetings_router = APIRouter(prefix="/meetings", tags=["meetings"])


def _resolve_project_id(db: Session, project_uuid: str) -> str:
    if not ProjectRepository(db).exists_by_id(project_uuid):
        raise NotFoundError("The project could not be found.")
    return project_uuid


# Project-scoped meeting endpoints
@projects_router.post(
    "/{project_uuid}/meetings/create",
    dependencies=[require_permission(MEETINGS_CREATE)],
    summary="Create meeting",
    description="Create a new meeting in a project",
    status_code=201
)
def create_meeting(
    request: Request,
    project_uuid: str,
    data: MeetingCreateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new meeting in a project."""
    project_id = _resolve_project_id(db, project_uuid)
    return MeetingController.create_meeting(request, project_id, data, db)


@projects_router.get(
    "/{project_uuid}/meetings",
    dependencies=[require_permission(MEETINGS_VIEW)],
    summary="List meetings",
    description="List meetings in a project",
    status_code=200
)
def list_meetings(
    request: Request,
    project_uuid: str,
    offset: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List meetings in a project."""
    project_id = _resolve_project_id(db, project_uuid)
    query = MeetingListQuery(offset=offset, pageSize=pageSize)
    return MeetingController.list_meetings(request, project_id, query, db)


# Standalone meeting endpoints
@meetings_router.get(
    "/{meeting_id}",
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


@meetings_router.patch(
    "/{meeting_id}",
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


@meetings_router.delete(
    "/{meeting_id}",
    dependencies=[require_permission(MEETINGS_DELETE)],
    summary="Delete meeting",
    description="Delete a meeting",
    status_code=204,
    response_model=None
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
    return MeetingController.delete_meeting(request, meeting_id, db)


# Meeting participants endpoints
@meetings_router.post(
    "/{meeting_id}/participants/create",
    dependencies=[require_permission(MEETINGS_UPDATE)],
    summary="Add participant",
    description="Add a participant to a meeting",
    status_code=201
)
def add_participant(
    request: Request,
    meeting_id: int,
    data: ParticipantAddRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add a participant to a meeting.

    Requires: MEETINGS_UPDATE permission
    """
    return MeetingController.add_participant(request, meeting_id, data, db)


@meetings_router.get(
    "/{meeting_id}/participants",
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


@meetings_router.delete(
    "/{meeting_id}/participants/{user_id}",
    dependencies=[require_permission(MEETINGS_UPDATE)],
    summary="Remove participant",
    description="Remove a participant from a meeting",
    status_code=204,
    response_model=None
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
    return MeetingController.remove_participant(request, meeting_id, user_id, db)


# Meeting agenda endpoints
@meetings_router.post(
    "/{meeting_id}/agenda_items/create",
    dependencies=[require_permission(MEETINGS_UPDATE)],
    summary="Create agenda item",
    description="Create an agenda item for a meeting",
    status_code=201
)
def create_agenda_item(
    request: Request,
    meeting_id: int,
    data: AgendaItemCreateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create an agenda item for a meeting.

    Requires: MEETINGS_UPDATE permission
    """
    return MeetingController.create_agenda_item(request, meeting_id, data, db)


@meetings_router.get(
    "/{meeting_id}/agenda_items",
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


@meetings_router.get(
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


@meetings_router.patch(
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


@meetings_router.delete(
    "/agenda_items/{agenda_item_id}",
    dependencies=[require_permission(MEETINGS_DELETE)],
    summary="Delete agenda item",
    description="Delete an agenda item",
    status_code=204,
    response_model=None
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
    return MeetingController.delete_agenda_item(request, agenda_item_id, db)


