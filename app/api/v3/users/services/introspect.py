"""
Introspection service for tokens.

Handles public introspection and refresh token rotation.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from .....core.security import (
    verify_access_token,
    verify_refresh_token,
    create_access_token,
    create_refresh_token,
)
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.service_result import ServiceResult


def introspect_tokens(
    db: Session,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None
) -> ServiceResult[dict]:
    """
    Introspect provided tokens. Public endpoint.

    Behavior:
    - If access_token is valid -> return active:true + user info
    - If access_token expired AND refresh_token valid -> rotate refresh token, issue new access+refresh
    - If refresh invalid/expired/reused -> return Unauthorized
    """
    if not access_token and not refresh_token:
        return ServiceResult.fail(error="No token provided", error_type="validation_error")

    repo = UserRepository(db)

    # Try access token first
    if access_token:
        is_valid, is_expired, payload = verify_access_token(access_token)
        if is_valid:
            # Fetch user info
            user = repo.get_by_id(payload.get("user_id"))
            if not user:
                return ServiceResult.fail(error="User not found", error_type="not_found")
            return ServiceResult.ok({
                "active": True,
                "user": user
            })

        # If expired and no refresh token provided, return a clear unauthorized
        if is_expired and not refresh_token:
            return ServiceResult.fail(
                error="Access token expired; refresh token required",
                error_type="authentication_error"
            )

        # If expired, and a refresh token is provided, fall through to refresh flow

    # Refresh flow
    if refresh_token:
        refresh_payload = verify_refresh_token(refresh_token)
        if not refresh_payload:
            return ServiceResult.fail(error="Invalid refresh token", error_type="authentication_error")

        user_id = refresh_payload.get("user_id")
        token_jti = refresh_payload.get("jti")
        if not user_id or not token_jti:
            return ServiceResult.fail(error="Invalid refresh token payload", error_type="authentication_error")

        stored_jti, stored_expires = repo.get_refresh_metadata(user_id)

        # Check stored metadata
        if not stored_jti or stored_jti != token_jti:
            # Token reused or not matching
            return ServiceResult.fail(error="Refresh token invalid or reused", error_type="authentication_error")

        # Check not expired according to stored_expires
        if stored_expires and stored_expires < datetime.utcnow():
            return ServiceResult.fail(error="Refresh token expired", error_type="authentication_error")

        # Issue new tokens (rotation)
        # Recreate subject data from payload
        token_data = {
            "sub": refresh_payload.get("sub"),
            "user_id": user_id,
            "email": refresh_payload.get("email"),
            "role": refresh_payload.get("role"),
            "is_admin": refresh_payload.get("is_admin", False),
        }

        new_access = create_access_token(token_data)
        new_refresh, new_jti, new_expires = create_refresh_token(token_data)

        # Persist new jti atomically: require that stored_jti still equals the
        # current token_jti to avoid race conditions (rotation must be single-writer).
        updated = repo.update_refresh_token_metadata(user_id, new_jti, new_expires, expected_old_jti=token_jti)
        if not updated:
            # Could not persist rotation; treat as token reuse or race and deny
            return ServiceResult.fail(error="Refresh token invalid or reused", error_type="authentication_error")

        user = repo.get_by_id(user_id)
        if not user:
            return ServiceResult.fail(error="User not found", error_type="not_found")

        return ServiceResult.ok({
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "user": user
        })

    return ServiceResult.fail(error="Invalid or expired tokens", error_type="authentication_error")
