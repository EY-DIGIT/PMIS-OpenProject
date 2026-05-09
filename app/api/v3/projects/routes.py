"""
Project routes - URL definitions with permission bindings.

All URL path parameters use ``project_uuid`` (the public handle). The
controller resolves UUID -> internal id.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.orm import Session

from ....core.middleware.rbac import (
    require_permission,
    require_project_permission,
)
from ....infrastructure.db.session import get_db

from ....core.base_controller import BaseController
from ....core.errors import NotFoundError
from ....core.permissions import PROJECT_MEMBERS_READ
from ....infrastructure.db.models.project import ProjectModel
from ....infrastructure.db.models.role import RoleModel
from ....infrastructure.db.models.user import UserModel
from ....infrastructure.db.models.user_role_assignment import (
    UserRoleAssignmentModel,
)

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
    "/create",
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
    "/{project_uuid}",
    dependencies=[require_permission(PROJECTS_CREATE)],
    summary="Create or update project by uuid (idempotent)",
    description=(
        "Idempotent create-or-update of a project keyed by uuid. Used by "
        "multi-step creation wizards — re-submitting the same uuid updates "
        "the existing row rather than creating a duplicate. Returns 201 on "
        "first call, 200 on subsequent calls; on the update path, caller "
        "must own the project (or be admin). The frontend generates the uuid "
        "via crypto.randomUUID() once per wizard session. The server "
        "auto-generates projectCode on insert and preserves it on update."
    ),
)
def upsert_project_by_uuid(
    request: Request,
    project_uuid: str,
    data: ProjectUpsertRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.upsert(request, project_uuid, data, db)


@router.get(
    "",
    dependencies=[require_permission(PROJECTS_READ)],
    summary="List live projects (excludes soft-deleted)",
    description=(
        "Default Search Project listing. Soft-deleted projects are filtered "
        "out; results are newest-first (createdAt descending). For the "
        "admin view that includes deleted rows, see GET /projects/all."
    ),
)
def list_projects(
    request: Request,
    offset: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    active: bool = Query(None),
    public: bool = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = ProjectListQuery(
        offset=offset, pageSize=pageSize, active=active, public=public,
        includeDeleted=False,
    )
    return ProjectController.list(request, query, db)


@router.get(
    "/all",
    dependencies=[require_permission(PROJECTS_READ)],
    summary="List all projects including soft-deleted",
    description=(
        "Admin / audit view. Returns every project row, including those that "
        "have been soft-deleted. Each row carries a `deletedAt` field — NULL "
        "for live projects, populated for deleted ones. Sort order is the "
        "same newest-first ordering used by GET /projects."
    ),
)
def list_all_projects(
    request: Request,
    offset: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    active: bool = Query(None),
    public: bool = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = ProjectListQuery(
        offset=offset, pageSize=pageSize, active=active, public=public,
        includeDeleted=True,
    )
    return ProjectController.list(request, query, db)


@router.get(
    "/{project_uuid}",
    dependencies=[require_permission(PROJECTS_READ)],
    summary="Get project",
)
def get_project(
    request: Request,
    project_uuid: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.get(request, project_uuid, db)


@router.patch(
    "/{project_uuid}",
    dependencies=[require_project_permission(PROJECTS_UPDATE)],
    summary="Update project",
)
def update_project(
    request: Request,
    project_uuid: str,
    data: ProjectUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.update(request, project_uuid, data, db)


@router.delete(
    "/{project_uuid}",
    dependencies=[require_project_permission(PROJECTS_DELETE_ALL)],
    summary="Soft-delete project",
)
def delete_project(
    request: Request,
    project_uuid: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.delete(request, project_uuid, db)


@router.post(
    "/{project_uuid}/save",
    dependencies=[require_project_permission(PROJECTS_UPDATE)],
    summary="Save project setup (new -> draft if milestones exist)",
    description=(
        "Maps to the 'Save Project' button in the Step-1 wizard. Flips status "
        "from 'new' to 'draft' when at least one live milestone exists on the "
        "project. Adding a milestone alone does NOT change status — only this "
        "explicit save call does. Idempotent: a no-op once past 'new'."
    ),
)
def save_project(
    request: Request,
    project_uuid: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.save(request, project_uuid, db)


@router.post(
    "/{project_uuid}/publish",
    dependencies=[require_project_permission(PROJECTS_PUBLISH)],
    summary="Publish project",
)
def publish_project(
    request: Request,
    project_uuid: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.publish(request, project_uuid, db)


@router.post(
    "/{project_uuid}/close",
    dependencies=[require_project_permission(PROJECTS_CLOSE)],
    summary="Close project",
)
def close_project(
    request: Request,
    project_uuid: str,
    data: Optional[ProjectCloseRequest] = Body(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ProjectController.close(request, project_uuid, data, db)


@router.get(
    "/{project_uuid}/role-assignments",
    dependencies=[require_permission(PROJECT_MEMBERS_READ)],
    summary="Per-project role assignments grouped by role",
    description=(
        "Doc 44 round 8: monolith mirror of the user-mgmt route at the "
        "same path. Returns the users assigned to this project, grouped "
        "by the doc-41 scoped role they hold (project_admin / "
        "project_member / division_member). Powers the project-opened "
        "User Management view so the FE can avoid a cross-service call "
        "to user-mgmt for this read."
    ),
)
def list_project_role_assignments(
    project_uuid: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = (
        db.query(UserRoleAssignmentModel, RoleModel, UserModel)
        .join(RoleModel, RoleModel.id == UserRoleAssignmentModel.role_id)
        .join(UserModel, UserModel.id == UserRoleAssignmentModel.user_id)
        .filter(UserRoleAssignmentModel.project_id == project_uuid)
        .filter(UserModel.deleted_at.is_(None))
        .order_by(RoleModel.name.asc(), UserModel.login.asc())
        .all()
    )

    buckets: Dict[int, Dict[str, Any]] = {}
    for ura, role, user in rows:
        bucket = buckets.setdefault(role.id, {
            "roleId": role.id,
            "roleName": role.name,
            "users": [],
        })
        bucket["users"].append({
            "id": user.id,
            "login": user.login,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "assignmentId": ura.id,
        })

    project = (
        db.query(ProjectModel)
        .filter(ProjectModel.id == project_uuid)
        .first()
    )
    if project is None:
        raise NotFoundError(f"Project {project_uuid} not found.")

    return BaseController.ok(data={
        "projectId": project_uuid,
        "projectName": project.name,
        "roles": list(buckets.values()),
    })
