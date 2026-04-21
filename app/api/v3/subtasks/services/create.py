"""Create a subtask under a task."""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.task import TaskModel
from .....infrastructure.db.repositories.subtask_repository import SubtaskRepository
from .....shared.date_rules import validate_entity_dates, validate_resource_dates
from .....domain.subtasks.subtask import (
    Subtask,
    SUBTASK_TYPE_RESOURCE,
    RESOURCE_MODE_COUNT,
    RESOURCE_MODE_DETAILS,
)
from .....domain.subtasks.subtask_resource import SubtaskResource


def create_subtask(
    db: Session,
    *,
    task_id: str,
    name: str,
    description: Optional[str],
    type: str,
    start_date: datetime,
    end_date: datetime,
    actual_start_date: Optional[datetime],
    actual_end_date: Optional[datetime],
    position: Optional[int],
    resource_mode: Optional[str],
    resource_count: Optional[int],
    resource: Optional[Dict[str, Any]],
    current_user_id: Optional[int],
) -> Tuple[Subtask, Optional[SubtaskResource]]:
    task = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id)
        .filter(TaskModel.deleted_at.is_(None))
        .first()
    )
    if task is None:
        raise NotFoundError("The task could not be found.")
    assert_project_editable(db, task.project_id)

    project = db.query(ProjectModel).filter(ProjectModel.id == task.project_id).first()
    if project is None or project.start_date is None:
        raise ValidationError(
            "The project this subtask belongs to could not be found or has no start date."
        )

    validate_entity_dates(
        entity_start=start_date, entity_end=end_date,
        actual_start=actual_start_date, actual_end=actual_end_date,
        parent_start_date=task.start_date,
        project_start_date=project.start_date,
        entity_label="subtask",
        parent_label="task",
    )

    if resource is not None:
        validate_resource_dates(
            onboard=resource.get("onboard_date"),
            actual_onboard=resource.get("actual_onboard_date"),
            offboard=resource.get("offboard_date"),
            actual_offboard=resource.get("actual_offboard_date"),
            project_start_date=project.start_date,
        )

    repo = SubtaskRepository(db)
    pos = position if position is not None else repo.next_position(task_id)

    store_mode = resource_mode if type == SUBTASK_TYPE_RESOURCE else None
    store_count = resource_count if (
        type == SUBTASK_TYPE_RESOURCE and resource_mode == RESOURCE_MODE_COUNT
    ) else None

    subtask = repo.create(
        project_id=task.project_id,
        task_id=task_id,
        name=name.strip(),
        description=description,
        type=type,
        start_date=start_date, end_date=end_date,
        actual_start_date=actual_start_date, actual_end_date=actual_end_date,
        position=pos,
        created_by=current_user_id,
        resource_mode=store_mode,
        resource_count=store_count,
    )
    resource_domain = None
    if type == SUBTASK_TYPE_RESOURCE and resource_mode == RESOURCE_MODE_DETAILS:
        resource_domain = repo.insert_resource(
            subtask_id=subtask.id, project_id=task.project_id, data=resource,
        )
    db.commit()
    refreshed = repo.get_by_id(subtask.id)
    return refreshed or subtask, resource_domain
