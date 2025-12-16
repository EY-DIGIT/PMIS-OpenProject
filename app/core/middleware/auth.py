"""
Authentication middleware for JWT validation.
"""
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from ..security import decode_access_token
from ..rbac import Role


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to authenticate requests using JWT Bearer tokens.

    This middleware:
    1. Extracts JWT token from Authorization header
    2. Validates and decodes the token
    3. Attaches user information to request.state
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process the request and authenticate if token is present.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from next handler
        """
        # Initialize request state with anonymous user
        request.state.user_id = None
        request.state.user_login = None
        request.state.user_role = Role.ANONYMOUS
        request.state.is_admin = False

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

            # Decode and validate token
            payload = decode_access_token(token)

            if payload:
                # Attach user information to request state
                request.state.user_id = payload.get("user_id")
                request.state.user_login = payload.get("sub")
                request.state.user_role = Role(payload.get("role", Role.ANONYMOUS.value))
                request.state.is_admin = payload.get("is_admin", False)

        # Continue processing
        response = await call_next(request)
        return response
