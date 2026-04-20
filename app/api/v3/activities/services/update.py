"""
Update an activity. Handles the four type-transition paths:

  current type  →  new type       action
  -----------------------------------------------
  resource      →  resource       update activity row; upsert resource row from body
  resource      →  standard|txn   update activity row; soft-delete live resource row
  standard|txn  →  resource       update activity row; INSERT fresh resource row
  standard|txn  →  standard|txn   update activity row only

All in one transaction.
"""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.milestone import MilestoneModel
from .....infrastructure.db.repositories.activity_repository import ActivityRepository
from .....shared.date_rules import validate_entity_dates, validate_resource_dates
from .....domain.activities.activity import Activity, ACTIVITY_TYPE_RESOURCE
from .....domain.activities.activity_resource import ActivityResource


def update_activity(
    db: Session,
    *,
    activity_id: int,
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
) -> Tuple[Activity, Optional[ActivityResource]]:
    repo = ActivityRepository(db)
    model = repo.get_model(activity_id)
    if model is None:
        raise NotFoundError("The activity could not be found.")

    assert_project_editable(db, model.project_id)

    milestone = (
        db.query(MilestoneModel)
        .filter(MilestoneModel.id == model.milestone_id)
        .filter(MilestoneModel.deleted_at.is_(None))
        .first()
    )
    if milestone is None:
        raise NotFoundError(
            "The milestone this activity belongs to could not be found. "
            "It may have been deleted."
        )
    project = db.query(ProjectModel).filter(ProjectModel.id == model.project_id).first()
    if project is None or project.start_date is None:
        raise ValidationError(
            "The project this activity belongs to could not be found or has no start date."
        )

    # Merge incoming partial values against current state.
    new_start = start_date if start_date is not None else model.start_date
    new_end = end_date if end_date is not None else model.end_date
    # For the actual-* fields, None in the body means "don't change".
    # There is no separate "clear" semantic (update endpoints rarely need it;
    # can be added later if required).
    new_actual_start = actual_start_date if actual_start_date is not None else model.actual_start_date
    new_actual_end = actual_end_date if actual_end_date is not None else model.actual_end_date

    validate_entity_dates(
        entity_start=new_start,
        entity_end=new_end,
        actual_start=new_actual_start,
        actual_end=new_actual_end,
        parent_start_date=milestone.start_date,
        project_start_date=project.start_date,
        entity_label="activity",
        parent_label="milestone",
    )

    old_type = model.type
    new_type = type if type is not None else old_type

    # Validate resource block presence against the (post-update) type.
    if new_type == ACTIVITY_TYPE_RESOURCE:
        if old_type != ACTIVITY_TYPE_RESOURCE and (resource is None or not resource.get("resource_name")):
            raise ValidationError(
                "Please provide the resource details (including the resource name) "
                "when changing the activity type to 'Resource'."
            )
    else:
        if resource is not None:
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

    # Build the activity-row update dict (only fields that were provided).
    updates: Dict[str, Any] = {}
    if name is not None:
        updates["name"] = name.strip()
    if description is not None:
        updates["description"] = description
    if type is not None:
        updates["type"] = new_type
    if start_date is not None:
        updates["start_date"] = start_date
    if end_date is not None:
        updates["end_date"] = end_date
    if actual_start_date is not None:
        updates["actual_start_date"] = actual_start_date
    if actual_end_date is not None:
        updates["actual_end_date"] = actual_end_date
    if position is not None:
        updates["position"] = position

    # --- Apply the transitions ---
    if updates:
        repo.update(activity_id, updates=updates, updated_by=current_user_id)

    resource_domain: Optional[ActivityResource] = None

    if new_type == ACTIVITY_TYPE_RESOURCE:
        if resource is not None:
            # r→r (partial update) OR standard|txn→r (insert fresh).
            resource_domain = repo.upsert_resource(
                activity_id=activity_id,
                project_id=model.project_id,
                data=resource,
            )
        else:
            # r→r with no resource block -- just return the existing live row.
            resource_domain = repo.get_live_resource(activity_id)
    else:
        # new_type is NOT resource. If old_type was resource, soft-delete the row.
        if old_type == ACTIVITY_TYPE_RESOURCE:
            repo.soft_delete_live_resource(activity_id)
        resource_domain = None

    db.commit()
    updated = repo.get_by_id(activity_id)
    assert updated is not None
    return updated, resource_domain
