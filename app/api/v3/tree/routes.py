"""Project tree endpoint."""
from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ....core.base_controller import BaseController
from ....core.middleware.rbac import require_permission
from ....core.rbac import Permission
from ....infrastructure.db.session import get_db
from .service import build_project_tree


router = APIRouter(prefix="/projects", tags=["tree"])


@router.get(
    "/{project_id}/tree",
    dependencies=[require_permission(Permission.PROJECTS_READ)],
    summary="Full M/A/T/S tree under a project",
    description=(
        "Returns the full project tree in one call: milestones → activities → "
        "tasks → subtasks, with resource details inlined for resource-type "
        "entities. Soft-deleted rows are filtered by default; pass "
        "`includeDeleted=true` to include them (admin-only in practice)."
    ),
)
def get_project_tree(
    request: Request,
    project_id: int,
    includeDeleted: bool = Query(False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    tree = build_project_tree(db, project_id, include_deleted=includeDeleted)
    return BaseController.ok(data=tree)
