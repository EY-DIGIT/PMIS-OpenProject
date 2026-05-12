"""Doc 37 part 2 — user-service proxy plumbing.

Coverage:
- When USER_SERVICE_PROXY_ENABLED=false (the default), every request
  flows through the monolith's local handlers. Proxy middleware is a
  no-op pass-through.
- When the flag is on AND USER_SERVICE_URL is set, requests to
  /api/v3/users/* and /api/v3/master/{roles,permissions,
  notification_templates}/* are forwarded to the upstream URL.
- Forwarded responses preserve status code and body byte-for-byte.
- Forwarded headers carry Authorization, Content-Type, Accept,
  X-Request-Id from the original request.
- Other paths (/api/v3/projects/*, /api/v3/master/divisions/*, /health,
  etc.) bypass the proxy even when the flag is on.
- httpx errors (connection refused, timeout) result in 503 with a
  user-facing error envelope; we do NOT silently fall back to local
  handlers.
"""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _StubResponse:
    """Minimal httpx.Response stand-in that the proxy reads."""

    def __init__(self, *, status_code: int, body: bytes, content_type: str = "application/json"):
        self.status_code = status_code
        self.content = body
        self.headers = {"content-type": content_type}


@pytest.fixture
def proxy_off(monkeypatch):
    """Default: proxy disabled. Local handlers run."""
    from app.core.config import settings as _settings
    monkeypatch.setattr(_settings, "USER_SERVICE_PROXY_ENABLED", False)
    monkeypatch.setattr(_settings, "USER_SERVICE_URL", "")
    yield


@pytest.fixture
def proxy_on(monkeypatch):
    """Flag on, URL set."""
    from app.core.config import settings as _settings
    monkeypatch.setattr(_settings, "USER_SERVICE_PROXY_ENABLED", True)
    monkeypatch.setattr(_settings, "USER_SERVICE_URL", "http://user-mgmt.test:8001")
    yield


@pytest.fixture
def stub_httpx(monkeypatch):
    """Replace httpx.Client with a stub that records every call.

    Returns the recorder dict so individual tests can configure the
    response and assert on what was sent.
    """
    recorder = {
        "calls": [],
        "next_response": _StubResponse(
            status_code=200,
            body=b'{"data": null, "message": null, "error": null, "status": 200}',
        ),
        "raise_on_request": None,
    }

    def _record(method, url, *, headers=None, params=None,
                content=None, json=None, **kw):
        recorder["calls"].append({
            "method": method, "url": url,
            "headers": dict(headers or {}),
            "params": dict(params or {}),
            "content": content, "json": json,
        })
        if recorder["raise_on_request"] is not None:
            raise recorder["raise_on_request"]
        return recorder["next_response"]

    class _StubClient:
        def __init__(self, *a, **kw):
            self._timeout = kw.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def request(self, method, url, **kw):
            return _record(method, url, **kw)

    class _StubAsyncClient:
        """Mirror of ``_StubClient`` for ``httpx.AsyncClient`` — needed
        after the doc-49 conversion of the proxy plumbing to async."""
        def __init__(self, *a, **kw):
            self._timeout = kw.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, **kw):
            return _record(method, url, **kw)

    monkeypatch.setattr(httpx, "Client", _StubClient)
    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)
    return recorder


# ---------------------------------------------------------------------------
# Path-prefix matching
# ---------------------------------------------------------------------------

class TestPathMatching:
    def test_users_path_is_proxied(self):
        from app.shared.user_service_client import _should_proxy_path
        assert _should_proxy_path("/api/v3/users") is True
        assert _should_proxy_path("/api/v3/users/login") is True
        assert _should_proxy_path("/api/v3/users/123/permissions/x") is True

    def test_master_roles_path_is_proxied(self):
        from app.shared.user_service_client import _should_proxy_path
        assert _should_proxy_path("/api/v3/master/roles") is True
        assert _should_proxy_path("/api/v3/master/permissions") is True
        assert _should_proxy_path("/api/v3/master/permissions/by-module") is True

    def test_notification_templates_NOT_proxied_to_user_service_post_doc38(self):
        # Doc 38 moved /master/notification_templates ownership to
        # notification-service. The user-service proxy must NOT
        # claim those paths.
        from app.shared.user_service_client import _should_proxy_path
        assert _should_proxy_path("/api/v3/master/notification_templates") is False
        assert _should_proxy_path(
            "/api/v3/master/notification_templates/1/restore"
        ) is False

    def test_other_master_paths_not_proxied(self):
        from app.shared.user_service_client import _should_proxy_path
        # Project-management master slices stay on the monolith.
        assert _should_proxy_path("/api/v3/master/divisions") is False
        assert _should_proxy_path("/api/v3/master/vendors") is False
        assert _should_proxy_path("/api/v3/master/project_categories") is False
        assert _should_proxy_path("/api/v3/master/activity_types") is False
        assert _should_proxy_path("/api/v3/master/milestone_statuses") is False
        assert _should_proxy_path("/api/v3/master/resource_types") is False

    def test_non_master_non_users_paths_not_proxied(self):
        from app.shared.user_service_client import _should_proxy_path
        assert _should_proxy_path("/health") is False
        assert _should_proxy_path("/api/v3/projects") is False
        assert _should_proxy_path("/api/v3/projects/abc/milestones") is False
        assert _should_proxy_path("/api/v3/work_packages/1") is False
        assert _should_proxy_path("/api/v3/meetings/1") is False

    def test_path_prefix_must_match_segment_boundary(self):
        # /api/v3/userspace would NOT match /api/v3/users.
        from app.shared.user_service_client import _should_proxy_path
        assert _should_proxy_path("/api/v3/userspace") is False

    # Doc 41: project- and vendor-side role-assignment endpoints
    # (e.g. /projects/{id}/role-assignments, /vendors/{id}/projects)
    # are intentionally NOT proxied. The FE talks to user-mgmt :8001
    # directly for those — keeps the new surface decoupled from the
    # monolith and shrinks the proxy responsibility.
    def test_doc41_project_role_assignments_NOT_proxied(self):
        from app.shared.user_service_client import _should_proxy_path
        assert _should_proxy_path(
            "/api/v3/projects/abc-123/role-assignments"
        ) is False

    def test_doc41_vendor_projects_NOT_proxied(self):
        from app.shared.user_service_client import _should_proxy_path
        assert _should_proxy_path(
            "/api/v3/vendors/abc-123/projects"
        ) is False

    def test_users_role_assignments_IS_proxied_via_users_prefix(self):
        # /api/v3/users/{id}/role-assignments still goes through because
        # it starts with the /api/v3/users prefix (existing rule). This
        # is the only doc-41 path that's proxied — the user-side variant.
        from app.shared.user_service_client import _should_proxy_path
        assert _should_proxy_path(
            "/api/v3/users/abc-123/role-assignments"
        ) is True


# ---------------------------------------------------------------------------
# Active-flag gate
# ---------------------------------------------------------------------------

class TestProxyActiveGate:
    def test_off_when_flag_false_even_if_url_set(self, monkeypatch):
        from app.core.config import settings as _settings
        from app.shared.user_service_client import _is_proxy_active
        monkeypatch.setattr(_settings, "USER_SERVICE_PROXY_ENABLED", False)
        monkeypatch.setattr(_settings, "USER_SERVICE_URL", "http://x")
        assert _is_proxy_active() is False

    def test_off_when_flag_true_but_url_blank(self, monkeypatch):
        from app.core.config import settings as _settings
        from app.shared.user_service_client import _is_proxy_active
        monkeypatch.setattr(_settings, "USER_SERVICE_PROXY_ENABLED", True)
        monkeypatch.setattr(_settings, "USER_SERVICE_URL", "")
        assert _is_proxy_active() is False

    def test_on_when_flag_and_url_set(self, monkeypatch):
        from app.core.config import settings as _settings
        from app.shared.user_service_client import _is_proxy_active
        monkeypatch.setattr(_settings, "USER_SERVICE_PROXY_ENABLED", True)
        monkeypatch.setattr(_settings, "USER_SERVICE_URL", "http://x")
        assert _is_proxy_active() is True


# ---------------------------------------------------------------------------
# Local handlers run when proxy is off
# ---------------------------------------------------------------------------

class TestProxyOff:
    def test_local_login_runs_when_proxy_disabled(
        self, client, admin_user, proxy_off,
    ):
        # admin_user has 2FA off (fixture default), so /login returns
        # the JWT pair directly. This exercises the LOCAL code path.
        resp = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()["data"]

    def test_local_health_runs_when_proxy_disabled(
        self, client, proxy_off,
    ):
        resp = client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Proxy forwards when on
# ---------------------------------------------------------------------------

class TestProxyOn:
    def test_login_forwards_to_user_service(
        self, client, proxy_on, stub_httpx,
    ):
        stub_httpx["next_response"] = _StubResponse(
            status_code=200,
            body=b'{"data":{"access_token":"forwarded.jwt.token"},"status":200}',
        )
        resp = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        assert "forwarded.jwt.token" in resp.text

        assert len(stub_httpx["calls"]) == 1
        call = stub_httpx["calls"][0]
        assert call["method"] == "POST"
        assert call["url"] == "http://user-mgmt.test:8001/api/v3/users/login"

    def test_master_roles_forwards(
        self, client, proxy_on, stub_httpx,
    ):
        stub_httpx["next_response"] = _StubResponse(
            status_code=200,
            body=b'{"data":{"_embedded":{"elements":[]}},"status":200}',
        )
        resp = client.get(
            "/api/v3/master/roles",
            headers={"Authorization": "Bearer fake.test.token"},
        )
        assert resp.status_code == 200
        # Authorization header must propagate so the user-service can
        # authenticate the caller.
        assert (
            stub_httpx["calls"][0]["headers"].get("Authorization")
            == "Bearer fake.test.token"
        )

    def test_query_string_forwarded(
        self, client, proxy_on, stub_httpx,
    ):
        stub_httpx["next_response"] = _StubResponse(
            status_code=200,
            body=b'{"data":null,"status":200}',
        )
        client.get(
            "/api/v3/master/permissions?offset=2&pageSize=50",
            headers={"Authorization": "Bearer x"},
        )
        params = stub_httpx["calls"][0]["params"]
        assert params.get("offset") == "2"
        assert params.get("pageSize") == "50"

    def test_non_proxied_path_bypasses_middleware(
        self, client, admin_headers, proxy_on, stub_httpx,
    ):
        # /api/v3/master/divisions is project-management territory —
        # must run locally even with the proxy flag on.
        resp = client.get("/api/v3/master/divisions", headers=admin_headers)
        assert resp.status_code == 200
        # No httpx calls should have been made.
        assert stub_httpx["calls"] == []

    def test_health_bypasses_middleware(
        self, client, proxy_on, stub_httpx,
    ):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert stub_httpx["calls"] == []

    def test_response_status_preserved(
        self, client, proxy_on, stub_httpx,
    ):
        # User-service returns 422 — monolith forwards it transparently.
        stub_httpx["next_response"] = _StubResponse(
            status_code=422,
            body=b'{"detail":[{"loc":["body","login"],"msg":"required"}]}',
        )
        resp = client.post("/api/v3/users/login", json={})
        assert resp.status_code == 422
        assert b"required" in resp.content


# ---------------------------------------------------------------------------
# CORS preflight handling — proxy must NOT forward OPTIONS
# ---------------------------------------------------------------------------

class TestCorsPreflightBypass:
    """OPTIONS preflights belong to the gateway the browser typed
    (monolith), not to the upstream user-service. The proxy must let
    them fall through so monolith's CORSMiddleware answers them
    locally — otherwise user-service routes (POST-only on /login etc.)
    return 405 and the browser blocks the actual request."""

    def test_options_on_proxied_path_not_forwarded(
        self, client, proxy_on, stub_httpx,
    ):
        # Build an actual CORS preflight: Origin + Access-Control-Request-*
        resp = client.options(
            "/api/v3/users/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )
        # No httpx call should have been made — the proxy let it fall
        # through, monolith's CORSMiddleware answered.
        assert stub_httpx["calls"] == [], (
            f"OPTIONS leaked to user-service: {stub_httpx['calls']}"
        )
        # CORSMiddleware answers 200 (or 204) with the right CORS headers.
        assert resp.status_code in (200, 204), resp.text

    def test_options_on_master_roles_not_forwarded(
        self, client, proxy_on, stub_httpx,
    ):
        resp = client.options(
            "/api/v3/master/roles",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert stub_httpx["calls"] == []
        assert resp.status_code in (200, 204)

    def test_post_after_options_still_forwards(
        self, client, proxy_on, stub_httpx,
    ):
        """Sanity: bypassing OPTIONS doesn't accidentally also bypass POST."""
        stub_httpx["next_response"] = _StubResponse(
            status_code=200,
            body=b'{"data":{"_type":"Login"},"status":200}',
        )
        client.options(
            "/api/v3/users/login",
            headers={"Origin": "http://localhost:3000",
                     "Access-Control-Request-Method": "POST"},
        )
        resp = client.post(
            "/api/v3/users/login", json={"login": "admin", "password": "x"},
        )
        assert resp.status_code == 200
        assert len(stub_httpx["calls"]) == 1
        assert stub_httpx["calls"][0]["method"] == "POST"

    def test_proxied_post_response_carries_cors_headers(
        self, client, proxy_on, stub_httpx,
    ):
        """When the proxy intercepts a POST and short-circuits ``send``,
        the response still has to be wrapped by CORSMiddleware on the
        way back. CORSMiddleware must be the OUTERMOST middleware
        (added LAST in app/main.py) — otherwise the browser sees a
        2xx body without ``Access-Control-Allow-Origin`` and blocks
        the response with "failed to fetch", even though the request
        itself succeeded server-side."""
        stub_httpx["next_response"] = _StubResponse(
            status_code=200,
            body=b'{"data":{"_type":"Login","access_token":"t"},"status":200}',
        )
        resp = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "x"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200
        # The proxy actually forwarded.
        assert len(stub_httpx["calls"]) == 1
        # AND a CORS Allow-Origin header is present on the proxied response.
        # The exact value depends on CORS_ORIGINS (the default test config
        # is ["*"] → "*"; a deploy with a specific allowlist echoes the
        # origin) — the regression we're pinning is "header present at
        # all," because if CORSMiddleware moves back inside the proxy
        # the header disappears entirely and browsers break with
        # "failed to fetch".
        allow_origin = resp.headers.get("access-control-allow-origin")
        assert allow_origin is not None, (
            "no Access-Control-Allow-Origin on proxied response. "
            "Likely cause: CORSMiddleware is no longer outermost in "
            "app/main.py — must be added LAST so it wraps the proxy."
        )


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

class TestProxyFailure:
    def test_connection_error_returns_503(
        self, client, proxy_on, stub_httpx,
    ):
        stub_httpx["raise_on_request"] = httpx.ConnectError("connection refused")
        resp = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["errorIdentifier"] == "user_service_unavailable"
        # Critically, we do NOT fall through to the local handler —
        # otherwise a degraded user-service would mask state divergence.
        # Confirm the response came from the proxy, not the local
        # /login handler (which would return a different shape).

    def test_timeout_returns_503(
        self, client, proxy_on, stub_httpx,
    ):
        stub_httpx["raise_on_request"] = httpx.ReadTimeout("read timeout")
        resp = client.post("/api/v3/users/login", json={"login": "x", "password": "y"})
        assert resp.status_code == 503
        assert resp.json()["error"]["errorIdentifier"] == "user_service_unavailable"
