"""
User creation service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....core.security import hash_password
from .....core.errors import ValidationError, AlreadyExistsError
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....domain.users.user import User
from .....shared.service_result import ServiceResult
from .....shared.utils import is_valid_email, is_valid_login, is_valid_password, normalize_email, normalize_login


def create_user(
    db: Session,
    login: str,
    email: str,
    password: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    admin: bool = False
) -> ServiceResult[User]:
    """
    Create a new user.

    Args:
        db: Database session
        login: User login
        email: User email
        password: Plain text password
        first_name: First name
        last_name: Last name
        admin: Admin flag

    Returns:
        ServiceResult with created user or error
    """
    # Normalize inputs
    login = normalize_login(login)
    email = normalize_email(email)

    # Validate login
    if not is_valid_login(login):
        return ServiceResult.fail(
            error="Invalid login format. Must be 3-50 alphanumeric characters, underscores, or hyphens.",
            error_type="validation_error"
        )

    # Validate email
    if not is_valid_email(email):
        return ServiceResult.fail(
            error="Invalid email format",
            error_type="validation_error"
        )

    # Validate password
    if not is_valid_password(password):
        return ServiceResult.fail(
            error="Password must be at least 8 characters long",
            error_type="validation_error"
        )

    # Check for existing user
    repository = UserRepository(db)

    if repository.exists_by_login(login):
        return ServiceResult.fail(
            error=f"User with login '{login}' already exists",
            error_type="already_exists"
        )

    if repository.exists_by_email(email):
        return ServiceResult.fail(
            error=f"User with email '{email}' already exists",
            error_type="already_exists"
        )

    # Hash password
    hashed_password = hash_password(password)

    # Create user
    try:
        user = repository.create(
            login=login,
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            admin=admin
        )

        return ServiceResult.ok(user)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to create user: {str(e)}",
            error_type="internal_error"
        )
