"""Soft-delete a milestone (cascades down)."""
from typing import Optional
from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.repositories.milestone_repository import MilestoneRepository


def delete_milestone(db: Session, *, milestone_id: str, current_user_id: Optional[int]) -> None:
    repo = MilestoneRepository(db)
    model = repo.get_model(milestone_id)
    if model is None:
        raise NotFoundError("The milestone could not be found.")
    assert_project_editable(db, model.project_id)
    repo.soft_delete_with_cascade(milestone_id, deleted_by=current_user_id)
