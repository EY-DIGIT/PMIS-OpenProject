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

from fastapi import File, UploadFile
from typing import List

from .._inline_attachments import dispatch_create, pre_validate_files
from ..comments.services import create_comment, list_comments
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
from ....core.permissions import COMMENTS_CREATE
from ....core.errors import ValidationError as CoreValidationError
from ....core.response import format_error_response

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "/create",
    dependencies=[require_permission(PROJECTS_CREATE)],
    summary="Create project (JSON or multipart with optional file attachments)",
    description=(
        "Dual-mode dispatch: ``application/json`` keeps the legacy "
        "behaviour; ``multipart/form-data`` accepts the same project "
        "fields PLUS optional ``files[]`` for documents (project "
        "charter, RFP, scope notes etc.). Attached files land in the "
        "shared comments table with ``body=NULL`` and "
        "``target_kind=\"project\"`` — exposed back through "
        "``GET /projects/{id}/attachments``."
    ),
    status_code=201,
    # Route signature is ``Request`` (so we can dispatch on Content-Type),
    # which means FastAPI can't auto-generate the request-body OpenAPI
    # schema. Declare it explicitly so Swagger UI renders body input
    # fields for both shapes. JSON schema comes from the Pydantic model
    # so Swagger stays in sync with the validators.
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ProjectCreateRequest.model_json_schema(
                        by_alias=True,
                    ),
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {
                                "type": "string", "minLength": 1, "maxLength": 255,
                            },
                            "description": {
                                "type": "string", "maxLength": 5000,
                            },
                            "statusExplanation": {
                                "type": "string", "maxLength": 5000,
                            },
                            "parentId": {
                                "type": "string",
                                "description": "Parent project UUID (optional).",
                            },
                            "status": {
                                "type": "string",
                                "description": "Project lifecycle status (new/draft/published/closed).",
                            },
                            "owner": {
                                "type": "string",
                                "description": "Division code: tmd1 / tmd2 / others.",
                            },
                            "ownerOther": {
                                "type": "string",
                                "description": (
                                    "Required (non-empty) when ``owner == 'others'``. "
                                    "Omit / null for other owner values."
                                ),
                            },
                            "vendorIds": {
                                "type": "string",
                                "description": (
                                    "JSON-encoded array of vendor UUIDs or vendor codes "
                                    "(e.g. ``[\"VN-ACME-...\"]``). Multipart can't carry "
                                    "typed arrays natively so the FE JSON-encodes them."
                                ),
                            },
                            "startDate": {
                                "type": "string", "format": "date-time",
                                "description": "ISO 8601, e.g. 2026-07-01T00:00:00+05:30",
                            },
                            "endDate": {
                                "type": "string", "format": "date-time",
                            },
                            "files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                                "description": (
                                    "Optional file uploads. Each file is stored as a "
                                    "comment row with ``body=NULL`` and "
                                    "``target_kind=\"project\"``. Allowed extensions "
                                    "and per-file size cap apply (see "
                                    "ATTACHMENTS_ALLOWED_EXTENSIONS, "
                                    "ATTACHMENTS_MAX_BYTES). Disguised binaries "
                                    "(e.g. .exe renamed to .pdf) are rejected by the "
                                    "magic-byte content sniff."
                                ),
                            },
                        },
                    },
                },
            },
        },
    },
)
async def create_project(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return await dispatch_create(
        request,
        schema_cls=ProjectCreateRequest,
        json_handler=lambda req, db, data:
            ProjectController.create(req, data, db),
        multipart_handler=lambda req, db:
            ProjectController.create_multipart(req, db),
        json_args=(db,),
        multipart_args=(db,),
    )


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


# ---------------------------------------------------------------------------
# Project attachments (project-honest URL surface; storage is the
# shared comments table — see app/api/v3/comments/_target_helper.py
# for the polymorphism whitelist).
# ---------------------------------------------------------------------------

def _list_project_attachments_rows(db: Session, project_uuid: str) -> List[Dict[str, Any]]:
    """Slim attachment rows for the GET endpoint. Each entry is one
    file, carrying the parent comment row id (use it with DELETE
    ``/api/v3/comments/{id}`` to soft-delete the attachment)."""
    from ....infrastructure.db.models.comment import CommentModel
    rows = (
        db.query(CommentModel)
        .filter(CommentModel.target_kind == "project")
        .filter(CommentModel.target_id == project_uuid)
        .filter(CommentModel.deleted_at.is_(None))
        .order_by(CommentModel.created_at.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for c in rows:
        for att in (c.attachments or []):
            # JSON column persists camelCase keys (see
            # ``AttachmentInfo.to_dict``).
            out.append({
                "id": c.id,
                "filename": att.get("filename"),
                "url": att.get("url"),
                "mimeType": att.get("mimeType") or att.get("mime_type"),
                "sizeBytes": att.get("sizeBytes") or att.get("size_bytes"),
                "uploadedAt": att.get("uploadedAt") or att.get("uploaded_at"),
                "createdAt": c.created_at.isoformat() if c.created_at else None,
                "createdBy": c.author_user_id,
            })
    return out


@router.get(
    "/{project_uuid}/attachments",
    dependencies=[require_permission(PROJECTS_READ)],
    summary="List attachments uploaded against this project",
)
def list_project_attachments(
    request: Request,
    project_uuid: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if (
        db.query(ProjectModel)
        .filter(ProjectModel.id == project_uuid)
        .filter(ProjectModel.deleted_at.is_(None))
        .first()
    ) is None:
        raise NotFoundError(f"Project {project_uuid} not found.")
    items = _list_project_attachments_rows(db, project_uuid)
    return BaseController.ok(data={
        "_type": "Collection",
        "total": len(items),
        "count": len(items),
        "_embedded": {"elements": items},
    })


@router.post(
    "/{project_uuid}/attachments",
    dependencies=[require_permission(COMMENTS_CREATE)],
    summary="Upload more attachments to an existing project (multipart)",
    description=(
        "Multipart-only endpoint for adding files to a project after "
        "create. Accepts ``files[]`` repeated; no comment body — "
        "projects do not surface a comment-text field on this URL. "
        "Files land in the comments table with ``body=NULL`` and "
        "``target_kind=\"project\"`` for storage; the response carries "
        "the FE-facing flat attachment shape."
    ),
    status_code=201,
)
async def upload_project_attachments(
    request: Request,
    project_uuid: str,
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if (
        db.query(ProjectModel)
        .filter(ProjectModel.id == project_uuid)
        .filter(ProjectModel.deleted_at.is_(None))
        .first()
    ) is None:
        raise NotFoundError(f"Project {project_uuid} not found.")
    files = files or []
    if not files:
        return BaseController.error(
            format_error_response(
                error_type="validation_error",
                message="At least one file is required.",
            ),
            status=422,
        )
    # Pre-validate (size + extension + magic-byte content sniff).
    file_err = pre_validate_files(files)
    if file_err is not None:
        return BaseController.error(
            format_error_response(
                error_type=file_err["error_type"],
                message=file_err["message"],
                details=file_err["details"],
            ),
            status=422,
        )
    current_user_id = getattr(request.state, "user_id", None)
    result = create_comment(
        db=db,
        target_kind="project",
        target_id=project_uuid,
        body=None,
        files=files,
        author_user_id=current_user_id,
    )
    if not result.is_success():
        return BaseController.error(
            format_error_response(
                error_type=result.error_type or "internal_error",
                message=result.error or "Failed to attach files.",
                details=result.details,
            ),
            status=422,
        )
    # Emit the slim attachment shape for these freshly-uploaded rows
    # only (caller wants "what just got created", not the full project
    # attachment listing).
    comment = result.data
    new_rows: List[Dict[str, Any]] = []
    for att in (comment.attachments or []):
        new_rows.append({
            "id": comment.id,
            "filename": att.filename if hasattr(att, "filename") else att.get("filename"),
            "url": att.url if hasattr(att, "url") else att.get("url"),
            "mimeType": att.mime_type if hasattr(att, "mime_type") else att.get("mime_type"),
            "sizeBytes": att.size_bytes if hasattr(att, "size_bytes") else att.get("size_bytes"),
            "uploadedAt": (
                att.uploaded_at.isoformat()
                if hasattr(att, "uploaded_at") and att.uploaded_at
                else att.get("uploaded_at") if isinstance(att, dict) else None
            ),
            "createdAt": comment.created_at.isoformat() if comment.created_at else None,
            "createdBy": comment.author_user_id,
        })
    return BaseController.created(data={
        "_type": "Collection",
        "total": len(new_rows),
        "count": len(new_rows),
        "_embedded": {"elements": new_rows},
    })
