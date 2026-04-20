"""
Project routes - URL definitions with permission bindings.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from .controller import ProjectController
from .schemas import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectUpsertRequest,
    ProjectListQuery
)
from .permissions import (
    PROJECTS_CREATE,
    PROJECTS_READ,
    PROJECTS_READ_ALL,
    PROJECTS_UPDATE,
    PROJECTS_UPDATE_ALL,
    PROJECTS_DELETE_ALL
)
from ....core.middleware.rbac import require_permission, require_authenticated
from ....infrastructure.db.session import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    dependencies=[require_permission(PROJECTS_CREATE)],
    summary="Create project",
    description="Create a new project",
    status_code=201
)
def create_project(
    request: Request,
    data: ProjectCreateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new project.

    Requires: PROJECTS_CREATE permission (member+)
    """
    return ProjectController.create(request, data, db)


@router.put(
    "/{identifier}",
    dependencies=[require_permission(PROJECTS_CREATE)],
    summary="Create or update project by identifier (idempotent)",
    description=(
        "Idempotent create-or-update of a project keyed by its identifier. "
        "Intended for multi-step creation wizards: re-submitting the same "
        "identifier updates the existing project instead of creating a "
        "duplicate. Returns 201 on first call, 200 on subsequent calls. "
        "Requires ownership of the existing project (or admin) on the "
        "update path."
    ),
)
def upsert_project_by_identifier(
    request: Request,
    identifier: str,
    data: ProjectUpsertRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Upsert a project by identifier.

    Requires: PROJECTS_CREATE permission (member+).
    On update path, caller must be the project's owner or an admin.
    """
    return ProjectController.upsert(request, identifier, data, db)


@router.get(
    "",
    dependencies=[require_permission(PROJECTS_READ)],
    summary="List projects",
    description="List all projects with pagination"
)
def list_projects(
    request: Request,
    offset: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    active: bool = Query(None, description="Filter by active status"),
    public: bool = Query(None, description="Filter by public status"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List projects with pagination.

    Requires: PROJECTS_READ permission (viewer+)
    """
    query = ProjectListQuery(offset=offset, pageSize=pageSize, active=active, public=public)
    return ProjectController.list(request, query, db)


@router.get(
    "/{project_id}",
    dependencies=[require_permission(PROJECTS_READ)],
    summary="Get project",
    description="Get project by ID"
)
def get_project(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get project by ID.

    Requires: PROJECTS_READ permission (viewer+)
    """
    return ProjectController.get(request, project_id, db)


@router.patch(
    "/{project_id}",
    dependencies=[require_permission(PROJECTS_UPDATE)],
    summary="Update project",
    description="Update project details"
)
def update_project(
    request: Request,
    project_id: int,
    data: ProjectUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update project details.

    Requires: PROJECTS_UPDATE permission (member+)
    """
    return ProjectController.update(request, project_id, data, db)


@router.delete(
    "/{project_id}",
    dependencies=[require_permission(PROJECTS_DELETE_ALL)],
    summary="Delete project",
    description="Delete project by ID"
)
def delete_project(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete project by ID.

    Requires: PROJECTS_DELETE_ALL permission (admin only)
    """
    return ProjectController.delete(request, project_id, db)
