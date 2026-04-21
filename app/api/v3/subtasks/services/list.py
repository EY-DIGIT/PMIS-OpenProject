"""List subtasks under a task."""
from dataclasses import dataclass
from typing import List
from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....domain.subtasks.subtask import Subtask
from .....infrastructure.db.models.task import TaskModel
from .....infrastructure.db.repositories.subtask_repository import SubtaskRepository


@dataclass
class PagedSubtasks:
    items: List[Subtask]
    total: int
    page: int
    page_size: int


def list_subtasks(
    db: Session, *, task_id: str, page: int, page_size: int, include_deleted: bool,
) -> PagedSubtasks:
    t = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id)
        .filter(TaskModel.deleted_at.is_(None))
        .first()
    )
    if t is None:
        raise NotFoundError("The task could not be found.")
    offset = max(page - 1, 0) * page_size
    items, total = SubtaskRepository(db).list_by_task(
        task_id=task_id, offset=offset, limit=page_size, include_deleted=include_deleted,
    )
    return PagedSubtasks(items=items, total=total, page=page, page_size=page_size)
