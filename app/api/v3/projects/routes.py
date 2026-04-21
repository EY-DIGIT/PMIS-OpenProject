"""
Project routes - URL definitions with permission bindings.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.orm import Session

from ....core.middleware.rbac import require_permission
from ....infrastructure.db.session import get_db

from .controller import ProjectController
from .permissions import (
    PROJECTS_CLOSE,
    PROJECTS_CREATE,
    PROJECTS_DELETE_ALL,
    PROJECTS_PUBLISH,
    PROJECTS_READ,
    PROJECTS_UPDATE,
)
from .schemas import (
    ProjectCloseRequest,
    ProjectCreateRequest,
    ProjectListQuery,
    ProjectUpdateRequest,
    ProjectUpsertRequest,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    dependencies=[require_permission(PROJECTS_CREATE)],
    summary="Create project",
    status_code=201,
)
def create_project(
    request: Request,
    data: ProjectCreateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.create(request, data, db)


@router.put(
    "/{identifier}",
    dependencies=[require_permission(PROJECTS_CREATE)],
    summary="Create or update project by identifier (idempotent)",
    description=(
        "Idempotent create-or-update of a project keyed by identifier. "
        "Used by multi-step creation wizards — re-submitting the same "
        "identifier updates the existing row rather than creating a duplicate. "
        "Returns 201 on first call, 200 on subsequent calls; on the update "
        "path, caller must own the project (or be admin)."
    ),
)
def upsert_project_by_identifier(
    request: Request,
    identifier: str,
    data: ProjectUpsertRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.upsert(request, identifier, data, db)


@router.get(
    "",
    dependencies=[require_permission(PROJECTS_READ)],
    summary="List projects",
)
def list_projects(
    request: Request,
    offset: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    active: bool = Query(None),
    public: bool = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = ProjectListQuery(offset=offset, pageSize=pageSize, active=active, public=public)
    return ProjectController.list(request, query, db)


@router.get(
    "/{project_id}",
    dependencies=[require_permission(PROJECTS_READ)],
    summary="Get project",
)
def get_project(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.get(request, project_id, db)


@router.patch(
    "/{project_id}",
    dependencies=[require_permission(PROJECTS_UPDATE)],
    summary="Update project",
)
def update_project(
    request: Request,
    project_id: int,
    data: ProjectUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.update(request, project_id, data, db)


@router.delete(
    "/{project_id}",
    dependencies=[require_permission(PROJECTS_DELETE_ALL)],
    summary="Soft-delete project",
)
def delete_project(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.delete(request, project_id, db)


@router.post(
    "/{project_id}/publish",
    dependencies=[require_permission(PROJECTS_PUBLISH)],
    summary="Publish project",
)
def publish_project(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.publish(request, project_id, db)


@router.post(
    "/{project_id}/close",
    dependencies=[require_permission(PROJECTS_CLOSE)],
    summary="Close project",
)
def close_project(
    request: Request,
    project_id: int,
    data: Optional[ProjectCloseRequest] = Body(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.close(request, project_id, data, db)


@router.post(
    "/{project_id}/suspend",
    dependencies=[require_permission(PROJECTS_UPDATE)],
    summary="Suspend version project",
)
def suspend_project(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.suspend(request, project_id, db)


@router.post(
    "/{identifier}/versions",
    dependencies=[require_permission(PROJECTS_CREATE)],
    summary="Create new version of a published project",
    status_code=201,
)
def create_project_version(
    request: Request,
    identifier: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.create_version(request, identifier, db)
