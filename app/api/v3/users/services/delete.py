"""
User soft-delete service.

Sets ``deleted_at``, ``deleted_by``, and ``status='inactive'``. The
project_members mapping rows are intentionally NOT removed — undelete
(via PATCH status='active') restores the user with their full mapping
history. Closed/completed projects are filtered out at response time.
"""
from typing import Optional

from sqlalchemy.orm import Session

from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.service_result import ServiceResult


def delete_user(
    db: Session,
    user_id: int,
    *,
    actor_id: Optional[int] = None,
) -> ServiceResult[bool]:
    """Soft-delete a user. Idempotent on already-deleted rows."""
    repository = UserRepository(db)

    # Use include_deleted so re-deleting a soft-deleted row reports
    # "already deleted" rather than 404.
    user = repository.get_by_id(user_id, include_deleted=True)
    if not user:
        return ServiceResult.fail(
            error=f"User with ID {user_id} not found",
            error_type="not_found",
        )

    try:
        ok = repository.soft_delete(user_id, actor_id=actor_id)
        if not ok:
            return ServiceResult.fail(
                error=f"Failed to delete user with ID {user_id}",
                error_type="internal_error",
            )
        db.commit()
        return ServiceResult.ok(True)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        return ServiceResult.fail(
            error=f"Failed to delete user: {e}",
            error_type="internal_error",
        )
