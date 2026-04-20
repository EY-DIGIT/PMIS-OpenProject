"""Create an activity under a milestone. Handles nested resource."""
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.milestone import MilestoneModel
from .....infrastructure.db.repositories.activity_repository import ActivityRepository
from .....shared.date_rules import validate_entity_dates, validate_resource_dates
from .....domain.activities.activity import Activity, ACTIVITY_TYPE_RESOURCE
from .....domain.activities.activity_resource import ActivityResource


def create_activity(
    db: Session,
    *,
    milestone_id: int,
    name: str,
    description: Optional[str],
    type: str,
    start_date: datetime,
    end_date: datetime,
    actual_start_date: Optional[datetime],
    actual_end_date: Optional[datetime],
    position: Optional[int],
    resource: Optional[dict],
    current_user_id: Optional[int],
) -> Tuple[Activity, Optional[ActivityResource]]:
    milestone = (
        db.query(MilestoneModel)
        .filter(MilestoneModel.id == milestone_id)
        .filter(MilestoneModel.deleted_at.is_(None))
        .first()
    )
    if milestone is None:
        raise NotFoundError("The milestone could not be found.")
    assert_project_editable(db, milestone.project_id)

    project = db.query(ProjectModel).filter(ProjectModel.id == milestone.project_id).first()
    if project is None or project.start_date is None:
        raise ValidationError(
            "The project this activity belongs to could not be found or has no start date."
        )

    validate_entity_dates(
        entity_start=start_date,
        entity_end=end_date,
        actual_start=actual_start_date,
        actual_end=actual_end_date,
        parent_start_date=milestone.start_date,
        project_start_date=project.start_date,
        entity_label="activity",
        parent_label="milestone",
    )

    if type == ACTIVITY_TYPE_RESOURCE and resource is None:
        raise ValidationError(
            "Resource details are required when the activity type is 'Resource'."
        )
    if type != ACTIVITY_TYPE_RESOURCE and resource is not None:
        raise ValidationError(
            "Resource details should only be provided when the activity type is 'Resource'."
        )

    if resource is not None:
        validate_resource_dates(
            onboard=resource.get("onboard_date"),
            actual_onboard=resource.get("actual_onboard_date"),
            offboard=resource.get("offboard_date"),
            actual_offboard=resource.get("actual_offboard_date"),
            project_start_date=project.start_date,
        )

    repo = ActivityRepository(db)
    pos = position if position is not None else repo.next_position(milestone_id)

    activity = repo.create(
        project_id=milestone.project_id,
        milestone_id=milestone_id,
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
            activity_id=activity.id,
            project_id=milestone.project_id,
            data=resource,
        )

    db.commit()
    return activity, resource_domain
