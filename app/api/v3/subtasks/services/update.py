"""Update a subtask — same 4-path type-transition logic."""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.task import TaskModel
from .....infrastructure.db.repositories.subtask_repository import SubtaskRepository
from .....shared.date_rules import validate_entity_dates, validate_resource_dates
from .....domain.subtasks.subtask import Subtask, SUBTASK_TYPE_RESOURCE
from .....domain.subtasks.subtask_resource import SubtaskResource


def update_subtask(
    db: Session,
    *,
    subtask_id: int,
    name: Optional[str],
    description: Optional[str],
    type: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    actual_start_date: Optional[datetime],
    actual_end_date: Optional[datetime],
    position: Optional[int],
    resource: Optional[Dict[str, Any]],
    current_user_id: Optional[int],
) -> Tuple[Subtask, Optional[SubtaskResource]]:
    repo = SubtaskRepository(db)
    model = repo.get_model(subtask_id)
    if model is None:
        raise NotFoundError("The subtask could not be found.")

    assert_project_editable(db, model.project_id)

    parent = (
        db.query(TaskModel)
        .filter(TaskModel.id == model.task_id)
        .filter(TaskModel.deleted_at.is_(None))
        .first()
    )
    if parent is None:
        raise NotFoundError(
            "The task this subtask belongs to could not be found. "
            "It may have been deleted."
        )
    project = db.query(ProjectModel).filter(ProjectModel.id == model.project_id).first()
    if project is None or project.start_date is None:
        raise ValidationError(
            "The project this subtask belongs to could not be found or has no start date."
        )

    new_start = start_date if start_date is not None else model.start_date
    new_end = end_date if end_date is not None else model.end_date
    new_actual_start = actual_start_date if actual_start_date is not None else model.actual_start_date
    new_actual_end = actual_end_date if actual_end_date is not None else model.actual_end_date

    validate_entity_dates(
        entity_start=new_start, entity_end=new_end,
        actual_start=new_actual_start, actual_end=new_actual_end,
        parent_start_date=parent.start_date, project_start_date=project.start_date,
        entity_label="subtask",
        parent_label="task",
    )

    old_type = model.type
    new_type = type if type is not None else old_type

    if new_type == SUBTASK_TYPE_RESOURCE:
        if old_type != SUBTASK_TYPE_RESOURCE and (resource is None or not resource.get("resource_name")):
            raise ValidationError(
                "Please provide the resource details (including the resource name) "
                "when changing the subtask type to 'Resource'."
            )
    else:
        if resource is not None:
            raise ValidationError(
                "Resource details should only be provided when the subtask type is 'Resource'."
            )

    if resource is not None:
        validate_resource_dates(
            onboard=resource.get("onboard_date"),
            actual_onboard=resource.get("actual_onboard_date"),
            offboard=resource.get("offboard_date"),
            actual_offboard=resource.get("actual_offboard_date"),
            project_start_date=project.start_date,
        )

    updates: Dict[str, Any] = {}
    if name is not None: updates["name"] = name.strip()
    if description is not None: updates["description"] = description
    if type is not None: updates["type"] = new_type
    if start_date is not None: updates["start_date"] = start_date
    if end_date is not None: updates["end_date"] = end_date
    if actual_start_date is not None: updates["actual_start_date"] = actual_start_date
    if actual_end_date is not None: updates["actual_end_date"] = actual_end_date
    if position is not None: updates["position"] = position
    if updates:
        repo.update(subtask_id, updates=updates, updated_by=current_user_id)

    resource_domain: Optional[SubtaskResource] = None
    if new_type == SUBTASK_TYPE_RESOURCE:
        if resource is not None:
            resource_domain = repo.upsert_resource(
                subtask_id=subtask_id, project_id=model.project_id, data=resource,
            )
        else:
            resource_domain = repo.get_live_resource(subtask_id)
    else:
        if old_type == SUBTASK_TYPE_RESOURCE:
            repo.soft_delete_live_resource(subtask_id)

    db.commit()
    updated = repo.get_by_id(subtask_id)
    assert updated is not None
    return updated, resource_domain
