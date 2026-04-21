"""Update a milestone (partial; with date re-validation)."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.repositories.milestone_repository import MilestoneRepository
from .....shared.date_rules import validate_entity_dates
from .....domain.milestones.milestone import Milestone


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

    if not updates:
        return repo._to_domain(model)

    updated = repo.update(milestone_id, updates=updates, updated_by=current_user_id)
    db.commit()
    return updated
