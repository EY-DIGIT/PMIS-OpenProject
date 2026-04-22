"""Soft-delete a milestone (cascades down)."""
from typing import Optional
from sqlalchemy.orm import Session

from .....core.errors import NotFoundError
from .....core.project_lock import assert_milestone_activity_writable
from .....infrastructure.db.repositories.milestone_repository import MilestoneRepository
from ...projects.services.audit import record_audit
from ...projects.services.baseline_version_sync import (
    ACTION_MILESTONE_DELETE,
    propagate_milestone_soft_delete,
)


def delete_milestone(db: Session, *, milestone_id: str, current_user_id: Optional[int]) -> None:
    repo = MilestoneRepository(db)
    model = repo.get_model(milestone_id)
    if model is None:
        raise NotFoundError("The milestone could not be found.")
    assert_milestone_activity_writable(db, model.project_id)

    before = {
        "milestone_id": milestone_id,
        "name": model.name,
        "project_id": model.project_id,
    }
    repo.soft_delete_with_cascade(milestone_id, deleted_by=current_user_id)
    record_audit(
        db,
        project_id=model.project_id,
        actor_id=current_user_id,
        action=ACTION_MILESTONE_DELETE,
        before=before,
        after=None,
    )
    db.commit()
    propagate_milestone_soft_delete(
        db, baseline_milestone_id=milestone_id, actor_id=current_user_id,
    )
