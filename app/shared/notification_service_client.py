"""Notification-service proxy client (doc 38).

Mirrors ``user_service_client.py`` for notification-service master
endpoints (doc 38 ownership move). Forwards ``/api/v3/master/
notification_templates/*`` to the standalone PMIS-notification-service
on port 8002 when ``NOTIFICATION_SERVICE_PROXY_ENABLED=true``.

Strangler-fig pattern, fail-closed contract identical to the user-
service proxy. When the flag is off, the middleware is a cheap pass-
through and the monolith's local handlers (still on disk for rollback
safety) run instead.

Auth: proxied requests carry the original ``Authorization`` header so
the notification-service authenticates them with the shared SECRET_KEY.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from ..core.config import settings


logger = logging.getLogger(__name__)


_HTTP_CONNECT_TIMEOUT = 5.0


def _is_proxy_active() -> bool:
    return bool(getattr(settings, "NOTIFICATION_SERVICE_PROXY_ENABLED", False)) and bool(
        (getattr(settings, "NOTIFICATION_SERVICE_URL", "") or "").strip()
    )


def _build_url(path: str) -> str:
    base = (settings.NOTIFICATION_SERVICE_URL or "").rstrip("/")
    return f"{base}{path}"


def _proxy_request_sync(
    request: Request,
    *,
    method: str,
    target_path: str,
    body_bytes: Optional[bytes],
) -> Response:
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

    timeout_s = float(
        getattr(settings, "NOTIFICATION_SERVICE_TIMEOUT_SECONDS", 10.0)
    )
    timeout = httpx.Timeout(
        connect=_HTTP_CONNECT_TIMEOUT,
        read=timeout_s,
        write=timeout_s,
        pool=timeout_s,
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            kwargs: Dict[str, Any] = {"headers": headers, "params": query}
            if body_bytes:
                kwargs["content"] = body_bytes
            resp = client.request(method.upper(), url, **kwargs)
    except httpx.HTTPError as e:
        logger.error(
            "Notification-service proxy failed for %s %s: %s",
            method, target_path, e,
        )
        return JSONResponse(
            status_code=503,
            content={
                "data": None,
                "message": None,
                "error": {
                    "_type": "Error",
                    "errorIdentifier": "notification_service_unavailable",
                    "message": (
                        "Notification service unavailable (proxy). "
                        "Set NOTIFICATION_SERVICE_PROXY_ENABLED=false to "
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


# Path prefixes notification-service owns (post-doc-38).
_PROXIED_PATH_PREFIXES = (
    "/api/v3/master/notification_templates",
)


def _should_proxy_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _PROXIED_PATH_PREFIXES)


class NotificationServiceProxyMiddleware:
    """ASGI middleware that forwards notification-template admin paths
    to notification-service (port 8002). Same contract as the user-
    service proxy: fail-closed 503 on unreachable; off-flag = no-op
    pass-through.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        if not _is_proxy_active():
            await self.app(scope, receive, send)
            return

        # CORS preflights belong to the gateway the client typed (monolith),
        # not to the upstream. Forwarding OPTIONS makes notification-service
        # return 405 and breaks browser preflight. Let CORSMiddleware on the
        # monolith answer it locally.
        if (scope.get("method") or "").upper() == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not _should_proxy_path(path):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        body_bytes = await request.body()
        response = _proxy_request_sync(
            request,
            method=request.method,
            target_path=path,
            body_bytes=body_bytes,
        )
        await response(scope, receive, send)
