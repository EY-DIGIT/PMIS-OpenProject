"""
User deletion service.
"""
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.service_result import ServiceResult


def delete_user(
    db: Session,
    user_id: int
) -> ServiceResult[bool]:
    """
    Delete user.

    Note: This is a hard delete. Consider implementing soft delete in production.

    Args:
        db: Database session
        user_id: User ID to delete

    Returns:
        ServiceResult with success status or error
    """
    repository = UserRepository(db)

    # Check user exists
    user = repository.get_by_id(user_id)
    if not user:
        return ServiceResult.fail(
            error=f"User with ID {user_id} not found",
            error_type="not_found"
        )

    # Delete user
    try:
        success = repository.delete(user_id)

        if not success:
            return ServiceResult.fail(
                error=f"Failed to delete user with ID {user_id}",
                error_type="internal_error"
            )

        return ServiceResult.ok(True)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to delete user: {str(e)}",
            error_type="internal_error"
        )
