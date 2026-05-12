"""User-service proxy client (doc 37 part 2).

Forwards user/auth/RBAC/notification-template requests from the
monolith to PMIS-user-management running on port 8001. Same
strangler-fig pattern as ``HttpNotificationClient`` — the FE keeps
calling the same monolith URLs; the monolith decides per-route
whether to run locally or proxy to the user-service based on the
``USER_SERVICE_PROXY_ENABLED`` flag.

Selection rules (applied per-request in the route handlers):

  1. ``USER_SERVICE_PROXY_ENABLED=false`` (default): every handler
     runs the local code path. No HTTP hop. This is the pre-doc-37
     behaviour.
  2. ``USER_SERVICE_PROXY_ENABLED=true``: handlers that have been
     wired with ``maybe_proxy_user_service`` forward their incoming
     request body / query / path / headers to the user-service and
     return the response transparently.

What happens on user-service failure:
  - Connection errors / timeouts → 503 with the message
    ``"User service unavailable (proxy)"`` to the FE. We do NOT fall
    through to the local handler — that's deliberate. The local
    code path's RBAC + DB state may have diverged from user-service
    while the proxy was on, and silently falling back risks
    inconsistent behavior across requests. Fail-closed is the safer
    default; if ops want a fallback path, set the flag back to false.
  - HTTP non-2xx from user-service → forwarded as-is (status code
    + body), so the FE sees the user-service's error envelope
    directly. This preserves error-identifier semantics across the
    proxy.

Auth:
  - Proxied requests carry the original ``Authorization`` header so
    the user-service authenticates them with the shared SECRET_KEY.
  - For public endpoints (``/login`` etc.) the header is absent on
    the way in and stays absent on the way through.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from ..core.config import settings


logger = logging.getLogger(__name__)


# Connect timeout fixed at 5s; read timeout from settings so ops can
# tune for slow upstream paths (rare, but configurable).
_HTTP_CONNECT_TIMEOUT = 5.0


def _is_proxy_active() -> bool:
    """Single source of truth for whether to proxy."""
    return bool(settings.USER_SERVICE_PROXY_ENABLED) and bool(
        (settings.USER_SERVICE_URL or "").strip()
    )


def _build_url(path: str) -> str:
    base = (settings.USER_SERVICE_URL or "").rstrip("/")
    return f"{base}{path}"


def _proxy_request_sync(
    request: Request,
    *,
    method: str,
    target_path: str,
    body_bytes: Optional[bytes],
    json_body: Optional[Dict[str, Any]] = None,
) -> Response:
    """Synchronous forward to user-service; returns a FastAPI Response.

    Sync (not async) so it slots into existing sync FastAPI handlers
    without forcing an async refactor of the whole users router.
    Reads the incoming request body via ``request.scope["pmis_body_cache"]``
    when populated by the helper below — FastAPI consumes the body
    once and we cache it before delegating.

    Forwards: method, body, query string, Authorization header (if
    present), Content-Type / Accept / X-Request-Id headers. Strips
    host-related headers that don't carry meaning across the hop.
    """
    headers: Dict[str, str] = {}
    auth = request.headers.get("authorization")
    if auth:
        headers["Authorization"] = auth
    content_type = request.headers.get("content-type")
    if content_type:
        headers["Content-Type"] = content_type
    accept = request.headers.get("accept")
    if accept:
        headers["Accept"] = accept
    request_id = request.headers.get("x-request-id")
    if request_id:
        headers["X-Request-Id"] = request_id

    url = _build_url(target_path)
    query = dict(request.query_params)

    timeout = httpx.Timeout(
        connect=_HTTP_CONNECT_TIMEOUT,
        read=float(settings.USER_SERVICE_TIMEOUT_SECONDS),
        write=float(settings.USER_SERVICE_TIMEOUT_SECONDS),
        pool=float(settings.USER_SERVICE_TIMEOUT_SECONDS),
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            kwargs: Dict[str, Any] = {
                "headers": headers,
                "params": query,
            }
            if json_body is not None:
                kwargs["json"] = json_body
            elif body_bytes:
                kwargs["content"] = body_bytes
            resp = client.request(method.upper(), url, **kwargs)
    except httpx.HTTPError as e:
        logger.error(
            "User-service proxy failed for %s %s: %s",
            method, target_path, e,
        )
        return JSONResponse(
            status_code=503,
            content={
                "data": None,
                "message": None,
                "error": {
                    "_type": "Error",
                    "errorIdentifier": "user_service_unavailable",
                    "message": (
                        "User service unavailable (proxy). "
                        "Set USER_SERVICE_PROXY_ENABLED=false to "
                        "fall back to the monolith's local handlers."
                    ),
                },
                "status": 503,
            },
        )

    response_content_type = resp.headers.get("content-type", "")
    forwarded_headers = {}
    for h_name in ("content-type", "x-request-id"):
        if h_name in resp.headers:
            forwarded_headers[h_name] = resp.headers[h_name]
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=forwarded_headers,
        media_type=response_content_type or None,
    )


def maybe_proxy_user_service(
    request: Request,
    *,
    target_path: Optional[str] = None,
    json_body: Optional[Dict[str, Any]] = None,
    body_bytes: Optional[bytes] = None,
) -> Optional[Response]:
    """Sync helper for monolith route handlers (kept for direct use).

    Returns:
      - ``None`` when the proxy is off → caller continues with the
        local code path.
      - A forwarded ``Response`` when the proxy is on → caller
        returns it directly to the FE.

    Most callers should use ``UserServiceProxyMiddleware`` instead —
    it intercepts proxied paths globally without touching individual
    handlers. This helper is for routes that need to make per-request
    decisions about whether to proxy.
    """
    if not _is_proxy_active():
        return None
    path = target_path if target_path is not None else request.url.path
    return _proxy_request_sync(
        request,
        method=request.method,
        target_path=path,
        body_bytes=body_bytes,
        json_body=json_body,
    )


def proxy_or_503(
    request: Request,
    *,
    body_bytes: Optional[bytes] = None,
) -> Response:
    """For handlers that exist solely to forward — no local fallback.

    Doc 44 round 12: a handful of user-mgmt-only routes
    (``POST/DELETE /projects/{id}/role-assignments`` and
    ``GET /vendors/{id}/users``) are surfaced on monolith :8000 so the
    FE never needs a direct :8001 call. The monolith does not own the
    write path — it just forwards. When ``USER_SERVICE_PROXY_ENABLED``
    is off there's no local code to fall back to, so we 503 with a
    clear envelope rather than silently 404.
    """
    response = maybe_proxy_user_service(request, body_bytes=body_bytes)
    if response is not None:
        return response
    return JSONResponse(
        status_code=503,
        content={
            "data": None,
            "message": None,
            "error": {
                "_type": "Error",
                "errorIdentifier": "user_service_proxy_disabled",
                "message": (
                    "This route forwards to user-management. Enable "
                    "USER_SERVICE_PROXY_ENABLED on the monolith, or call "
                    "user-management :8001 directly."
                ),
            },
            "status": 503,
        },
    )


# ---------------------------------------------------------------------------
# Middleware — global path-based proxy interception
# ---------------------------------------------------------------------------

# Path prefixes user-service owns. Requests matching these get
# forwarded to USER_SERVICE_URL when the proxy flag is on.
#
# Doc 38: notification_templates moved to notification-service. It used
# to be in this list; now it's in _NOTIFICATION_SERVICE_PREFIXES below.
_PROXIED_PATH_PREFIXES = (
    "/api/v3/users",
    "/api/v3/master/roles",
    "/api/v3/master/permissions",
    # Doc 44 round 9 — /role-grants is a standalone user-mgmt prefix
    # (the static grant-matrix endpoint backing the FE create-user role
    # dropdown). Adding it here makes ``GET /api/v3/role-grants/...``
    # reachable through monolith :8000 so the FE never needs a direct
    # :8001 call.
    "/api/v3/role-grants",
)

# Doc 41 / 44 round 9 — the project- and vendor-side scoped
# role-assignment routes (``POST/DELETE /projects/{id}/role-assignments``
# and ``GET /vendors/{id}/users``) are NOT proxied. Their URL namespaces
# (``/projects/*`` and ``/vendors/*``) are monolith-owned — blanket
# prefixing would forward unrelated routes. Instead they live as
# native handlers in ``projects/routes.py`` and ``vendors/routes.py``,
# with shared schemas + services under ``role_assignments/``. The
# ``/users/{id}/role-assignments`` variant remains reachable through
# the ``/api/v3/users`` prefix above.


def _should_proxy_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _PROXIED_PATH_PREFIXES)


class UserServiceProxyMiddleware:
    """ASGI middleware that forwards user/auth/RBAC paths to user-service.

    When ``USER_SERVICE_PROXY_ENABLED=true`` AND ``USER_SERVICE_URL`` is
    set, every incoming request whose path matches the proxied
    prefixes is forwarded as-is. Otherwise the request continues
    through the normal FastAPI routing.

    Mounted in app/main.py before AuthenticationMiddleware so the
    proxy bypasses the monolith's auth + RBAC chain entirely — the
    user-service is the authoritative gate for those paths.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # Cheap gate: nothing happens unless the proxy is on.
        if not _is_proxy_active():
            await self.app(scope, receive, send)
            return

        # CORS preflights belong to whoever the client typed the URL at —
        # the monolith — not to the upstream service. Forwarding OPTIONS
        # makes user-service return 405 (no OPTIONS handler on its routes)
        # and breaks browser preflight. Let the request fall through so
        # monolith's CORSMiddleware answers it locally.
        if (scope.get("method") or "").upper() == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not _should_proxy_path(path):
            await self.app(scope, receive, send)
            return

        # Build a Request to leverage the helper. We need to consume
        # the body before the local handlers do.
        request = Request(scope, receive=receive)
        body_bytes = await request.body()
        response = _proxy_request_sync(
            request,
            method=request.method,
            target_path=path,
            body_bytes=body_bytes,
        )
        await response(scope, receive, send)
