"""Activities routes."""
from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ....core.middleware.rbac import require_permission
from ....infrastructure.db.session import get_db
from .controller import ActivityController
from .permissions import (
    ACTIVITIES_CREATE, ACTIVITIES_READ, ACTIVITIES_UPDATE,
    ACTIVITIES_DELETE, ACTIVITIES_RESTORE,
)
from .schemas import ActivityCreateRequest, ActivityUpdateRequest, ActivityListQuery


activities_milestone_router = APIRouter(prefix="/milestones", tags=["activities"])
activities_router = APIRouter(prefix="/activities", tags=["activities"])


@activities_milestone_router.post(
    "/{milestone_id}/activities",
    dependencies=[require_permission(ACTIVITIES_CREATE)],
    summary="Create activity under milestone",
    status_code=201,
)
def create(
    request: Request, milestone_id: int,
    data: ActivityCreateRequest, db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ActivityController.create(request, milestone_id, data, db)


@activities_milestone_router.get(
    "/{milestone_id}/activities",
    dependencies=[require_permission(ACTIVITIES_READ)],
    summary="List activities under milestone",
)
def list_(
    request: Request, milestone_id: int,
    offset: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
    includeDeleted: bool = Query(False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ActivityController.list(
        request, milestone_id,
        ActivityListQuery(offset=offset, pageSize=pageSize, includeDeleted=includeDeleted),
        db,
    )


@activities_router.get(
    "/{activity_id}",
    dependencies=[require_permission(ACTIVITIES_READ)],
    summary="Get activity by id",
)
def get(request: Request, activity_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return ActivityController.get(request, activity_id, db)


@activities_router.patch(
    "/{activity_id}",
    dependencies=[require_permission(ACTIVITIES_UPDATE)],
    summary="Update activity (handles type transitions + resource upsert)",
)
def update(
    request: Request, activity_id: int,
    data: ActivityUpdateRequest, db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ActivityController.update(request, activity_id, data, db)


@activities_router.delete(
    "/{activity_id}",
    dependencies=[require_permission(ACTIVITIES_DELETE)],
    summary="Soft-delete activity (cascades)",
)
def delete(request: Request, activity_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return ActivityController.delete(request, activity_id, db)


@activities_router.post(
    "/{activity_id}/restore",
    dependencies=[require_permission(ACTIVITIES_RESTORE)],
    summary="Restore a soft-deleted activity (admin)",
)
def restore(request: Request, activity_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    return ActivityController.restore(request, activity_id, db)
