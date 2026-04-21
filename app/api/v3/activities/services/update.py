"""
Update an activity.

Handles the full type × resource-mode transition matrix in one place:

  Final state (after PATCH)                  Effect
  ─────────────────────────────────────────────────────────────────────────
  (type != resource)                          clear mode + count;
                                              soft-delete live resource row (if any)
  (type = resource, mode = count)             write count;
                                              soft-delete live resource row (if any)
  (type = resource, mode = details)           upsert the resource row from body;
                                              clear count

For a PATCH body, "final state" = existing columns overlaid with any fields
provided in the body. This lets the frontend send just the fields the user
changed.

All changes commit in a single transaction.
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
from .....domain.activities.activity import (
    Activity,
    ACTIVITY_TYPE_RESOURCE,
    RESOURCE_MODE_COUNT,
    RESOURCE_MODE_DETAILS,
)
from .....domain.activities.activity_resource import ActivityResource


# Sentinel: body field was not provided vs. body field was explicitly sent as None.
# We need to distinguish "don't touch this column" from "set to NULL".
_UNSET = object()


def update_activity(
    db: Session,
    *,
    activity_id: str,
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

    # Merge incoming partial values against current state for date checks.
    new_start = start_date if start_date is not None else model.start_date
    new_end = end_date if end_date is not None else model.end_date
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

    # Determine the FINAL (type, mode, count, has_resource_body) shape after
    # applying this partial update.
    new_type = type if type is not None else model.type
    # resource_mode follows the same "None = unchanged" semantic as type.
    new_mode = resource_mode if resource_mode is not None else model.resource_mode
    # resource_count follows the same pattern.
    new_count = resource_count if resource_count is not None else model.resource_count

    # Validate final shape based on new_type.
    if new_type != ACTIVITY_TYPE_RESOURCE:
        # Non-resource activity: mode and count will be cleared, resource row
        # soft-deleted. Reject body fields that wouldn't make sense.
        if resource_mode is not None:
            raise ValidationError(
                "Resource mode should only be provided when the activity type is 'resource'."
            )
        if resource_count is not None:
            raise ValidationError(
                "Resource count should only be provided when the activity type is 'resource'."
            )
        if resource is not None:
            raise ValidationError(
                "Resource details should only be provided when the activity type is 'resource'."
            )
        final_mode = None
        final_count = None
        target_has_resource_row = False
    else:
        # Resource activity -- we need a concrete final mode.
        if new_mode is None:
            raise ValidationError(
                "Please choose a resource mode ('count' or 'details') for a Resource-type activity."
            )
        if new_mode == RESOURCE_MODE_COUNT:
            if new_count is None:
                raise ValidationError(
                    "Resource count is required when resource mode is 'count'."
                )
            if resource is not None:
                raise ValidationError(
                    "Resource details should be omitted when resource mode is 'count'."
                )
            final_mode = RESOURCE_MODE_COUNT
            final_count = new_count
            target_has_resource_row = False
        else:  # details
            # Switching to (or staying in) details: body may provide a resource
            # block. If not provided, a live one must already exist.
            had_live_resource = repo.get_live_resource(activity_id) is not None
            if not had_live_resource and resource is None:
                raise ValidationError(
                    "Please provide the resource details when using resource mode 'details'."
                )
            # Reject only if the CALLER explicitly sent resource_count in the body.
            # A stale value inherited from prior 'count' mode is silently cleared.
            if resource_count is not None:
                raise ValidationError(
                    "Resource count should be omitted when resource mode is 'details'."
                )
            final_mode = RESOURCE_MODE_DETAILS
            final_count = None
            target_has_resource_row = True

    # Validate resource dates if a resource block was provided.
    if resource is not None:
        validate_resource_dates(
            onboard=resource.get("onboard_date"),
            actual_onboard=resource.get("actual_onboard_date"),
            offboard=resource.get("offboard_date"),
            actual_offboard=resource.get("actual_offboard_date"),
            project_start_date=project.start_date,
        )

    # Build the activity-row update dict.
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
    # Always write the resolved final_mode / final_count so transitions clean up.
    # These may flip values to/from NULL.
    if final_mode != model.resource_mode or final_count != model.resource_count:
        updates["resource_mode"] = final_mode
        updates["resource_count"] = final_count

    if updates:
        repo.update(activity_id, updates=updates, updated_by=current_user_id)

    # Reconcile the resource sub-entity.
    resource_domain: Optional[ActivityResource] = None
    if target_has_resource_row:
        # details mode: upsert if body provided; otherwise leave existing row.
        if resource is not None:
            resource_domain = repo.upsert_resource(
                activity_id=activity_id,
                project_id=model.project_id,
                data=resource,
            )
        else:
            resource_domain = repo.get_live_resource(activity_id)
    else:
        # count or non-resource: any live resource row must be soft-deleted.
        repo.soft_delete_live_resource(activity_id)
        resource_domain = None

    db.commit()
    updated = repo.get_by_id(activity_id)
    assert updated is not None
    return updated, resource_domain
