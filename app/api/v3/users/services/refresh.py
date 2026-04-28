"""
Refresh-token rotation service.

Backs ``POST /api/v3/users/refresh``. Takes a refresh token, validates it
against the user row's stored jti + expiry, and on success issues a fresh
access + refresh pair. Atomic — the user row's ``refresh_token_jti`` is
swapped to the new value via a conditional UPDATE that requires the old
jti to match (single-writer guarantee), so concurrent refresh attempts
with the same token only succeed once.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .....core.security import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.service_result import ServiceResult


def _exp_metadata(token: str) -> Dict[str, Any]:
    """Decode a freshly-minted token (no signature check needed — we just
    minted it) to surface its expiry / issued-at timestamps to the caller."""
    from jose import jwt
    from .....core.config import settings
    payload = jwt.decode(
        token, settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"verify_exp": False},
    )
    exp = payload.get("exp")
    iat = payload.get("iat")
    return {
        "expiresAt": (
            datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
            if isinstance(exp, (int, float)) else None
        ),
        "issuedAt": (
            datetime.fromtimestamp(iat, tz=timezone.utc).isoformat()
            if isinstance(iat, (int, float)) else None
        ),
        "exp": exp,
        "iat": iat,
    }


def refresh_tokens(
    db: Session,
    refresh_token: Optional[str] = None,
) -> ServiceResult[Dict[str, Any]]:
    """Validate a refresh token and rotate to a new pair.

    Returns:
        On success: dict with the new access + refresh tokens, the rotated
        user, and expiry metadata for both tokens.
        On failure: ServiceResult.fail with errorIdentifier=
        ``authentication_error`` and a 401 from the controller.
    """
    if not refresh_token:
        return ServiceResult.fail(
            error="refresh_token is required.",
            error_type="validation_error",
        )

    payload = verify_refresh_token(refresh_token)
    if not payload:
        return ServiceResult.fail(
            error="Invalid refresh token.",
            error_type="authentication_error",
        )

    user_id = payload.get("user_id")
    token_jti = payload.get("jti")
    if not user_id or not token_jti:
        return ServiceResult.fail(
            error="Invalid refresh token payload.",
            error_type="authentication_error",
        )

    repo = UserRepository(db)
    stored_jti, stored_expires = repo.get_refresh_metadata(user_id)
    if not stored_jti or stored_jti != token_jti:
        # Either the user has been logged out (jti cleared), or this is
        # an older refresh token that has already been rotated out.
        return ServiceResult.fail(
            error="Refresh token invalid or already rotated.",
            error_type="authentication_error",
        )

    if stored_expires is not None:
        stored_aware = (
            stored_expires
            if stored_expires.tzinfo is not None
            else stored_expires.replace(tzinfo=timezone.utc)
        )
        if stored_aware < datetime.now(timezone.utc):
            return ServiceResult.fail(
                error="Refresh token expired.",
                error_type="authentication_error",
            )

    # Mint the new pair with the same identity claims as the old refresh.
    token_data = {
        "sub": payload.get("sub"),
        "user_id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role"),
        "is_admin": payload.get("is_admin", False),
    }
    new_access = create_access_token(token_data)
    new_refresh, new_jti, new_expires = create_refresh_token(token_data)

    # Atomic swap: only succeeds when the stored jti still equals the one
    # we validated against. Two concurrent refreshes can't both win.
    swapped = repo.update_refresh_token_metadata(
        user_id, new_jti, new_expires, expected_old_jti=token_jti,
    )
    if not swapped:
        return ServiceResult.fail(
            error="Refresh token invalid or already rotated.",
            error_type="authentication_error",
        )

    user = repo.get_by_id(user_id)
    if not user:
        return ServiceResult.fail(
            error="User not found.",
            error_type="not_found",
        )

    access_meta = _exp_metadata(new_access)
    refresh_meta = _exp_metadata(new_refresh)

    return ServiceResult.ok({
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "accessTokenExpiresAt": access_meta["expiresAt"],
        "accessTokenIssuedAt": access_meta["issuedAt"],
        "refreshTokenExpiresAt": refresh_meta["expiresAt"],
        "refreshTokenIssuedAt": refresh_meta["issuedAt"],
        "expiresInSeconds": (
            int(access_meta["exp"] - access_meta["iat"])
            if access_meta["exp"] and access_meta["iat"] else None
        ),
        "user": user,
    })
