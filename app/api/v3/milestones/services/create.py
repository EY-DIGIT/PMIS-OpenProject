"""Create a milestone under a project."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.repositories.milestone_repository import MilestoneRepository
from .....shared.date_rules import validate_entity_dates
from .....domain.milestones.milestone import Milestone


def create_milestone(
    db: Session,
    *,
    project_id: str,
    name: str,
    description: Optional[str],
    start_date: datetime,
    end_date: datetime,
    position: Optional[int],
    current_user_id: Optional[int],
) -> Milestone:
    """
    Create a milestone under the given project.

    Validation:
      - Project must exist, not deleted, not a published baseline.
      - Project must have a start_date set (we need it for date rules).
      - start_date >= project.start_date; end_date >= start_date.
    """
    assert_project_editable(db, project_id)

    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if project is None:
        raise NotFoundError("The project could not be found.")
    if project.start_date is None:
        from .....core.errors import ValidationError
        raise ValidationError(
            "The project does not have a start date yet. "
            "Please set the project start date before adding milestones."
        )

    # Parent of a milestone is the project itself.
    validate_entity_dates(
        entity_start=start_date,
        entity_end=end_date,
        actual_start=None,
        actual_end=None,
        parent_start_date=project.start_date,
        project_start_date=project.start_date,
        entity_label="milestone",
        parent_label="project",
    )

    repo = MilestoneRepository(db)
    if position is None:
        position = repo.next_position(project_id)

    return repo.create(
        project_id=project_id,
        name=name.strip(),
        description=description,
        start_date=start_date,
        end_date=end_date,
        position=position,
        created_by=current_user_id,
    )
