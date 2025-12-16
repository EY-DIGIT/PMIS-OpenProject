"""
User update service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....core.security import hash_password
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....domain.users.user import User
from .....shared.service_result import ServiceResult
from .....shared.utils import is_valid_email, is_valid_password, normalize_email


def update_user(
    db: Session,
    user_id: int,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    admin: Optional[bool] = None,
    status: Optional[str] = None,
    requesting_user_id: Optional[int] = None,
    is_admin: bool = False
) -> ServiceResult[User]:
    """
    Update user.

    Args:
        db: Database session
        user_id: User ID to update
        email: New email
        first_name: New first name
        last_name: New last name
        admin: New admin flag
        status: New status
        requesting_user_id: ID of user making the request
        is_admin: Whether requesting user is admin

    Returns:
        ServiceResult with updated user or error
    """
    repository = UserRepository(db)

    # Check user exists
    user = repository.get_by_id(user_id)
    if not user:
        return ServiceResult.fail(
            error=f"User with ID {user_id} not found",
            error_type="not_found"
        )

    # Authorization checks
    is_self = requesting_user_id == user_id

    # Only admin can update admin flag
    if admin is not None and not is_admin:
        return ServiceResult.fail(
            error="Only admin users can modify admin flag",
            error_type="authorization_error"
        )

    # Only admin can update status
    if status is not None and not is_admin:
        return ServiceResult.fail(
            error="Only admin users can modify user status",
            error_type="authorization_error"
        )

    # Non-admin users can only update their own profile
    if not is_admin and not is_self:
        return ServiceResult.fail(
            error="You can only update your own profile",
            error_type="authorization_error"
        )

    # Validate email if provided
    if email is not None:
        email = normalize_email(email)
        if not is_valid_email(email):
            return ServiceResult.fail(
                error="Invalid email format",
                error_type="validation_error"
            )

        # Check if email already exists for another user
        existing_user = repository.get_by_email(email)
        if existing_user and existing_user.id != user_id:
            return ServiceResult.fail(
                error=f"Email '{email}' is already in use",
                error_type="already_exists"
            )

    # Validate status if provided
    if status is not None and status not in ["active", "locked", "registered"]:
        return ServiceResult.fail(
            error="Invalid status. Must be: active, locked, or registered",
            error_type="validation_error"
        )

    # Update user
    try:
        updated_user = repository.update(
            user_id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            admin=admin,
            status=status
        )

        if not updated_user:
            return ServiceResult.fail(
                error=f"Failed to update user with ID {user_id}",
                error_type="internal_error"
            )

        return ServiceResult.ok(updated_user)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to update user: {str(e)}",
            error_type="internal_error"
        )


def update_password(
    db: Session,
    user_id: int,
    new_password: str,
    requesting_user_id: Optional[int] = None,
    is_admin: bool = False
) -> ServiceResult[bool]:
    """
    Update user password.

    Args:
        db: Database session
        user_id: User ID to update
        new_password: New plain text password
        requesting_user_id: ID of user making the request
        is_admin: Whether requesting user is admin

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

    # Authorization check
    is_self = requesting_user_id == user_id
    if not is_admin and not is_self:
        return ServiceResult.fail(
            error="You can only update your own password",
            error_type="authorization_error"
        )

    # Validate password
    if not is_valid_password(new_password):
        return ServiceResult.fail(
            error="Password must be at least 8 characters long",
            error_type="validation_error"
        )

    # Hash and update password
    try:
        hashed_password = hash_password(new_password)
        success = repository.update_password(user_id, hashed_password)

        if not success:
            return ServiceResult.fail(
                error=f"Failed to update password for user with ID {user_id}",
                error_type="internal_error"
            )

        return ServiceResult.ok(True)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to update password: {str(e)}",
            error_type="internal_error"
        )
