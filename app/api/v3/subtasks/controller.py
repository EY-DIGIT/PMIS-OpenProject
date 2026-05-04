"""Subtasks controller."""
from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....core.base_controller import BaseController
from ....shared.labels import (
    KIND_SUBTASK,
    LabelIndex,
    build_label_index_for_project,
)
from .schemas import SubtaskCreateRequest, SubtaskUpdateRequest, SubtaskListQuery
from .services import (
    create_subtask, get_subtask_with_resource, list_subtasks,
    update_subtask, delete_subtask, restore_subtask,
)


def _format_resource(r: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if r is None:
        return None
    return {
        "_type": "SubtaskResource",
        "id": r["id"],
        "resourceName": r["resource_name"],
        "onboardDate": r["onboard_date"],
        "actualOnboardDate": r["actual_onboard_date"],
        "offboardDate": r["offboard_date"],
        "actualOffboardDate": r["actual_offboard_date"],
        "position": r["position"],
        "designation": r["designation"],
        "jobRole": r["job_role"],
        "qualification": r["qualification"],
        "experienceYears": r["experience_years"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }


def format_subtask_response(
    s: Dict[str, Any],
    resource: Optional[Dict[str, Any]] = None,
    label_index: Optional[LabelIndex] = None,
    base_url: str = "/api/v3",
) -> Dict[str, Any]:
    deps = s.get("depends_on") or []
    display_code = (
        label_index.label_of(KIND_SUBTASK, s["id"]) if label_index else None
    )
    deps_display = (
        label_index.labels_of(KIND_SUBTASK, deps) if label_index else []
    )
    return {
        "_type": "Subtask",
        "_links": {
            "self": {"href": f"{base_url}/subtasks/{s['id']}", "title": s["name"]},
            "task": {"href": f"{base_url}/tasks/{s['task_id']}"},
            "project": {"href": f"{base_url}/projects/{s['project_id']}"},
        },
        "id": s["id"],
        "displayCode": display_code,
        "projectId": s["project_id"],
        "taskId": s["task_id"],
        "parentSubtaskId": s.get("parent_subtask_id"),
        "name": s["name"],
        "description": s["description"],
        "type": s["type"],
        "startDate": s["start_date"],
        "endDate": s["end_date"],
        "actualStartDate": s["actual_start_date"],
        "actualEndDate": s["actual_end_date"],
        "position": s["position"],
        "resourceMode": s.get("resource_mode"),
        "resourceCount": s.get("resource_count"),
        "dependsOn": deps,
        "dependsOnDisplay": deps_display,
        "createdAt": s["created_at"],
        "updatedAt": s["updated_at"],
        "createdBy": s["created_by"],
        "updatedBy": s["updated_by"],
        "deletedAt": s["deleted_at"],
        "resource": _format_resource(resource),
    }


class SubtaskController:
    @staticmethod
    def create(request: Request, task_id: str, data: SubtaskCreateRequest, db: Session) -> JSONResponse:
        cuid = getattr(request.state, "user_id", None)
        rd = data.resource.model_dump() if data.resource else None
        s, r = create_subtask(
            db,
            task_id=task_id,
            # ``type`` is no longer in the request body; service derives it
            # from the parent task. Cross-type mapping reserved for future.
            name=data.name, description=data.description,
            start_date=data.start_date, end_date=data.end_date,
            actual_start_date=data.actual_start_date, actual_end_date=data.actual_end_date,
            position=data.position,
            resource_mode=data.resource_mode, resource_count=data.resource_count,
            resource=rd, current_user_id=cuid,
            depends_on=data.depends_on,
        )
        idx = build_label_index_for_project(db, s.project_id)
        return BaseController.created(data=format_subtask_response(
            s.to_dict(), r.to_dict() if r else None, label_index=idx,
        ))

    @staticmethod
    def create_nested(
        request: Request,
        parent_subtask_id: str,
        data: SubtaskCreateRequest,
        db: Session,
    ) -> JSONResponse:
        """Doc 24: create a subtask nested under another subtask.

        Same body as the task-scoped create. The service infers the root
        ``task_id`` from the parent subtask and writes
        ``parent_subtask_id`` so the new row sits as the parent's child.
        """
        cuid = getattr(request.state, "user_id", None)
        rd = data.resource.model_dump() if data.resource else None
        s, r = create_subtask(
            db,
            parent_subtask_id=parent_subtask_id,
            name=data.name, description=data.description,
            start_date=data.start_date, end_date=data.end_date,
            actual_start_date=data.actual_start_date,
            actual_end_date=data.actual_end_date,
            position=data.position,
            resource_mode=data.resource_mode,
            resource_count=data.resource_count,
            resource=rd, current_user_id=cuid,
            depends_on=data.depends_on,
        )
        idx = build_label_index_for_project(db, s.project_id)
        return BaseController.created(data=format_subtask_response(
            s.to_dict(), r.to_dict() if r else None, label_index=idx,
        ))

    @staticmethod
    def list(request: Request, task_id: str, query: SubtaskListQuery, db: Session) -> JSONResponse:
        paged = list_subtasks(db, task_id=task_id, page=query.offset, page_size=query.pageSize, include_deleted=query.includeDeleted)
        items_data = list(paged.items)
        idx = (
            build_label_index_for_project(db, items_data[0].project_id)
            if items_data else None
        )
        items = [format_subtask_response(s.to_dict(), None, label_index=idx) for s in items_data]
        payload = {
            "_type": "Collection",
            "_links": {"self": {"href": f"/api/v3/tasks/{task_id}/subtasks?offset={paged.page}&pageSize={paged.page_size}"}},
            "total": paged.total, "count": len(items),
            "pageSize": paged.page_size, "offset": paged.page,
            "_embedded": {"elements": items},
        }
        return BaseController.ok(data=payload)

    @staticmethod
    def get(request: Request, subtask_id: str, db: Session) -> JSONResponse:
        s, r = get_subtask_with_resource(db, subtask_id)
        idx = build_label_index_for_project(db, s.project_id)
        return BaseController.ok(data=format_subtask_response(
            s.to_dict(), r.to_dict() if r else None, label_index=idx,
        ))

    @staticmethod
    def update(request: Request, subtask_id: str, data: SubtaskUpdateRequest, db: Session) -> JSONResponse:
        cuid = getattr(request.state, "user_id", None)
        rd = data.resource.model_dump() if data.resource else None
        s, r = update_subtask(
            db,
            subtask_id=subtask_id,
            name=data.name, description=data.description, type=data.type,
            start_date=data.start_date, end_date=data.end_date,
            actual_start_date=data.actual_start_date, actual_end_date=data.actual_end_date,
            position=data.position,
            resource_mode=data.resource_mode, resource_count=data.resource_count,
            resource=rd, current_user_id=cuid,
            depends_on=data.depends_on,
        )
        idx = build_label_index_for_project(db, s.project_id)
        return BaseController.ok(data=format_subtask_response(
            s.to_dict(), r.to_dict() if r else None, label_index=idx,
        ))

    @staticmethod
    def delete(request: Request, subtask_id: str, db: Session) -> JSONResponse:
        cuid = getattr(request.state, "user_id", None)
        delete_subtask(db, subtask_id=subtask_id, current_user_id=cuid)
        return BaseController.no_content()

    @staticmethod
    def restore(request: Request, subtask_id: str, db: Session) -> JSONResponse:
        cuid = getattr(request.state, "user_id", None)
        s = restore_subtask(db, subtask_id=subtask_id, current_user_id=cuid)
        idx = build_label_index_for_project(db, s.project_id)
        return BaseController.ok(data=format_subtask_response(
            s.to_dict(), label_index=idx,
        ))
