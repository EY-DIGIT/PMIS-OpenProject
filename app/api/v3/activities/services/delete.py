"""Soft-delete an activity (cascades to tasks/subtasks + all resources)."""
from typing import Optional
from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....core.project_lock import assert_milestone_activity_writable
from .....infrastructure.db.repositories.activity_repository import ActivityRepository
from ...projects.services.audit import record_audit
from ...projects.services.baseline_version_sync import (
    ACTION_ACTIVITY_DELETE,
    propagate_activity_soft_delete,
)


def delete_activity(db: Session, *, activity_id: str, current_user_id: Optional[int]) -> None:
    repo = ActivityRepository(db)
    model = repo.get_model(activity_id)
    if model is None:
        raise NotFoundError("The activity could not be found.")
    assert_milestone_activity_writable(db, model.project_id)

    before = {
        "activity_id": activity_id,
        "name": model.name,
        "milestone_id": model.milestone_id,
        "project_id": model.project_id,
    }
    repo.soft_delete_with_cascade(activity_id, deleted_by=current_user_id)
    record_audit(
        db,
        project_id=model.project_id,
        actor_id=current_user_id,
        action=ACTION_ACTIVITY_DELETE,
        before=before,
        after=None,
    )
    db.commit()
    propagate_activity_soft_delete(
        db, baseline_activity_id=activity_id, actor_id=current_user_id,
    )
