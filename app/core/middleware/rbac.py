"""
RBAC middleware: permission-based authorization (doc 21B + doc 41 scope).

Two layers:

  * ``require_permission(code)`` — global gate. Reads
    ``request.state.user_permissions`` (the flat union populated by
    ``AuthenticationMiddleware``). Backwards-compatible with every
    pre-doc-41 route.

  * ``require_project_permission(code)`` /
    ``require_org_permission(code)`` — scope-aware gates (doc 41).
    Resolve the project_id / org_id from the request path (with an
    ancestor lookup chain for M-A-T-S routes), then consult
    ``request.state.scoped_permissions``. A user passes if they hold
    the code at the matching scope **OR** at global scope (global
    always wins, mirroring how super_admin works in any RBAC system).

Anonymous calls have empty permission sets → every gate rejects 401.
"""
from typing import Dict, Optional, Set, Tuple, Union
from fastapi import Depends, Request

from ..errors import AuthenticationError, AuthorizationError


def _user_permissions(request: Request) -> Set[str]:
    return getattr(request.state, "user_permissions", set()) or set()


def _scoped_permissions(
    request: Request,
) -> Dict[Tuple[str, Optional[str]], Set[str]]:
    return getattr(request.state, "scoped_permissions", {}) or {}


def _user_id(request: Request) -> Optional[str]:
    """Doc 26: returns the caller's UUID (was int pre-doc-26)."""
    return getattr(request.state, "user_id", None)


def require_permission(permission: Union[str, "object"]):
    """
    Dependency factory: require the caller to hold a specific permission.

    ``permission`` is the canonical string code (recommended). The legacy
    ``Permission`` enum from ``app.core.rbac`` is also accepted to keep
    in-flight route imports working — ``.value`` is read off enum members.
    """
    code = getattr(permission, "value", permission)

    def check_permission(request: Request) -> None:
        if _user_id(request) is None:
            raise AuthenticationError("Authentication required")
        if code not in _user_permissions(request):
            raise AuthorizationError(
                f"Insufficient permissions. Required: {code}"
            )

    return Depends(check_permission)


def require_authenticated():
    """Dependency: require an authenticated (non-anonymous) caller."""

    def check_authenticated(request: Request) -> None:
        if _user_id(request) is None:
            raise AuthenticationError("Authentication required")

    return Depends(check_authenticated)


def require_admin():
    """Dependency: require the caller to be a superuser (admin role)."""

    def check_admin(request: Request) -> None:
        if _user_id(request) is None:
            raise AuthenticationError("Authentication required")
        if not getattr(request.state, "is_admin", False):
            raise AuthorizationError("Admin privileges required")

    return Depends(check_admin)


# ---------------------------------------------------------------------------
# Doc 41 — scope-aware helpers
# ---------------------------------------------------------------------------

# Project-id resolver path-param keys, in priority order. ``project_uuid``
# is the modern convention (doc 26+); other variants stay listed for
# legacy routes.
_PROJECT_PATH_PARAM_KEYS = ("project_uuid", "project_id", "projectId")

# M-A-T-S + project-membership ancestor resolver keys. When the request
# path carries one of these, the dependency joins back to the owning
# project_id via SQL.
_ANCESTOR_PATH_PARAM_KEYS = (
    "milestone_id", "milestoneId",
    "activity_id", "activityId",
    "task_id", "taskId",
    "subtask_id", "subtaskId",
    # nested-subtask create routes use parent_subtask_id; resolution
    # is the same as subtask_id (subtasks.task_id always points at the
    # ROOT task — see app/infrastructure/db/models/subtask.py:4).
    "parent_subtask_id", "parentSubtaskId",
    # project-membership writes live at /memberships/{membership_id};
    # we resolve back to the owning project_id via project_members.
    "membership_id", "membershipId",
    # comments/attachments routes are typed by target — when carrying
    # only the comment_id / attachment_id we walk via the comment's
    # target_type + target_id.
    "comment_id", "commentId",
    "attachment_id", "attachmentId",
)


def _resolve_project_id_from_path(request: Request) -> Optional[str]:
    """Pull the project_id from the URL.

    Resolution order:
      1. Direct project param (``project_uuid`` / ``project_id``).
      2. Ancestor lookup: if the path carries ``milestone_id`` /
         ``activity_id`` / ``task_id`` / ``subtask_id``, walk back to
         the owning project via the DB.

    The DB lookup uses a fresh session (auth middleware doesn't keep
    one open). The result is cached on ``request.state`` so a route
    with multiple ``require_project_permission`` decorators only pays
    the lookup cost once.
    """
    cached = getattr(request.state, "_resolved_project_id", None)
    if cached is not None:
        return cached or None  # cached "" means "no resolution"

    path_params = getattr(request, "path_params", {}) or {}

    # Direct.
    for key in _PROJECT_PATH_PARAM_KEYS:
        v = path_params.get(key)
        if v:
            request.state._resolved_project_id = v
            return v

    # Ancestor lookup.
    for key in _ANCESTOR_PATH_PARAM_KEYS:
        v = path_params.get(key)
        if not v:
            continue
        project_id = _ancestor_project_id(key, v)
        if project_id:
            request.state._resolved_project_id = project_id
            return project_id

    # Mark as resolved-to-nothing so we don't redo the lookup.
    request.state._resolved_project_id = ""
    return None


def _ancestor_project_id(param_key: str, value: str) -> Optional[str]:
    """Walk M-A-T-S → project via the DB.

    Joins are short and indexed:
      milestone_id → milestones.project_id
      activity_id  → activities.project_id  (denormalised on the row)
      task_id      → tasks.activity_id → activities.project_id
      subtask_id   → subtasks.task_id → tasks.activity_id → activities.project_id
    """
    # Local imports to keep the module light at import-time.
    from ...infrastructure.db.session import SessionLocal
    from sqlalchemy import text

    base = param_key.replace("Id", "_id")  # camelCase variants → snake
    # parent_subtask_id resolves identically to subtask_id (the
    # subtasks.task_id column points at the ROOT task regardless of
    # nesting depth — see app/infrastructure/db/models/subtask.py).
    if base == "parent_subtask_id":
        base = "subtask_id"
    db = SessionLocal()
    try:
        if base == "milestone_id":
            row = db.execute(
                text("SELECT project_id FROM milestones WHERE id = :id"),
                {"id": value},
            ).first()
            return row[0] if row else None
        if base == "activity_id":
            row = db.execute(
                text("SELECT project_id FROM activities WHERE id = :id"),
                {"id": value},
            ).first()
            return row[0] if row else None
        if base == "task_id":
            row = db.execute(
                text(
                    "SELECT a.project_id FROM tasks t "
                    "JOIN activities a ON a.id = t.activity_id "
                    "WHERE t.id = :id"
                ),
                {"id": value},
            ).first()
            return row[0] if row else None
        if base == "subtask_id":
            row = db.execute(
                text(
                    "SELECT a.project_id FROM subtasks s "
                    "JOIN tasks t ON t.id = s.task_id "
                    "JOIN activities a ON a.id = t.activity_id "
                    "WHERE s.id = :id"
                ),
                {"id": value},
            ).first()
            return row[0] if row else None
        if base == "membership_id":
            row = db.execute(
                text("SELECT project_id FROM project_members WHERE id = :id"),
                {"id": value},
            ).first()
            return row[0] if row else None
        if base == "comment_id":
            # Comment carries (target_type, target_id). Resolve to project
            # via the chain implied by target_type.
            row = db.execute(
                text("SELECT target_type, target_id FROM comments WHERE id = :id"),
                {"id": value},
            ).first()
            if row is None:
                return None
            return _project_id_for_target(db, row[0], row[1])
        if base == "attachment_id":
            # Attachments live inline on comments (post doc 35) — same
            # resolution chain as comment_id.
            row = db.execute(
                text(
                    "SELECT c.target_type, c.target_id FROM comments c "
                    "WHERE c.id = (SELECT comment_id FROM attachments WHERE id = :id)"
                ),
                {"id": value},
            ).first()
            if row is None:
                return None
            return _project_id_for_target(db, row[0], row[1])
    finally:
        db.close()
    return None


def _project_id_for_target(db, target_type: str, target_id: str) -> Optional[str]:
    """Walk a comment/attachment's (target_type, target_id) up to the project."""
    from sqlalchemy import text
    if target_type == "project":
        return target_id
    if target_type == "milestone":
        row = db.execute(
            text("SELECT project_id FROM milestones WHERE id = :id"),
            {"id": target_id},
        ).first()
        return row[0] if row else None
    if target_type == "activity":
        row = db.execute(
            text("SELECT project_id FROM activities WHERE id = :id"),
            {"id": target_id},
        ).first()
        return row[0] if row else None
    if target_type == "task":
        row = db.execute(
            text(
                "SELECT a.project_id FROM tasks t "
                "JOIN activities a ON a.id = t.activity_id "
                "WHERE t.id = :id"
            ),
            {"id": target_id},
        ).first()
        return row[0] if row else None
    if target_type == "subtask":
        row = db.execute(
            text(
                "SELECT a.project_id FROM subtasks s "
                "JOIN tasks t ON t.id = s.task_id "
                "JOIN activities a ON a.id = t.activity_id "
                "WHERE s.id = :id"
            ),
            {"id": target_id},
        ).first()
        return row[0] if row else None
    return None


def _has_scoped_permission(
    request: Request, code: str, scope_key: Tuple[str, Optional[str]],
) -> bool:
    """True iff the user holds ``code`` at ``scope_key`` OR globally.

    Global wins by design: a global super_admin / admin pass every
    scoped check. The per-scope bucket layered on top never *removes*
    permissions — assignments are purely additive.
    """
    scoped = _scoped_permissions(request)
    if code in scoped.get(("global", None), set()):
        return True
    if code in scoped.get(scope_key, set()):
        return True
    # Backwards-compat: legacy ``user_permissions`` flat set may still
    # carry the perm via paths the scope view didn't include.
    return code in _user_permissions(request)


def require_project_permission(permission: Union[str, "object"]):
    """Doc 41 — gate ``permission`` on the project_id in the URL.

    Resolves project_id directly from path or via M-A-T-S ancestor.
    User passes if they hold ``permission`` at scope
    ``("project", project_id)`` OR at global scope.
    """
    code = getattr(permission, "value", permission)

    def check(request: Request) -> None:
        if _user_id(request) is None:
            raise AuthenticationError("Authentication required")
        project_id = _resolve_project_id_from_path(request)
        if project_id is None:
            raise AuthorizationError(
                f"require_project_permission({code}) used on a route "
                f"without a resolvable project_id."
            )
        if not _has_scoped_permission(request, code, ("project", project_id)):
            raise AuthorizationError(
                f"Insufficient permissions. Required: {code} on project {project_id}"
            )

    return Depends(check)


def require_org_permission(permission: Union[str, "object"]):
    """Doc 41 — gate ``permission`` on the vendor_id (= organization)
    in the URL.

    Looks for ``vendor_id`` / ``vendor_uuid`` / ``organization_id``
    in path_params. User passes if they hold the code at scope
    ``("org", <vendor_id>)`` OR at global scope.
    """
    code = getattr(permission, "value", permission)

    def check(request: Request) -> None:
        if _user_id(request) is None:
            raise AuthenticationError("Authentication required")
        path_params = getattr(request, "path_params", {}) or {}
        org_id = (
            path_params.get("vendor_id")
            or path_params.get("vendor_uuid")
            or path_params.get("organization_id")
        )
        if org_id is None:
            raise AuthorizationError(
                f"require_org_permission({code}) used on a route without "
                f"a vendor_id / organization_id path param."
            )
        if not _has_scoped_permission(request, code, ("org", org_id)):
            raise AuthorizationError(
                f"Insufficient permissions. Required: {code} on organization {org_id}"
            )

    return Depends(check)
