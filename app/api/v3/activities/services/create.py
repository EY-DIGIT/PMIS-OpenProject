"""Create an activity under a milestone. Handles nested resource."""
from datetime import datetime
from typing import Any, List, Optional, Tuple

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....domain.activities.activity import (
    ACTIVITY_STATUS_CHOICES,
    ACTIVITY_STATUS_DEFAULT,
    ACTIVITY_TYPE_RESOURCE,
    ACTIVITY_TYPE_STANDARD,
    Activity,
    RESOURCE_MODE_COUNT,
    RESOURCE_MODE_DETAILS,
)
from .....domain.activities.activity_resource import ActivityResource
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.milestone import MilestoneModel
from .....infrastructure.db.repositories.activity_repository import ActivityRepository
from .....infrastructure.db.repositories.resource_type_repository import (
    ResourceTypeRepository,
)
from .....shared.date_rules import validate_entity_dates, validate_resource_dates


def create_activity(
    db: Session,
    *,
    milestone_id: str,
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
    resource: Optional[dict],
    current_user_id: Optional[int],
    status: Optional[str] = None,
    dependency: Optional[List[Any]] = None,
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

    # Resource block: validate the classification columns now that we know we
    # have a details-mode resource block.
    if resource is not None:
        validate_resource_dates(
            onboard=resource.get("onboard_date"),
            actual_onboard=resource.get("actual_onboard_date"),
            offboard=resource.get("offboard_date"),
            actual_offboard=resource.get("actual_offboard_date"),
            project_start_date=project.start_date,
        )
        # type_of_resource_id must exist + be active in the catalog.
        type_of_resource_id = resource.get("type_of_resource_id")
        if type_of_resource_id:
            rt_repo = ResourceTypeRepository(db)
            if not rt_repo.is_active(type_of_resource_id):
                raise ValidationError(
                    "The selected 'type of resource' could not be found or is inactive."
                )

    # Normalize: for non-resource activities, mode + count must be NULL.
    store_mode = resource_mode if type == ACTIVITY_TYPE_RESOURCE else None
    store_count = resource_count if (
        type == ACTIVITY_TYPE_RESOURCE and resource_mode == RESOURCE_MODE_COUNT
    ) else None

    # Standard-only fields: apply a safe default status, keep dependency verbatim.
    resolved_status: Optional[str] = None
    resolved_dependency: Optional[list] = None
    if type == ACTIVITY_TYPE_STANDARD:
        resolved_status = status or ACTIVITY_STATUS_DEFAULT
        if resolved_status not in ACTIVITY_STATUS_CHOICES:
            raise ValidationError(
                f"Activity status must be one of: {', '.join(ACTIVITY_STATUS_CHOICES)}."
            )
        resolved_dependency = dependency

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
        resource_mode=store_mode,
        resource_count=store_count,
        status=resolved_status,
        dependency=resolved_dependency,
    )

    resource_domain = None
    # Only create a resource row when we are in details mode.
    if type == ACTIVITY_TYPE_RESOURCE and resource_mode == RESOURCE_MODE_DETAILS:
        resource_domain = repo.insert_resource(
            activity_id=activity.id,
            project_id=milestone.project_id,
            data=resource,
        )

    db.commit()
    # Re-read so the returned domain model has the freshly-written mode/count.
    refreshed = repo.get_by_id(activity.id)
    return refreshed or activity, resource_domain
