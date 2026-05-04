"""
Authentication middleware for JWT validation.

Doc 21 part B: after token decode, the middleware looks up the user's
effective permission set (role-derived ∪ direct grants) and stores it
on ``request.state.user_permissions``. The decorator
``require_permission(code)`` reads from that Set on each call. ``is_admin``
is derived from membership in the seeded ``admin`` role — the legacy
``users.admin`` boolean column is gone.

The lookup is one indexed JOIN per authenticated request. For anonymous
or revoked-token requests the lookup is skipped and ``user_permissions``
stays empty, which causes every ``require_permission`` to reject with 401.
"""
from datetime import datetime, timezone
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from ..security import decode_access_token


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        request.state.user_id = None
        request.state.user_login = None
        request.state.user_permissions = set()
        request.state.is_admin = False
        request.state.token_jti = None
        request.state.token_exp = None

        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = decode_access_token(token)
            if payload:
                jti = payload.get("jti")
                if jti and self._is_revoked(jti):
                    response = await call_next(request)
                    return response

                user_id = payload.get("user_id")
                request.state.user_id = user_id
                request.state.user_login = payload.get("sub")
                request.state.token_jti = jti
                exp_ts = payload.get("exp")
                if exp_ts is not None:
                    try:
                        request.state.token_exp = datetime.fromtimestamp(
                            int(exp_ts), tz=timezone.utc
                        )
                    except (TypeError, ValueError):
                        request.state.token_exp = None

                # Hydrate effective permission set + admin flag from DB.
                if user_id is not None:
                    perms, is_admin = self._load_user_permissions(user_id)
                    request.state.user_permissions = perms
                    request.state.is_admin = is_admin

        response = await call_next(request)
        return response

    @staticmethod
    def _is_revoked(jti: str) -> bool:
        from ...infrastructure.db.session import SessionLocal
        from ...infrastructure.db.repositories.revoked_token_repository import (
            RevokedTokenRepository,
        )
        db = SessionLocal()
        try:
            return RevokedTokenRepository(db).is_revoked(jti)
        finally:
            db.close()

    @staticmethod
    def _load_user_permissions(user_id: str):
        """Returns (permissions: Set[str], is_admin: bool)."""
        from ...infrastructure.db.session import SessionLocal
        from ...infrastructure.db.repositories.rbac_repository import (
            RbacRepository,
        )
        db = SessionLocal()
        try:
            repo = RbacRepository(db)
            perms = repo.effective_permissions_for_user(user_id)
            is_admin = repo.user_has_admin_role(user_id)
            return perms, is_admin
        finally:
            db.close()
