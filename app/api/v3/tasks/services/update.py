"""Update a task. Full type × resource-mode transition matrix.

See activities/services/update.py for the canonical commentary -- the logic
here is structurally identical; only the parent entity and the resource
sub-entity differ.
"""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.activity import ActivityModel
from .....infrastructure.db.repositories.task_repository import TaskRepository
from .....shared.date_rules import validate_entity_dates, validate_resource_dates
from .....domain.tasks.task import (
    Task,
    TASK_TYPE_RESOURCE,
    RESOURCE_MODE_COUNT,
    RESOURCE_MODE_DETAILS,
)
from .....domain.tasks.task_resource import TaskResource


def update_task(
    db: Session,
    *,
    task_id: str,
    name: Optional[str],
    description: Optional[str],
    type: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    actual_start_date: Optional[datetime],
    actual_end_date: Optional[datetime],
    position: Optional[int],
    resource_mode: Optional[str],
    resource_count: Optional[int],
    resource: Optional[Dict[str, Any]],
    current_user_id: Optional[int],
) -> Tuple[Task, Optional[TaskResource]]:
    repo = TaskRepository(db)
    model = repo.get_model(task_id)
    if model is None:
        raise NotFoundError("The task could not be found.")

    assert_project_editable(db, model.project_id)

    parent = (
        db.query(ActivityModel)
        .filter(ActivityModel.id == model.activity_id)
        .filter(ActivityModel.deleted_at.is_(None))
        .first()
    )
    if parent is None:
        raise NotFoundError(
            "The activity this task belongs to could not be found. "
            "It may have been deleted."
        )
    project = db.query(ProjectModel).filter(ProjectModel.id == model.project_id).first()
    if project is None or project.start_date is None:
        raise ValidationError(
            "The project this task belongs to could not be found or has no start date."
        )

    new_start = start_date if start_date is not None else model.start_date
    new_end = end_date if end_date is not None else model.end_date
    new_actual_start = actual_start_date if actual_start_date is not None else model.actual_start_date
    new_actual_end = actual_end_date if actual_end_date is not None else model.actual_end_date

    validate_entity_dates(
        entity_start=new_start, entity_end=new_end,
        actual_start=new_actual_start, actual_end=new_actual_end,
        parent_start_date=parent.start_date,
        project_start_date=project.start_date,
        entity_label="task",
        parent_label="activity",
    )

    new_type = type if type is not None else model.type
    new_mode = resource_mode if resource_mode is not None else model.resource_mode
    new_count = resource_count if resource_count is not None else model.resource_count

    if new_type != TASK_TYPE_RESOURCE:
        if resource_mode is not None:
            raise ValidationError(
                "Resource mode should only be provided when the task type is 'resource'."
            )
        if resource_count is not None:
            raise ValidationError(
                "Resource count should only be provided when the task type is 'resource'."
            )
        if resource is not None:
            raise ValidationError(
                "Resource details should only be provided when the task type is 'resource'."
            )
        final_mode = None
        final_count = None
        target_has_resource_row = False
    else:
        if new_mode is None:
            raise ValidationError(
                "Please choose a resource mode ('count' or 'details') for a Resource-type task."
            )
        if new_mode == RESOURCE_MODE_COUNT:
            if new_count is None:
                raise ValidationError("Resource count is required when resource mode is 'count'.")
            if resource is not None:
                raise ValidationError("Resource details should be omitted when resource mode is 'count'.")
            final_mode = RESOURCE_MODE_COUNT
            final_count = new_count
            target_has_resource_row = False
        else:
            had_live_resource = repo.get_live_resource(task_id) is not None
            if not had_live_resource and resource is None:
                raise ValidationError(
                    "Please provide the resource details when using resource mode 'details'."
                )
            # Reject only if the CALLER explicitly sent resource_count.
            # A stale value inherited from prior 'count' mode is silently cleared.
            if resource_count is not None:
                raise ValidationError("Resource count should be omitted when resource mode is 'details'.")
            final_mode = RESOURCE_MODE_DETAILS
            final_count = None
            target_has_resource_row = True

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
    if final_mode != model.resource_mode or final_count != model.resource_count:
        updates["resource_mode"] = final_mode
        updates["resource_count"] = final_count

    if updates:
        repo.update(task_id, updates=updates, updated_by=current_user_id)

    resource_domain: Optional[TaskResource] = None
    if target_has_resource_row:
        if resource is not None:
            resource_domain = repo.upsert_resource(
                task_id=task_id, project_id=model.project_id, data=resource,
            )
        else:
            resource_domain = repo.get_live_resource(task_id)
    else:
        repo.soft_delete_live_resource(task_id)
        resource_domain = None

    db.commit()
    updated = repo.get_by_id(task_id)
    assert updated is not None
    return updated, resource_domain
