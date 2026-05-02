"""
Role routes - URL definitions with permission bindings.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from ....core.base_controller import BaseController
from ....core.middleware.rbac import require_permission, require_authenticated
from ....core.permissions import ADMIN_ROLE_NAME, RBAC_ASSIGN
from ....core.response import format_error_response
from ....infrastructure.db.repositories.rbac_repository import RbacRepository
from ....infrastructure.db.session import get_db
from .controller import RoleController
from .schemas import (
    RoleCreateRequest,
    RoleUpdateRequest,
    RoleListQuery,
    RolePermissionsReplaceRequest,
)
from .permissions import (
    ROLES_CREATE,
    ROLES_READ,
    ROLES_UPDATE,
    ROLES_DELETE
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.post(
    "/create",
    dependencies=[require_permission(ROLES_CREATE)],
    summary="Create role",
    description="Create a new role",
    status_code=201
)
def create_role(
    request: Request,
    data: RoleCreateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new role.

    Requires: ROLES_CREATE permission (admin only)
    """
    return RoleController.create(request, data, db)


@router.get(
    "",
    dependencies=[require_permission(ROLES_READ)],
    summary="List roles",
    description="List all roles with pagination"
)
def list_roles(
    request: Request,
    offset: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List roles with pagination.

    Requires: ROLES_READ permission (admin only)
    """
    query = RoleListQuery(offset=offset, pageSize=pageSize)
    return RoleController.list(request, query, db)


@router.get(
    "/{role_id}",
    dependencies=[require_permission(ROLES_READ)],
    summary="Get role",
    description="Get role by ID"
)
def get_role(
    request: Request,
    role_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get role by ID.

    Requires: ROLES_READ permission (admin only)
    """
    return RoleController.get(request, role_id, db)


@router.patch(
    "/{role_id}",
    dependencies=[require_permission(ROLES_UPDATE)],
    summary="Update role",
    description="Update role details"
)
def update_role(
    request: Request,
    role_id: int,
    data: RoleUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update role details.

    Requires: ROLES_UPDATE permission (admin only)
    Note: Builtin roles cannot be modified
    """
    return RoleController.update(request, role_id, data, db)


@router.delete(
    "/{role_id}",
    dependencies=[require_permission(ROLES_DELETE)],
    summary="Delete role",
    description="Delete a role"
)
def delete_role(
    request: Request,
    role_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete a role.

    Requires: ROLES_DELETE permission (admin only)
    Note: The built-in 'admin' role cannot be deleted; other roles
    (including the seeded 'member'/'viewer') are deletable.
    """
    return RoleController.delete(request, role_id, db)


# ---------------------------------------------------------------------------
# Role-permission management (doc 21 part B)
# ---------------------------------------------------------------------------

def _admin_role_guard(role) -> Dict[str, Any]:
    """Returns an error payload + status when the role is the admin role,
    else None."""
    if role is not None and role.name == ADMIN_ROLE_NAME:
        return format_error_response(
            "forbidden",
            "The built-in 'admin' role's permission set is auto-managed "
            "and cannot be modified.",
        )
    return None


@router.get(
    "/{role_id}/permissions",
    dependencies=[require_permission(ROLES_READ)],
    summary="List a role's permissions",
)
def list_role_permissions(
    request: Request, role_id: int, db: Session = Depends(get_db),
):
    repo = RbacRepository(db)
    role = repo.get_role(role_id)
    if role is None:
        return BaseController.error(
            format_error_response("not_found", f"Role {role_id} not found."),
            status=404,
        )
    codes = repo.list_role_permissions(role_id)
    return BaseController.ok(data={
        "_type": "RolePermissions",
        "_links": {"self": {"href": f"/api/v3/roles/{role_id}/permissions"}},
        "roleId": role_id,
        "roleName": role.name,
        "permissions": codes,
    })


@router.put(
    "/{role_id}/permissions",
    dependencies=[require_permission(ROLES_UPDATE)],
    summary="Replace a role's permission set",
)
def replace_role_permissions(
    request: Request, role_id: int,
    data: RolePermissionsReplaceRequest,
    db: Session = Depends(get_db),
):
    repo = RbacRepository(db)
    role = repo.get_role(role_id)
    if role is None:
        return BaseController.error(
            format_error_response("not_found", f"Role {role_id} not found."),
            status=404,
        )
    err = _admin_role_guard(role)
    if err is not None:
        return BaseController.error(err, status=403)
    # Validate every code exists.
    bogus = [c for c in data.permissions if repo.get_permission(c) is None]
    if bogus:
        return BaseController.error(
            format_error_response(
                "validation_error",
                f"Unknown permission code(s): {', '.join(bogus)}",
            ),
            status=422,
        )
    repo.replace_role_permissions(role_id, list(dict.fromkeys(data.permissions)))
    db.commit()
    return BaseController.ok(data={
        "roleId": role_id,
        "permissions": repo.list_role_permissions(role_id),
    })


@router.post(
    "/{role_id}/permissions/{code}",
    dependencies=[require_permission(ROLES_UPDATE)],
    summary="Grant a single permission to a role",
)
def grant_role_permission(
    request: Request, role_id: int, code: str,
    db: Session = Depends(get_db),
):
    repo = RbacRepository(db)
    role = repo.get_role(role_id)
    if role is None:
        return BaseController.error(
            format_error_response("not_found", f"Role {role_id} not found."),
            status=404,
        )
    err = _admin_role_guard(role)
    if err is not None:
        return BaseController.error(err, status=403)
    if repo.get_permission(code) is None:
        return BaseController.error(
            format_error_response(
                "not_found", f"Permission {code} not found.",
            ),
            status=404,
        )
    repo.grant_permissions_to_role(role_id, [code])
    db.commit()
    return BaseController.ok(data={
        "roleId": role_id,
        "permissions": repo.list_role_permissions(role_id),
    })


@router.delete(
    "/{role_id}/permissions/{code}",
    dependencies=[require_permission(ROLES_UPDATE)],
    summary="Revoke a single permission from a role",
)
def revoke_role_permission(
    request: Request, role_id: int, code: str,
    db: Session = Depends(get_db),
):
    repo = RbacRepository(db)
    role = repo.get_role(role_id)
    if role is None:
        return BaseController.error(
            format_error_response("not_found", f"Role {role_id} not found."),
            status=404,
        )
    err = _admin_role_guard(role)
    if err is not None:
        return BaseController.error(err, status=403)
    repo.revoke_permission_from_role(role_id, code)
    db.commit()
    return BaseController.no_content()
