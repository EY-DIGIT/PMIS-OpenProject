"""Update a milestone (partial; with date re-validation)."""
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....domain.milestones.milestone import (
    MILESTONE_STATUS_CHOICES,
    Milestone,
)
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.repositories.milestone_repository import MilestoneRepository
from .....infrastructure.db.repositories.vendor_repository import VendorRepository
from .....shared.date_rules import validate_entity_dates


def update_milestone(
    db: Session,
    *,
    milestone_id: str,
    name: Optional[str],
    description: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    position: Optional[int],
    current_user_id: Optional[int],
    status: Optional[str] = None,
    depends: Optional[List[Any]] = None,
    vendor_ids: Optional[List[str]] = None,
) -> Milestone:
    repo = MilestoneRepository(db)
    model = repo.get_model(milestone_id)
    if model is None:
        raise NotFoundError("The milestone could not be found.")

    # Lock check against the owning project.
    assert_project_editable(db, model.project_id)

    project = db.query(ProjectModel).filter(ProjectModel.id == model.project_id).first()
    if project is None or project.start_date is None:
        raise NotFoundError(
            "The project this milestone belongs to could not be found or has no start date."
        )

    # Merge incoming against current for consistent cross-field checks.
    new_start = start_date if start_date is not None else model.start_date
    new_end = end_date if end_date is not None else model.end_date

    validate_entity_dates(
        entity_start=new_start,
        entity_end=new_end,
        actual_start=None,
        actual_end=None,
        parent_start_date=project.start_date,
        project_start_date=project.start_date,
        entity_label="milestone",
        parent_label="project",
    )

    if status is not None and status not in MILESTONE_STATUS_CHOICES:
        raise ValidationError(
            f"Milestone status must be one of: {', '.join(MILESTONE_STATUS_CHOICES)}."
        )

    updates = {}
    if name is not None:
        updates["name"] = name.strip()
    if description is not None:
        updates["description"] = description
    if start_date is not None:
        updates["start_date"] = start_date
    if end_date is not None:
        updates["end_date"] = end_date
    if position is not None:
        updates["position"] = position
    if status is not None:
        updates["status"] = status
    if depends is not None:
        updates["depends"] = depends

    # Vendor replacement is independent of column-level updates — it goes
    # through the association table.
    vendor_repo = VendorRepository(db)
    will_replace_vendors = vendor_ids is not None
    resolved_vendor_ids: List[str] = []
    if will_replace_vendors:
        unique = list(dict.fromkeys(vendor_ids or []))
        if unique:
            active = set(vendor_repo.existing_active_ids(unique))
            missing_active = [v for v in unique if v not in active]
            if missing_active:
                raise ValidationError(
                    f"Unknown or inactive vendor(s): {', '.join(missing_active)}"
                )
            project_vendor_ids = set(vendor_repo.project_vendor_ids(model.project_id))
            not_on_project = [v for v in unique if v not in project_vendor_ids]
            if not_on_project:
                raise ValidationError(
                    f"Vendor(s) not attached to this project: {', '.join(not_on_project)}. "
                    "Add them to the project first."
                )
        resolved_vendor_ids = unique

    if not updates and not will_replace_vendors:
        return repo._to_domain(model)

    if updates:
        updated = repo.update(milestone_id, updates=updates, updated_by=current_user_id)
    else:
        # No column changes requested — we still want to refresh the domain
        # object so the returned vendor list is correct.
        updated = repo._to_domain(model)

    if will_replace_vendors:
        vendor_repo.set_milestone_vendors(milestone_id, resolved_vendor_ids)
        db.commit()
        updated.vendors = vendor_repo.list_milestone_vendors(milestone_id)

    return updated
