"""
Work Package routes - URL definitions with permission bindings.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from .controller import WorkPackageController
from .schemas import (
    WorkPackageCreateRequest,
    WorkPackageUpdateRequest,
    WorkPackageListQuery
)
from .permissions import (
    WORK_PACKAGES_VIEW,
    WORK_PACKAGES_CREATE,
    WORK_PACKAGES_UPDATE,
    WORK_PACKAGES_DELETE,
)
from ....core.errors import NotFoundError
from ....core.middleware.rbac import require_permission
from ....infrastructure.db.repositories.project_repository import ProjectRepository
from ....infrastructure.db.session import get_db

# Router for project-scoped work packages
projects_router = APIRouter(prefix="/projects/{project_uuid}/work_packages", tags=["work_packages"])

# Router for global work package endpoints
work_packages_router = APIRouter(prefix="/work_packages", tags=["work_packages"])


def _resolve_project_id(db: Session, project_uuid: str) -> str:
    if not ProjectRepository(db).exists_by_id(project_uuid):
        raise NotFoundError("The project could not be found.")
    return project_uuid


# Project-scoped endpoints
@projects_router.post(
    "/create",
    dependencies=[require_permission(WORK_PACKAGES_CREATE)],
    summary="Create work package",
    description="Create a new work package in a project",
    status_code=201
)
def create_work_package_in_project(
    request: Request,
    project_uuid: str,
    data: WorkPackageCreateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new work package in a project."""
    project_id = _resolve_project_id(db, project_uuid)
    return WorkPackageController.create_in_project(request, project_id, data, db)


@projects_router.get(
    "",
    dependencies=[require_permission(WORK_PACKAGES_VIEW)],
    summary="List work packages",
    description="List work packages in a project with pagination"
)
def list_work_packages_in_project(
    request: Request,
    project_uuid: str,
    offset: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    parentId: int = Query(None, description="Filter by parent work package ID"),
    type: str = Query(None, description="Filter by type internal_name (milestone, activity, task)"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List work packages in a project with pagination."""
    project_id = _resolve_project_id(db, project_uuid)
    query = WorkPackageListQuery(offset=offset, pageSize=pageSize, parentId=parentId, type=type)
    return WorkPackageController.list(request, project_id, query, db)


# Global work package endpoints
@work_packages_router.get(
    "/{work_package_id}",
    dependencies=[require_permission(WORK_PACKAGES_VIEW)],
    summary="Get work package",
    description="Get work package by ID"
)
def get_work_package(
    request: Request,
    work_package_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get a work package by ID.

    Requires: WORK_PACKAGES_VIEW permission
    """
    return WorkPackageController.get(request, work_package_id, db)


@work_packages_router.patch(
    "/{work_package_id}",
    dependencies=[require_permission(WORK_PACKAGES_UPDATE)],
    summary="Update work package",
    description="Update a work package"
)
def update_work_package(
    request: Request,
    work_package_id: int,
    data: WorkPackageUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update a work package.

    Requires: WORK_PACKAGES_UPDATE permission
    """
    return WorkPackageController.update(request, work_package_id, data, db)


@work_packages_router.get(
    "/{work_package_id}/children",
    dependencies=[require_permission(WORK_PACKAGES_VIEW)],
    summary="Get work package tree",
    description="Get a work package with its full nested subtree"
)
def get_work_package_children(
    request: Request,
    work_package_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get work package with nested children tree.

    Requires: WORK_PACKAGES_VIEW permission
    """
    return WorkPackageController.get_children(request, work_package_id, db)


@work_packages_router.delete(
    "/{work_package_id}",
    dependencies=[require_permission(WORK_PACKAGES_DELETE)],
    summary="Delete work package",
    description="Delete a work package"
)
def delete_work_package(
    request: Request,
    work_package_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete a work package.

    Requires: WORK_PACKAGES_DELETE permission
    """
    return WorkPackageController.delete(request, work_package_id, db)
