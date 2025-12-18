"""
Work Package Type routes - URL definitions with permission bindings.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from .controller import WorkPackageTypeController
from .schemas import (
    WorkPackageTypeCreateRequest,
    WorkPackageTypeUpdateRequest,
    WorkPackageTypeListQuery,
)
from .permissions import (
    WORK_PACKAGE_TYPES_VIEW,
    WORK_PACKAGE_TYPES_MANAGE,
)
from ....core.middleware.rbac import require_permission
from ....infrastructure.db.session import get_db

router = APIRouter(prefix="/work_package_types", tags=["work_package_types"]) 


@router.get("", dependencies=[require_permission(WORK_PACKAGE_TYPES_VIEW)], summary="List work package types")
def list_types(request: Request, offset: int = 1, pageSize: int = 20, db: Session = Depends(get_db)) -> Dict[str, Any]:
    query = WorkPackageTypeListQuery(offset=offset, pageSize=pageSize)
    return WorkPackageTypeController.list(request, query, db)


@router.get("/{type_id}", dependencies=[require_permission(WORK_PACKAGE_TYPES_VIEW)], summary="Get work package type")
def get_type(request: Request, type_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return WorkPackageTypeController.get(request, type_id, db)


@router.post("", dependencies=[require_permission(WORK_PACKAGE_TYPES_MANAGE)], summary="Create work package type", status_code=201)
def create_type(request: Request, data: WorkPackageTypeCreateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return WorkPackageTypeController.create(request, data, db)


@router.patch("/{type_id}", dependencies=[require_permission(WORK_PACKAGE_TYPES_MANAGE)], summary="Update work package type")
def update_type(request: Request, type_id: int, data: WorkPackageTypeUpdateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return WorkPackageTypeController.update(request, type_id, data, db)


@router.delete("/{type_id}", dependencies=[require_permission(WORK_PACKAGE_TYPES_MANAGE)], summary="Delete work package type")
def delete_type(request: Request, type_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return WorkPackageTypeController.delete(request, type_id, db)
