"""
User authentication service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....core.security import verify_password, create_access_token, create_refresh_token
from .....core.config import settings
from .....core.rbac import Role
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.service_result import ServiceResult


def authenticate_user(
    db: Session,
    login: str,
    password: str
) -> ServiceResult[dict]:
    """
    Authenticate user and generate JWT token.

    Args:
        db: Database session
        login: User login
        password: Plain text password

    Returns:
        ServiceResult with token data or error
    """
    repository = UserRepository(db)

    # Get user
    user = repository.get_by_login(login)
    if not user:
        return ServiceResult.fail(
            error="Invalid credentials",
            error_type="invalid_credentials"
        )

    # Check if user is active
    if user.status != "active":
        return ServiceResult.fail(
            error="User account is not active",
            error_type="authentication_error"
        )

    # Verify password
    password_hash = repository.get_password_hash_by_login(login)
    if not password_hash or not verify_password(password, password_hash):
        return ServiceResult.fail(
            error="Invalid credentials",
            error_type="invalid_credentials"
        )

    # Determine user role
    if user.admin:
        role = Role.ADMIN
    else:
        role = Role.MEMBER

    # Create JWT token
    token_data = {
        "sub": user.login,
        "user_id": user.id,
        "email": user.email,
        "role": role.value,
        "is_admin": user.admin
    }

    access_token = create_access_token(token_data)
    # Create refresh token and persist its jti and expiry for rotation
    refresh_token, refresh_jti, refresh_expires = create_refresh_token({
        "sub": user.login,
        "user_id": user.id,
        "email": user.email,
        "role": role.value,
        "is_admin": user.admin
    })

    # Rotate the user's refresh-token jti. ``grace_seconds`` keeps the
    # previously-issued refresh token valid for a short window so a parallel
    # tab / login replay / in-flight refresh from before this login still
    # resolves successfully. See settings.REFRESH_TOKEN_GRACE_SECONDS and
    # the user-repository docstring for details.
    repository.rotate_refresh_token(
        user.id, refresh_jti, refresh_expires,
        grace_seconds=settings.REFRESH_TOKEN_GRACE_SECONDS,
    )

    return ServiceResult.ok({
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "user": user
    })
