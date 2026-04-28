"""
Token introspection service — RFC 7662 style.

Pure read-only metadata lookup. NEVER rotates tokens; rotation lives in
``services.refresh.refresh_tokens`` behind the dedicated
``POST /api/v3/users/refresh`` endpoint.

Returns a flat dict with the standard claim names:
    active, exp, iat, jti, sub, username, user_id, email, role, isAdmin,
    tokenType ('access' | 'refresh')

For an expired or unparseable token: ``{"active": false}`` (no payload
fields). The caller treats this as a 200 with the negative answer rather
than an error — matches RFC 7662's "active=false on inactive tokens".

Both ``access_token`` and ``refresh_token`` are accepted in the request
body (either or both). When both are supplied, two introspection results
are returned under ``access`` and ``refresh`` keys. When only one is
supplied, the response is a single inline result.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .....core.security import verify_access_token, verify_refresh_token
from .....infrastructure.db.repositories.revoked_token_repository import (
    RevokedTokenRepository,
)
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.service_result import ServiceResult


def _claims_to_response(
    payload: Dict[str, Any], *, token_type: str,
) -> Dict[str, Any]:
    """Project a decoded JWT payload into the public introspect response shape."""
    exp = payload.get("exp")
    iat = payload.get("iat")
    return {
        "active": True,
        "tokenType": token_type,
        "exp": exp,
        "iat": iat,
        # ISO 8601 forms for FE convenience — same value, easier to read.
        "expiresAt": (
            datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
            if isinstance(exp, (int, float)) else None
        ),
        "issuedAt": (
            datetime.fromtimestamp(iat, tz=timezone.utc).isoformat()
            if isinstance(iat, (int, float)) else None
        ),
        "jti": payload.get("jti"),
        "sub": payload.get("sub"),
        "username": payload.get("sub"),
        "userId": payload.get("user_id"),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "isAdmin": payload.get("is_admin", False),
    }


def _introspect_access(db: Session, token: str) -> Dict[str, Any]:
    """Introspect one access token. Always returns a dict (never raises)."""
    is_valid, _is_expired, payload = verify_access_token(token)
    if not is_valid or not payload:
        return {"active": False, "tokenType": "access"}

    # Active = signature valid AND not expired AND jti not in the
    # revoked-token blacklist (logout adds it). Only when all three hold
    # does the FE consider the token usable.
    jti = payload.get("jti")
    if jti and RevokedTokenRepository(db).is_revoked(jti):
        return {"active": False, "tokenType": "access"}

    return _claims_to_response(payload, token_type="access")


def _introspect_refresh(db: Session, token: str) -> Dict[str, Any]:
    """Introspect one refresh token. Always returns a dict (never raises).

    A refresh token is "active" only when:
      - signature is valid AND not expired
      - its jti matches the user row's stored ``refresh_token_jti``
        (i.e. it is the LATEST issued refresh — older ones rotated out)
      - the user row's stored ``refresh_token_expires_at`` is in the future
    """
    payload = verify_refresh_token(token)
    if not payload:
        return {"active": False, "tokenType": "refresh"}

    user_id = payload.get("user_id")
    jti = payload.get("jti")
    if not user_id or not jti:
        return {"active": False, "tokenType": "refresh"}

    repo = UserRepository(db)
    stored_jti, stored_expires = repo.get_refresh_metadata(user_id)
    if not stored_jti or stored_jti != jti:
        return {"active": False, "tokenType": "refresh"}

    if stored_expires is not None:
        # SQLite returns naive datetimes; coerce to aware UTC for comparison.
        stored_aware = (
            stored_expires
            if stored_expires.tzinfo is not None
            else stored_expires.replace(tzinfo=timezone.utc)
        )
        if stored_aware < datetime.now(timezone.utc):
            return {"active": False, "tokenType": "refresh"}

    return _claims_to_response(payload, token_type="refresh")


def introspect_tokens(
    db: Session,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> ServiceResult[Dict[str, Any]]:
    """Introspect one or both tokens.

    Returns:
      - Single token supplied → flat result dict ({"active": ..., ...}).
      - Both supplied → ``{"access": {...}, "refresh": {...}}``.
      - Neither → 422 validation_error.

    Never rotates. Rotation is the responsibility of ``refresh_tokens``.
    """
    if not access_token and not refresh_token:
        return ServiceResult.fail(
            error="No token provided. Supply 'access_token' or 'refresh_token'.",
            error_type="validation_error",
        )

    if access_token and refresh_token:
        return ServiceResult.ok({
            "access": _introspect_access(db, access_token),
            "refresh": _introspect_refresh(db, refresh_token),
        })

    if access_token:
        return ServiceResult.ok(_introspect_access(db, access_token))

    return ServiceResult.ok(_introspect_refresh(db, refresh_token))
