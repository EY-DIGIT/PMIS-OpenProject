"""Vendor catalog routes.

- GET    /api/v3/vendors                   : list live vendors (newest first,
                                             each with its mapped projects)
- POST   /api/v3/vendors/create            : create a vendor (admin)
- PATCH  /api/v3/vendors/{id}              : edit a vendor (admin)
- DELETE /api/v3/vendors/{id}              : soft-delete a vendor (admin)
- POST   /api/v3/vendors/{id}/restore      : undelete a vendor (admin)
- GET    /api/v3/vendors/{id}/projects     : projects mapped to this vendor,
                                             excluding closed/completed
"""
from typing import Any, Dict, Iterable, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....core.base_controller import BaseController
from ....core.dependencies import get_current_user_id
from ....core.errors import AlreadyExistsError, NotFoundError
from ....core.middleware.rbac import require_permission
from ....core.rbac import Permission
from ....infrastructure.db.models.project import ProjectModel
from ....infrastructure.db.models.project_vendor import ProjectVendorModel
from ....infrastructure.db.repositories.vendor_repository import VendorRepository
from ....infrastructure.db.session import get_db
from .schemas import VendorCreateRequest, VendorUpdateRequest


router = APIRouter(prefix="/vendors", tags=["vendors"])


# Statuses that mean "this project is no longer interesting on a vendor's
# project list". Mirrors the lifecycle in projects.services.transitions.
# `closed` is the terminal status today; if/when a `completed` status is
# added, append it here.
_HIDDEN_PROJECT_STATUSES = {"closed", "completed"}


def _vendor_to_response(v, projects: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    d = v.to_dict()
    return {
        "_type": "Vendor",
        "id": d["id"],
        "name": d["name"],
        "description": d.get("description"),
        "active": d.get("active", True),
        "createdAt": d.get("created_at"),
        "updatedAt": d.get("updated_at"),
        "deletedAt": d.get("deleted_at"),
        # Projects this vendor is mapped to. Excludes closed/completed and
        # soft-deleted projects (same rule as GET /vendors/{id}/projects).
        # Empty list when the vendor has no live mappings — never null, so
        # the FE can iterate unconditionally.
        "projects": projects if projects is not None else [],
    }


def _projects_by_vendor(
    db: Session, vendor_ids: Iterable[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """Return ``{vendor_id: [{id, projectCode, name}, ...]}`` for the given vendors.

    One batched query — no N+1. Filters out closed/completed and
    soft-deleted projects so the response matches the rule used by
    GET /vendors/{id}/projects.
    """
    vendor_ids = list(vendor_ids)
    if not vendor_ids:
        return {}
    rows = (
        db.query(
            ProjectVendorModel.vendor_id,
            ProjectModel.id,
            ProjectModel.project_code,
            ProjectModel.name,
            ProjectModel.created_at,
        )
        .join(ProjectModel, ProjectModel.id == ProjectVendorModel.project_id)
        .filter(ProjectVendorModel.vendor_id.in_(vendor_ids))
        .filter(ProjectModel.deleted_at.is_(None))
        .filter(~ProjectModel.status.in_(_HIDDEN_PROJECT_STATUSES))
        .order_by(ProjectModel.created_at.desc(), ProjectModel.id.desc())
        .all()
    )
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for vendor_id, project_id, project_code, project_name, _created in rows:
        grouped.setdefault(vendor_id, []).append({
            "id": project_id,
            "projectCode": project_code,
            "name": project_name,
        })
    return grouped


@router.get(
    "",
    dependencies=[require_permission(Permission.VENDORS_READ)],
    summary="List live vendors (newest first)",
    description=(
        "Returns vendors that are not soft-deleted, ordered by createdAt "
        "descending so the latest vendor is row 0 in Search Vendor."
    ),
)
def list_vendors(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    repo = VendorRepository(db)
    vendors = repo.list_active()
    projects_by_vendor = _projects_by_vendor(db, (v.id for v in vendors))
    items = [
        _vendor_to_response(v, projects_by_vendor.get(v.id, []))
        for v in vendors
    ]
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
    # Name uniqueness check spans soft-deleted rows too — name has a DB-level
    # UNIQUE constraint regardless of deletion state. If a soft-deleted vendor
    # has the same name, restore it instead of creating a duplicate.
    if repo.get_by_name(data.name, include_deleted=True) is not None:
        raise AlreadyExistsError(
            f"A vendor named '{data.name}' already exists "
            "(it may be soft-deleted; restore it via POST /vendors/{id}/restore)."
        )
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
    repo = VendorRepository(db)
    m = repo.get_model_by_id(vendor_id)
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
        deleted_at=m.deleted_at, deleted_by=m.deleted_by,
    )
    projects = _projects_by_vendor(db, [domain.id]).get(domain.id, [])
    return BaseController.ok(data=_vendor_to_response(domain, projects))


@router.delete(
    "/{vendor_id}",
    dependencies=[require_permission(Permission.VENDORS_MANAGE)],
    summary="Soft-delete a vendor (admin)",
    description=(
        "Marks the vendor as deleted (stamps deletedAt, flips active=False). "
        "The vendor disappears from GET /vendors and from picker validation, "
        "but its project_vendors / milestone_vendors mapping rows are kept "
        "so a later restore brings the associations back."
    ),
)
def delete_vendor(
    request: Request,
    vendor_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = VendorRepository(db)
    actor_id = get_current_user_id(request)
    # Use include_deleted=False so a double-delete returns 404 rather than a
    # silent no-op — clearer signal to the FE.
    m = repo.get_model_by_id(vendor_id)
    if m is None:
        raise NotFoundError("Vendor not found or already deleted.")
    repo.soft_delete(vendor_id, actor_id=actor_id)
    db.commit()
    return BaseController.no_content()


@router.post(
    "/{vendor_id}/restore",
    dependencies=[require_permission(Permission.VENDORS_MANAGE)],
    summary="Restore a soft-deleted vendor (admin)",
    description=(
        "Clears deletedAt and flips active=True. All previously-existing "
        "project / milestone associations are preserved on disk and re-surface "
        "automatically. Note: the vendor's projects list (GET "
        "/vendors/{id}/projects) filters out closed/completed projects."
    ),
)
def restore_vendor(
    request: Request,
    vendor_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = VendorRepository(db)
    m = repo.get_model_by_id(vendor_id, include_deleted=True)
    if m is None:
        raise NotFoundError("Vendor not found.")
    if m.deleted_at is None:
        # Already live — return the current snapshot so the call is idempotent
        # rather than 409'ing a benign retry.
        live = repo.get_by_id(vendor_id)
        projects = _projects_by_vendor(db, [vendor_id]).get(vendor_id, [])
        return BaseController.ok(data=_vendor_to_response(live, projects))
    restored = repo.restore(vendor_id)
    db.commit()
    projects = _projects_by_vendor(db, [vendor_id]).get(vendor_id, [])
    return BaseController.ok(data=_vendor_to_response(restored, projects))


@router.get(
    "/{vendor_id}/projects",
    dependencies=[require_permission(Permission.VENDORS_READ)],
    summary="List projects mapped to this vendor (excluding closed/completed)",
    description=(
        "Returns the live, non-deleted, non-closed projects associated with "
        "this vendor. Closed/completed projects are filtered out — they're "
        "preserved on disk but no longer presented in the vendor's project "
        "list per product rule."
    ),
)
def list_vendor_projects(
    request: Request,
    vendor_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    repo = VendorRepository(db)
    if repo.get_by_id(vendor_id, include_deleted=True) is None:
        raise NotFoundError("Vendor not found.")
    rows = (
        db.query(ProjectModel)
        .join(ProjectVendorModel, ProjectVendorModel.project_id == ProjectModel.id)
        .filter(ProjectVendorModel.vendor_id == vendor_id)
        .filter(ProjectModel.deleted_at.is_(None))
        .filter(~ProjectModel.status.in_(_HIDDEN_PROJECT_STATUSES))
        .order_by(ProjectModel.created_at.desc(), ProjectModel.id.desc())
        .all()
    )
    items: List[Dict[str, Any]] = [
        {
            "_type": "Project",
            "id": p.id,
            "projectCode": p.project_code,
            "name": p.name,
            "status": p.status,
            "createdAt": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]
    return BaseController.ok(data={
        "_type": "Collection",
        "total": len(items),
        "count": len(items),
        "_embedded": {"elements": items},
    })
