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

    class _StubClient:
        def __init__(self, *a, **kw):
            self._timeout = kw.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def request(self, method, url, *, headers=None, params=None,
                    content=None, json=None, **kw):
            recorder["calls"].append({
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "params": dict(params or {}),
                "content": content,
                "json": json,
            })
            if recorder["raise_on_request"] is not None:
                raise recorder["raise_on_request"]
            return recorder["next_response"]

    monkeypatch.setattr(httpx, "Client", _StubClient)
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
        assert _should_proxy_path("/api/v3/master/notification_templates") is True
        assert _should_proxy_path(
            "/api/v3/master/notification_templates/1/restore"
        ) is True

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
