"""Create a task under an activity."""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.activity import ActivityModel
from .....infrastructure.db.repositories.task_repository import TaskRepository
from .....shared.date_rules import validate_entity_dates, validate_resource_dates
from .....domain.tasks.task import Task, TASK_TYPE_RESOURCE
from .....domain.tasks.task_resource import TaskResource


def create_task(
    db: Session,
    *,
    activity_id: int,
    name: str,
    description: Optional[str],
    type: str,
    start_date: datetime,
    end_date: datetime,
    actual_start_date: Optional[datetime],
    actual_end_date: Optional[datetime],
    position: Optional[int],
    resource: Optional[Dict[str, Any]],
    current_user_id: Optional[int],
) -> Tuple[Task, Optional[TaskResource]]:
    activity = (
        db.query(ActivityModel)
        .filter(ActivityModel.id == activity_id)
        .filter(ActivityModel.deleted_at.is_(None))
        .first()
    )
    if activity is None:
        raise NotFoundError("The activity could not be found.")
    assert_project_editable(db, activity.project_id)

    project = db.query(ProjectModel).filter(ProjectModel.id == activity.project_id).first()
    if project is None or project.start_date is None:
        raise ValidationError(
            "The project this task belongs to could not be found or has no start date."
        )

    validate_entity_dates(
        entity_start=start_date,
        entity_end=end_date,
        actual_start=actual_start_date,
        actual_end=actual_end_date,
        parent_start_date=activity.start_date,
        project_start_date=project.start_date,
        entity_label="task",
        parent_label="activity",
    )

    if type == TASK_TYPE_RESOURCE and resource is None:
        raise ValidationError(
            "Resource details are required when the task type is 'Resource'."
        )
    if type != TASK_TYPE_RESOURCE and resource is not None:
        raise ValidationError(
            "Resource details should only be provided when the task type is 'Resource'."
        )

    if resource is not None:
        validate_resource_dates(
            onboard=resource.get("onboard_date"),
            actual_onboard=resource.get("actual_onboard_date"),
            offboard=resource.get("offboard_date"),
            actual_offboard=resource.get("actual_offboard_date"),
            project_start_date=project.start_date,
        )

    repo = TaskRepository(db)
    pos = position if position is not None else repo.next_position(activity_id)

    task = repo.create(
        project_id=activity.project_id,
        activity_id=activity_id,
        name=name.strip(),
        description=description,
        type=type,
        start_date=start_date,
        end_date=end_date,
        actual_start_date=actual_start_date,
        actual_end_date=actual_end_date,
        position=pos,
        created_by=current_user_id,
    )
    resource_domain = None
    if resource is not None:
        resource_domain = repo.insert_resource(
            task_id=task.id, project_id=activity.project_id, data=resource,
        )
    db.commit()
    return task, resource_domain
