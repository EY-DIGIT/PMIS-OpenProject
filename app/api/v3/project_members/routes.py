"""
Project Members routes - URL definitions with permission bindings.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from .controller import ProjectMembersController
from .schemas import (
    ProjectMemberAddRequest,
    ProjectMemberUpdateRequest,
    ProjectMembersListQuery
)
from .permissions import (
    PROJECT_MEMBERS_READ,
    PROJECT_MEMBERS_ADD,
    PROJECT_MEMBERS_UPDATE,
    PROJECT_MEMBERS_DELETE,
)
from ....core.errors import NotFoundError
from ....core.middleware.rbac import (
    require_authenticated,
    require_permission,
    require_project_permission,
)
from ....infrastructure.db.repositories.project_repository import ProjectRepository
from ....infrastructure.db.session import get_db

# Create two routers: one for project-scoped routes, one for standalone membership routes
projects_router = APIRouter(prefix="/projects", tags=["project_members"])
memberships_router = APIRouter(prefix="/memberships", tags=["project_members"])


def _resolve_project_id(db: Session, project_uuid: str) -> str:
    if not ProjectRepository(db).exists_by_id(project_uuid):
        raise NotFoundError("The project could not be found.")
    return project_uuid


@projects_router.post(
    "/{project_uuid}/memberships/create",
    dependencies=[require_project_permission(PROJECT_MEMBERS_ADD)],
    summary="Add project member",
    description="Add a user to a project",
    status_code=201
)
def add_project_member(
    request: Request,
    project_uuid: str,
    data: ProjectMemberAddRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Add a user to a project."""
    project_id = _resolve_project_id(db, project_uuid)
    return ProjectMembersController.add_member(request, project_id, data, db)


@projects_router.get(
    "/{project_uuid}/memberships",
    dependencies=[require_permission(PROJECT_MEMBERS_READ)],
    summary="List project members",
    description="List members of a project with pagination"
)
def list_project_members(
    request: Request,
    project_uuid: str,
    offset: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List members of a project."""
    project_id = _resolve_project_id(db, project_uuid)
    query = ProjectMembersListQuery(offset=offset, pageSize=pageSize)
    return ProjectMembersController.list_members(request, project_id, query, db)


@memberships_router.patch(
    "/{membership_id}",
    dependencies=[require_project_permission(PROJECT_MEMBERS_UPDATE)],
    summary="Update project member",
    description="Update member roles"
)
def update_project_member(
    request: Request,
    membership_id: int,
    data: ProjectMemberUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update a membership's roles.

    Requires: PROJECT_MEMBERS_UPDATE permission
    """
    return ProjectMembersController.update_member(request, membership_id, data, db)


@memberships_router.delete(
    "/{membership_id}",
    dependencies=[require_project_permission(PROJECT_MEMBERS_DELETE)],
    summary="Remove project member",
    description="Remove a user from a project",
    status_code=204,
    response_model=None
)
def delete_project_member(
    request: Request,
    membership_id: int,
    db: Session = Depends(get_db)
) -> None:
    """
    Remove a member from a project.

    Requires: PROJECT_MEMBERS_DELETE permission
    """
    return ProjectMembersController.remove_member(request, membership_id, db)
