"""Soft-delete a task (cascades to subtasks + resources)."""
from typing import Optional
from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....core.project_lock import assert_task_subtask_writable
from .....infrastructure.db.repositories.task_repository import TaskRepository


def delete_task(db: Session, *, task_id: str, current_user_id: Optional[int]) -> None:
    repo = TaskRepository(db)
    model = repo.get_model(task_id)
    if model is None:
        raise NotFoundError("The task could not be found.")
    assert_task_subtask_writable(db, model.project_id)
    repo.soft_delete_with_cascade(task_id, deleted_by=current_user_id)
