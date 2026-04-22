"""Vendor catalog routes.

- GET  /api/v3/vendors       : list active vendors (any authenticated user)
- POST /api/v3/vendors       : create a vendor (admin only, for seeding)
- PATCH /api/v3/vendors/{id} : edit a vendor (admin only)
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....core.base_controller import BaseController
from ....core.errors import AlreadyExistsError
from ....core.middleware.rbac import require_permission
from ....core.rbac import Permission
from ....infrastructure.db.repositories.vendor_repository import VendorRepository
from ....infrastructure.db.session import get_db
from .schemas import VendorCreateRequest, VendorUpdateRequest


router = APIRouter(prefix="/vendors", tags=["vendors"])


def _vendor_to_response(v) -> Dict[str, Any]:
    d = v.to_dict()
    return {
        "_type": "Vendor",
        "id": d["id"],
        "name": d["name"],
        "description": d.get("description"),
        "active": d.get("active", True),
        "createdAt": d.get("created_at"),
        "updatedAt": d.get("updated_at"),
    }


@router.get(
    "",
    dependencies=[require_permission(Permission.VENDORS_READ)],
    summary="List active vendors",
)
def list_vendors(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    repo = VendorRepository(db)
    items = [_vendor_to_response(v) for v in repo.list_active()]
    return BaseController.ok(data={
        "_type": "Collection",
        "total": len(items),
        "count": len(items),
        "_embedded": {"elements": items},
    })


@router.post(
    "/create",
    dependencies=[require_permission(Permission.VENDORS_MANAGE)],
    summary="Create a vendor (admin)",
    status_code=201,
)
def create_vendor(
    request: Request,
    data: VendorCreateRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = VendorRepository(db)
    if repo.get_by_name(data.name) is not None:
        raise AlreadyExistsError(f"A vendor named '{data.name}' already exists.")
    vendor = repo.create(
        name=data.name,
        description=data.description,
        active=data.active,
    )
    db.commit()
    return BaseController.created(data=_vendor_to_response(vendor))


@router.patch(
    "/{vendor_id}",
    dependencies=[require_permission(Permission.VENDORS_MANAGE)],
    summary="Update a vendor (admin)",
)
def update_vendor(
    request: Request,
    vendor_id: str,
    data: VendorUpdateRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    from ....infrastructure.db.models.vendor import VendorModel
    from ....core.errors import NotFoundError

    m = db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
    if m is None:
        raise NotFoundError("Vendor not found.")
    if data.name is not None:
        m.name = data.name
    if data.description is not None:
        m.description = data.description
    if data.active is not None:
        m.active = data.active
    db.flush()
    db.commit()
    from ....domain.vendors.vendor import Vendor
    domain = Vendor(
        id=m.id, name=m.name, description=m.description, active=bool(m.active),
        created_at=m.created_at, updated_at=m.updated_at,
    )
    return BaseController.ok(data=_vendor_to_response(domain))
