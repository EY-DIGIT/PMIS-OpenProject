"""List tasks under an activity."""
from dataclasses import dataclass
from typing import List
from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....domain.tasks.task import Task
from .....infrastructure.db.models.activity import ActivityModel
from .....infrastructure.db.repositories.task_repository import TaskRepository


@dataclass
class PagedTasks:
    items: List[Task]
    total: int
    page: int
    page_size: int


def list_tasks(
    db: Session, *, activity_id: str, page: int, page_size: int, include_deleted: bool,
) -> PagedTasks:
    a = (
        db.query(ActivityModel)
        .filter(ActivityModel.id == activity_id)
        .filter(ActivityModel.deleted_at.is_(None))
        .first()
    )
    if a is None:
        raise NotFoundError("The activity could not be found.")
    offset = max(page - 1, 0) * page_size
    items, total = TaskRepository(db).list_by_activity(
        activity_id=activity_id, offset=offset, limit=page_size,
        include_deleted=include_deleted,
    )
    return PagedTasks(items=items, total=total, page=page, page_size=page_size)
