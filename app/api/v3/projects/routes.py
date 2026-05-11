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


@router.get(
    "/{project_uuid}/assignable-users",
    dependencies=[require_permission(PROJECT_MEMBERS_READ)],
    summary="Users that can be assigned a Task / Sub-Task on this project",
    description=(
        "Round 11b: returns the union of (a) every user with a "
        "project-tier role assignment on this project (project_admin, "
        "project_member, division_member) AND (b) every user with an "
        "org_admin role assignment on the project's owning vendor(s). "
        "OAs are included so a project_admin can assign tasks up to an "
        "org admin per spec. The set is de-duplicated by user id. "
        "Each entry carries id / login / firstName / lastName / email / "
        "orgRole so the FE picker can render names without a per-id "
        "/users round-trip."
    ),
)
def list_project_assignable_users(
    project_uuid: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    from ....infrastructure.db.models.project_vendor import ProjectVendorModel

    # Round-9b: round-trippable orgRole from the column when no role
    # assignment matches. derive_org_role lives in user-mgmt — inline
    # the simple per-user lookup here so the monolith doesn't depend
    # on that helper.
    _ORG_ROLE_PRIORITY = (
        "super_admin", "admin", "org_admin",
        "project_admin", "project_member",
    )
    def _derive(user_obj):
        # Highest-tier role from any assignment row + fall back to
        # users.org_role column (round 9b).
        held = {n for (n,) in (
            db.query(RoleModel.name)
            .join(
                UserRoleAssignmentModel,
                UserRoleAssignmentModel.role_id == RoleModel.id,
            )
            .filter(UserRoleAssignmentModel.user_id == user_obj.id)
            .distinct().all()
        )}
        for tier in _ORG_ROLE_PRIORITY:
            if tier in held:
                return tier
        col = getattr(user_obj, "org_role", None)
        return col if col in _ORG_ROLE_PRIORITY else None

    project = (
        db.query(ProjectModel)
        .filter(ProjectModel.id == project_uuid)
        .first()
    )
    if project is None:
        raise NotFoundError(f"Project {project_uuid} not found.")

    # (a) Users with a project-scoped role on this project.
    project_scoped_rows = (
        db.query(UserModel)
        .join(
            UserRoleAssignmentModel,
            UserRoleAssignmentModel.user_id == UserModel.id,
        )
        .join(
            RoleModel, RoleModel.id == UserRoleAssignmentModel.role_id,
        )
        .filter(UserRoleAssignmentModel.project_id == project_uuid)
        .filter(UserModel.deleted_at.is_(None))
        .all()
    )

    # (b) Vendors that own this project → org_admin holders for those
    #     vendor(s). Project may be linked to >1 vendor via project_vendors.
    vendor_ids = [
        row[0] for row in
        db.query(ProjectVendorModel.vendor_id)
        .filter(ProjectVendorModel.project_id == project_uuid)
        .all()
    ]
    org_admin_rows: list = []
    if vendor_ids:
        org_admin_rows = (
            db.query(UserModel)
            .join(
                UserRoleAssignmentModel,
                UserRoleAssignmentModel.user_id == UserModel.id,
            )
            .join(
                RoleModel, RoleModel.id == UserRoleAssignmentModel.role_id,
            )
            .filter(UserRoleAssignmentModel.organization_id.in_(vendor_ids))
            .filter(RoleModel.name == "org_admin")
            .filter(UserModel.deleted_at.is_(None))
            .all()
        )

    # Round 11b hotfix — exclude users who hold admin / super_admin
    # in any form (legacy user_roles row OR scoped user_role_assignments
    # global row). Spec (round 10): admin / super_admin must not appear
    # in project pickers, even if they happen to also hold a project-
    # tier assignment on this project. Tester observed an `admin`-tier
    # entry in the response on the live server.
    from ....infrastructure.db.models.user_role import UserRoleModel
    admin_tier_user_ids = {
        uid for (uid,) in (
            db.query(UserRoleAssignmentModel.user_id)
            .join(RoleModel, RoleModel.id == UserRoleAssignmentModel.role_id)
            .filter(RoleModel.name.in_(("admin", "super_admin")))
            .filter(UserRoleAssignmentModel.organization_id.is_(None))
            .filter(UserRoleAssignmentModel.project_id.is_(None))
            .distinct().all()
        )
    } | {
        uid for (uid,) in (
            db.query(UserRoleModel.user_id)
            .join(RoleModel, RoleModel.id == UserRoleModel.role_id)
            .filter(RoleModel.name.in_(("admin", "super_admin")))
            .distinct().all()
        )
    }

    # De-dup by user id; render with the round-9b orgRole projection.
    seen: Dict[str, Dict[str, Any]] = {}
    for u in list(project_scoped_rows) + list(org_admin_rows):
        if u.id in seen:
            continue
        if u.id in admin_tier_user_ids:
            continue
        seen[u.id] = {
            "id": u.id,
            "login": u.login,
            "email": u.email,
            "firstName": u.first_name,
            "lastName": u.last_name,
            "orgRole": _derive(u),
        }

    return BaseController.ok(data={
        "projectId": project_uuid,
        "projectName": project.name,
        "users": sorted(seen.values(), key=lambda x: (x["login"] or "")),
    })


@router.get(
    "/{project_uuid}/audit-logs",
    dependencies=[require_project_permission(PROJECTS_READ)],
    summary="Project audit logs (doc 47)",
    description=(
        "Returns the recorded audit events for ``project_uuid`` — every "
        "state change, M/A/T/S subtree edit, vendor/member association, "
        "and dependency tweak that ``record_audit`` captured. Newest "
        "row first. Each entry carries the snapshotted ``actorLogin`` / "
        "``actorRole`` / ``projectName`` / ``projectStatus`` / ``owner`` "
        "at write time so the log row stays meaningful even if the "
        "source user / project rows later mutate. Authorization: any "
        "caller with PROJECTS_READ on this project."
    ),
)
def list_project_audit_logs(
    project_uuid: str,
    offset: int = Query(1, ge=1, description="Page number (1-indexed)."),
    pageSize: int = Query(50, ge=1, le=200, description="Items per page (max 200)."),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    from ....infrastructure.db.repositories.project_audit_log_repository import (
        ProjectAuditLogRepository,
    )

    project = (
        db.query(ProjectModel)
        .filter(ProjectModel.id == project_uuid)
        .first()
    )
    if project is None:
        raise NotFoundError(f"Project {project_uuid} not found.")

    db_offset = (offset - 1) * pageSize
    rows, total = ProjectAuditLogRepository(db).list_for_project(
        project_id=project_uuid,
        offset=db_offset,
        limit=pageSize,
    )

    def _to_response(entry) -> Dict[str, Any]:
        d = entry.to_dict()
        # Per-entry payload — only the audit-event-specific fields.
        # Project identity (id / code / name / status / owner) is the
        # same for every row in this collection so it lives at the
        # top-level ``project`` key instead of being repeated.
        return {
            "id": d["id"],
            "actorId": d["actor_id"],
            "actorLogin": d["actor_login"],
            "actorRole": d["actor_role"],
            "action": d["action"],
            "before": d["before"],
            "after": d["after"],
            "createdAt": d["created_at"],
        }

    return BaseController.ok(data={
        "_type": "Collection",
        "_links": {
            "self": {
                "href": f"/api/v3/projects/{project_uuid}/audit-logs"
                        f"?offset={offset}&pageSize={pageSize}"
            },
        },
        "project": {
            "projectId": project.id,
            "projectCode": project.project_code,
            "projectName": project.name,
            "projectStatus": project.status,
            "owner": project.owner,
        },
        "total": total,
        "count": len(rows),
        "offset": offset,
        "pageSize": pageSize,
        "_embedded": {"elements": [_to_response(r) for r in rows]},
    })
