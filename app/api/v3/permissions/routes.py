"""Permission catalog endpoints (doc 21 part B).

CRUD on the ``permissions`` table. Built-in permission rows (those
synced from ``app/core/permissions.py`` at startup) cannot be deleted —
only their name and description may be edited. Custom rows can be edited
or deleted freely.
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....core.base_controller import BaseController
from ....core.middleware.rbac import require_permission
from ....core.permissions import (
    PERMISSIONS_MANAGE,
    PERMISSIONS_READ,
)
from ....core.response import format_error_response
from ....infrastructure.db.repositories.rbac_repository import RbacRepository
from ....infrastructure.db.session import get_db
from .schemas import PermissionCreateRequest, PermissionUpdateRequest


router = APIRouter(prefix="/permissions", tags=["permissions"])


def _serialize(p) -> Dict[str, Any]:
    return {
        "_type": "Permission",
        "_links": {"self": {"href": f"/api/v3/permissions/{p.code}"}},
        "code": p.code,
        "name": p.name,
        "description": p.description,
        "isBuiltin": p.is_builtin,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
        "updatedAt": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get(
    "",
    dependencies=[require_permission(PERMISSIONS_READ)],
    summary="List permission catalog",
)
def list_permissions(
    request: Request,
    offset: int = Query(1, ge=1),
    pageSize: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = RbacRepository(db)
    rows, total = repo.list_permissions(
        offset=(offset - 1) * pageSize, limit=pageSize,
    )
    payload = {
        "_type": "Collection",
        "_links": {"self": {"href": f"/api/v3/permissions?offset={offset}&pageSize={pageSize}"}},
        "total": total,
        "count": len(rows),
        "pageSize": pageSize,
        "offset": offset,
        "_embedded": {"elements": [_serialize(r) for r in rows]},
    }
    return BaseController.ok(data=payload)


@router.get(
    "/{code}",
    dependencies=[require_permission(PERMISSIONS_READ)],
    summary="Get a permission row",
)
def get_permission(
    request: Request, code: str, db: Session = Depends(get_db),
) -> JSONResponse:
    row = RbacRepository(db).get_permission(code)
    if row is None:
        return BaseController.error(
            format_error_response("not_found", f"Permission {code} not found."),
            status=404,
        )
    return BaseController.ok(data=_serialize(row))


@router.post(
    "",
    dependencies=[require_permission(PERMISSIONS_MANAGE)],
    summary="Create a custom permission",
    status_code=201,
)
def create_permission(
    request: Request,
    data: PermissionCreateRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = RbacRepository(db)
    if repo.get_permission(data.code) is not None:
        return BaseController.error(
            format_error_response(
                "already_exists", f"Permission {data.code} already exists.",
            ),
            status=409,
        )
    row = repo.create_permission(
        code=data.code, name=data.name, description=data.description,
        is_builtin=False,
    )
    db.commit()
    return BaseController.created(data=_serialize(row))


@router.patch(
    "/{code}",
    dependencies=[require_permission(PERMISSIONS_MANAGE)],
    summary="Edit name/description of a permission (code is immutable)",
)
def update_permission(
    request: Request, code: str,
    data: PermissionUpdateRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = RbacRepository(db)
    row = repo.update_permission(
        code, name=data.name, description=data.description,
    )
    if row is None:
        return BaseController.error(
            format_error_response("not_found", f"Permission {code} not found."),
            status=404,
        )
    db.commit()
    return BaseController.ok(data=_serialize(row))


@router.delete(
    "/{code}",
    dependencies=[require_permission(PERMISSIONS_MANAGE)],
    summary="Delete a permission (built-in permissions are protected)",
)
def delete_permission(
    request: Request, code: str, db: Session = Depends(get_db),
) -> JSONResponse:
    repo = RbacRepository(db)
    row = repo.get_permission(code)
    if row is None:
        return BaseController.error(
            format_error_response("not_found", f"Permission {code} not found."),
            status=404,
        )
    if row.is_builtin:
        return BaseController.error(
            format_error_response(
                "forbidden",
                f"Permission {code} is built-in and cannot be deleted.",
            ),
            status=403,
        )
    repo.delete_permission(code)
    db.commit()
    return BaseController.no_content()
