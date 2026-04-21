"""List activities under a milestone."""
from dataclasses import dataclass
from typing import List
from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....domain.activities.activity import Activity
from .....infrastructure.db.models.milestone import MilestoneModel
from .....infrastructure.db.repositories.activity_repository import ActivityRepository


@dataclass
class PagedActivities:
    items: List[Activity]
    total: int
    page: int
    page_size: int


def list_activities(
    db: Session, *, milestone_id: str, page: int, page_size: int, include_deleted: bool,
) -> PagedActivities:
    m = (
        db.query(MilestoneModel)
        .filter(MilestoneModel.id == milestone_id)
        .filter(MilestoneModel.deleted_at.is_(None))
        .first()
    )
    if m is None:
        raise NotFoundError("The milestone could not be found.")
    offset = max(page - 1, 0) * page_size
    items, total = ActivityRepository(db).list_by_milestone(
        milestone_id=milestone_id, offset=offset, limit=page_size,
        include_deleted=include_deleted,
    )
    return PagedActivities(items=items, total=total, page=page, page_size=page_size)
