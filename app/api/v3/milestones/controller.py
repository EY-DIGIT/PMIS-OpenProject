"""Milestones controller."""
from typing import Any, Dict
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....core.base_controller import BaseController
from ....core.response import format_collection_response
from .schemas import MilestoneCreateRequest, MilestoneUpdateRequest, MilestoneListQuery
from .services import (
    create_milestone, get_milestone, list_milestones,
    update_milestone, delete_milestone, restore_milestone,
)


def format_milestone_response(m: dict, base_url: str = "/api/v3") -> Dict[str, Any]:
    return {
        "_type": "Milestone",
        "_links": {
            "self": {"href": f"{base_url}/milestones/{m['id']}", "title": m["name"]},
            "project": {"href": f"{base_url}/projects/{m['project_id']}"},
        },
        "id": m["id"],
        "projectId": m["project_id"],
        "name": m["name"],
        "description": m["description"],
        "startDate": m["start_date"],
        "endDate": m["end_date"],
        "position": m["position"],
        "createdAt": m["created_at"],
        "updatedAt": m["updated_at"],
        "createdBy": m["created_by"],
        "updatedBy": m["updated_by"],
        "deletedAt": m["deleted_at"],
    }


class MilestoneController:
    @staticmethod
    def create(request: Request, project_id: int, data: MilestoneCreateRequest, db: Session) -> JSONResponse:
        current_user_id = getattr(request.state, "user_id", None)
        m = create_milestone(
            db,
            project_id=project_id,
            name=data.name,
            description=data.description,
            start_date=data.start_date,
            end_date=data.end_date,
            position=data.position,
            current_user_id=current_user_id,
        )
        db.commit()
        return BaseController.created(data=format_milestone_response(m.to_dict()))

    @staticmethod
    def list(request: Request, project_id: int, query: MilestoneListQuery, db: Session) -> JSONResponse:
        paged = list_milestones(
            db, project_id=project_id,
            page=query.offset, page_size=query.pageSize,
            include_deleted=query.includeDeleted,
        )
        items = [format_milestone_response(m.to_dict()) for m in paged.items]
        payload = {
            "_type": "Collection",
            "_links": {"self": {"href": f"/api/v3/projects/{project_id}/milestones?offset={paged.page}&pageSize={paged.page_size}"}},
            "total": paged.total,
            "count": len(items),
            "pageSize": paged.page_size,
            "offset": paged.page,
            "_embedded": {"elements": items},
        }
        return BaseController.ok(data=payload)

    @staticmethod
    def get(request: Request, milestone_id: int, db: Session) -> JSONResponse:
        m = get_milestone(db, milestone_id)
        return BaseController.ok(data=format_milestone_response(m.to_dict()))

    @staticmethod
    def update(request: Request, milestone_id: int, data: MilestoneUpdateRequest, db: Session) -> JSONResponse:
        current_user_id = getattr(request.state, "user_id", None)
        m = update_milestone(
            db,
            milestone_id=milestone_id,
            name=data.name,
            description=data.description,
            start_date=data.start_date,
            end_date=data.end_date,
            position=data.position,
            current_user_id=current_user_id,
        )
        return BaseController.ok(data=format_milestone_response(m.to_dict()))

    @staticmethod
    def delete(request: Request, milestone_id: int, db: Session) -> JSONResponse:
        current_user_id = getattr(request.state, "user_id", None)
        delete_milestone(db, milestone_id=milestone_id, current_user_id=current_user_id)
        return BaseController.no_content()

    @staticmethod
    def restore(request: Request, milestone_id: int, db: Session) -> JSONResponse:
        current_user_id = getattr(request.state, "user_id", None)
        m = restore_milestone(db, milestone_id=milestone_id, current_user_id=current_user_id)
        return BaseController.ok(data=format_milestone_response(m.to_dict()))
