"""Catalog routes — project_status_transitions + project_owners + divisions + project_categories."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.base_controller import BaseController
from ....core.errors import NotFoundError, ValidationError
from ....core.middleware.rbac import require_authenticated, require_permission
from ....core.rbac import Permission
from ....domain.resource_types.resource_type import (
    DIVISION_CHOICES,
    DIVISION_OTHERS,
)
from ....infrastructure.db.models.user import UserModel
from ....infrastructure.db.repositories.project_owner_repository import (
    ProjectOwnerRepository,
)
from ....infrastructure.db.repositories.project_status_transition_repository import (
    ProjectStatusTransitionRepository,
)
from ....infrastructure.db.session import get_db


router = APIRouter(tags=["catalogs"])


# ---------------------------------------------------------------------------
# Divisions
# ---------------------------------------------------------------------------
#
# Division values back the activity-resource classification picker AND are
# reused by the FE as the project-owner / division picker (see HTML
# `buildDivisionField` — same dropdown serves both purposes). The list is a
# static in-code constant in `app.domain.resource_types.resource_type`; this
# endpoint surfaces it so the FE doesn't have to hard-code labels.
#
# Display labels (TMD1 / TMD2 / Others) are uppercase per the design;
# stored / wire codes are lowercase (`tmd1` / `tmd2` / `others`). The FE
# sends the lowercase code back in `division` fields.

_DIVISION_LABELS = {
    "tmd1": "TMD1",
    "tmd2": "TMD2",
    "others": "Others",
}


@router.get(
    "/divisions",
    dependencies=[require_authenticated()],
    summary="List the division catalog",
    description=(
        "Returns the division choices that back the activity-resource "
        "classification picker. The same list is reused by the FE as the "
        "project-owner / division picker. Each entry has a `code` (the wire "
        "value the API expects in `division` fields) and a `label` (the "
        "display string). The `requiresOther` flag on the 'others' entry "
        "tells the FE to show the free-text 'Specify' input."
    ),
)
def list_divisions(
    request: Request, db: Session = Depends(get_db),
) -> JSONResponse:
    items = [
        {
            "_type": "Division",
            "code": code,
            "label": _DIVISION_LABELS.get(code, code),
            "requiresOther": code == DIVISION_OTHERS,
        }
        for code in DIVISION_CHOICES
    ]
    return BaseController.ok(data={
        "_type": "Collection",
        "_links": {"self": {"href": "/api/v3/divisions"}},
        "total": len(items),
        "count": len(items),
        "_embedded": {"elements": items},
    })


# ---------------------------------------------------------------------------
# Project status transitions
# ---------------------------------------------------------------------------


@router.get(
    "/project_status_transitions",
    dependencies=[require_authenticated()],
    summary="List the project status transition catalog",
    description=(
        "Returns every active (from_status, to_status) edge in the project "
        "lifecycle, plus the initial-status seed (from_status=null). The "
        "frontend can use this to build the next-step dropdown for any "
        "project state, and to know which statuses are valid in request "
        "bodies. Validation in the create-project service rejects any "
        "status not present in this catalog with `invalid_status`."
    ),
)
def list_project_status_transitions(
    request: Request, db: Session = Depends(get_db),
) -> JSONResponse:
    rows = ProjectStatusTransitionRepository(db).list_active()
    items = [
        {
            "_type": "ProjectStatusTransition",
            "id": r.id,
            "fromStatus": r.from_status,
            "toStatus": r.to_status,
            "requiresAdmin": r.requires_admin,
            "versionOnly": r.version_only,
            "active": r.active,
            "description": r.description,
        }
        for r in rows
    ]
    return BaseController.ok(data={
        "_type": "Collection",
        "_links": {"self": {"href": "/api/v3/project_status_transitions"}},
        "total": len(items),
        "count": len(items),
        "_embedded": {"elements": items},
    })


# ---------------------------------------------------------------------------
# Project owners
# ---------------------------------------------------------------------------


class ProjectOwnerCreateRequest(BaseModel):
    """Body for POST /project_owners/create."""
    user_id: Optional[int] = Field(
        None, alias="userId",
        description="Existing user.id to add to the owner whitelist.",
    )
    login: Optional[str] = Field(
        None, max_length=255,
        description=(
            "Alternative to userId — supply the user login string. The "
            "service resolves it to a user_id."
        ),
    )
    display_name: Optional[str] = Field(
        None, alias="displayName", max_length=255,
        description="Optional UI label override.",
    )

    model_config = {"populate_by_name": True}


@router.get(
    "/project_owners",
    dependencies=[require_authenticated()],
    summary="List the project-owner whitelist (active rows)",
    description=(
        "Returns active project owners with the backing user info. Only "
        "users present in this list are accepted as the ``owner`` of a "
        "newly-created project."
    ),
)
def list_project_owners(
    request: Request, db: Session = Depends(get_db),
) -> JSONResponse:
    rows = ProjectOwnerRepository(db).list_active_with_user()
    items = []
    for owner_row, user_row in rows:
        items.append({
            "_type": "ProjectOwner",
            "id": owner_row.id,
            "userId": user_row.id,
            "login": user_row.login,
            "email": user_row.email,
            "firstName": user_row.first_name,
            "lastName": user_row.last_name,
            "displayName": owner_row.display_name,
            "active": owner_row.active,
        })
    return BaseController.ok(data={
        "_type": "Collection",
        "_links": {"self": {"href": "/api/v3/project_owners"}},
        "total": len(items),
        "count": len(items),
        "_embedded": {"elements": items},
    })


@router.post(
    "/project_owners/create",
    dependencies=[require_permission(Permission.PROJECTS_CREATE)],
    summary="Add a user to the project-owner whitelist (admin-curated)",
    status_code=201,
)
def create_project_owner(
    request: Request,
    data: ProjectOwnerCreateRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    if data.user_id is None and not data.login:
        raise ValidationError(
            "Either userId or login must be provided.",
        )
    user_q = db.query(UserModel)
    if data.user_id is not None:
        user = user_q.filter(UserModel.id == data.user_id).first()
        if user is None:
            raise NotFoundError(f"User with id {data.user_id} not found.")
    else:
        user = user_q.filter(UserModel.login == data.login).first()
        if user is None:
            raise NotFoundError(f"User with login '{data.login}' not found.")

    repo = ProjectOwnerRepository(db)
    row = repo.add_by_user_id(user.id, display_name=data.display_name)
    db.commit()
    return BaseController.created(data={
        "_type": "ProjectOwner",
        "id": row.id, "userId": user.id, "login": user.login,
        "email": user.email, "firstName": user.first_name,
        "lastName": user.last_name, "displayName": row.display_name,
        "active": row.active,
    })


@router.delete(
    "/project_owners/{user_id}",
    dependencies=[require_permission(Permission.PROJECTS_CREATE)],
    summary="Deactivate a project owner (soft — toggles active=False)",
)
def deactivate_project_owner(
    request: Request, user_id: int, db: Session = Depends(get_db),
) -> JSONResponse:
    ok = ProjectOwnerRepository(db).deactivate_by_user_id(user_id)
    if not ok:
        raise NotFoundError(f"No project_owners row for user_id {user_id}.")
    db.commit()
    return BaseController.ok(data={"_type": "Success", "userId": user_id})
