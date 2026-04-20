"""Soft-delete an activity (cascades to tasks/subtasks + all resources)."""
from typing import Optional
from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....core.project_lock import assert_project_editable
from .....infrastructure.db.repositories.activity_repository import ActivityRepository


def delete_activity(db: Session, *, activity_id: int, current_user_id: Optional[int]) -> None:
    repo = ActivityRepository(db)
    model = repo.get_model(activity_id)
    if model is None:
        raise NotFoundError("The activity could not be found.")
    assert_project_editable(db, model.project_id)
    repo.soft_delete_with_cascade(activity_id, deleted_by=current_user_id)
