"""Doc 38 — notification-service proxy plumbing.

Mirrors test_doc37_user_service_proxy.py for the notification-service
prefix set. Coverage:
- /api/v3/master/notification_templates/* paths are proxied when the
  flag is on.
- All other paths bypass the notification-service proxy.
- Failure modes: connection error / timeout → 503 with
  errorIdentifier="notification_service_unavailable"; no fallback to
  local handlers.
"""
from __future__ import annotations

import httpx
import pytest


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _StubResponse:
    def __init__(self, *, status_code: int, body: bytes, content_type: str = "application/json"):
        self.status_code = status_code
        self.content = body
        self.headers = {"content-type": content_type}


@pytest.fixture
def proxy_off(monkeypatch):
    from app.core.config import settings as _settings
    monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_PROXY_ENABLED", False)
    monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_URL", "")
    yield


@pytest.fixture
def proxy_on(monkeypatch):
    from app.core.config import settings as _settings
    monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_PROXY_ENABLED", True)
    monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_URL", "http://notif-service.test:8002")
    yield


@pytest.fixture
def stub_httpx(monkeypatch):
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
    def test_notification_templates_paths_proxied(self):
        from app.shared.notification_service_client import _should_proxy_path
        assert _should_proxy_path("/api/v3/master/notification_templates") is True
        assert _should_proxy_path("/api/v3/master/notification_templates/1") is True
        assert _should_proxy_path(
            "/api/v3/master/notification_templates/1/restore"
        ) is True

    def test_user_service_paths_not_proxied(self):
        from app.shared.notification_service_client import _should_proxy_path
        # The user-service proxy claims these — notification-service must NOT.
        assert _should_proxy_path("/api/v3/users") is False
        assert _should_proxy_path("/api/v3/users/login") is False
        assert _should_proxy_path("/api/v3/master/roles") is False
        assert _should_proxy_path("/api/v3/master/permissions") is False

    def test_other_paths_not_proxied(self):
        from app.shared.notification_service_client import _should_proxy_path
        assert _should_proxy_path("/health") is False
        assert _should_proxy_path("/api/v3/projects") is False
        assert _should_proxy_path("/api/v3/master/divisions") is False
        assert _should_proxy_path("/api/v3/master/vendors") is False


# ---------------------------------------------------------------------------
# Active-flag gate
# ---------------------------------------------------------------------------

class TestProxyActiveGate:
    def test_off_when_flag_false(self, monkeypatch):
        from app.core.config import settings as _settings
        from app.shared.notification_service_client import _is_proxy_active
        monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_PROXY_ENABLED", False)
        monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_URL", "http://x")
        assert _is_proxy_active() is False

    def test_off_when_url_blank(self, monkeypatch):
        from app.core.config import settings as _settings
        from app.shared.notification_service_client import _is_proxy_active
        monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_PROXY_ENABLED", True)
        monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_URL", "")
        assert _is_proxy_active() is False

    def test_on_when_flag_and_url_set(self, monkeypatch):
        from app.core.config import settings as _settings
        from app.shared.notification_service_client import _is_proxy_active
        monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_PROXY_ENABLED", True)
        monkeypatch.setattr(_settings, "NOTIFICATION_SERVICE_URL", "http://x")
        assert _is_proxy_active() is True


# ---------------------------------------------------------------------------
# On-mode forwarding
# ---------------------------------------------------------------------------

class TestProxyOn:
    def test_list_templates_forwarded(
        self, client, admin_headers, proxy_on, stub_httpx,
    ):
        stub_httpx["next_response"] = _StubResponse(
            status_code=200,
            body=b'{"data":{"_embedded":{"elements":[]}},"status":200}',
        )
        resp = client.get(
            "/api/v3/master/notification_templates", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert len(stub_httpx["calls"]) == 1
        call = stub_httpx["calls"][0]
        assert call["method"] == "GET"
        assert call["url"] == "http://notif-service.test:8002/api/v3/master/notification_templates"
        assert call["headers"].get("Authorization", "").startswith("Bearer ")

    def test_restore_endpoint_forwarded(
        self, client, admin_headers, proxy_on, stub_httpx,
    ):
        stub_httpx["next_response"] = _StubResponse(
            status_code=200,
            body=b'{"data":{},"status":200}',
        )
        client.post(
            "/api/v3/master/notification_templates/1/restore",
            headers=admin_headers,
        )
        assert stub_httpx["calls"][0]["url"].endswith(
            "/api/v3/master/notification_templates/1/restore"
        )

    def test_user_service_paths_bypass_this_middleware(
        self, client, admin_headers, proxy_on, stub_httpx,
    ):
        # /master/roles is the user-service's, not notification-service's.
        # When this middleware sees it, it should pass through (the
        # user-service proxy or local handler picks it up downstream).
        # In our test setup the user-service proxy is OFF, so the
        # request lands on the monolith's local /master/roles handler
        # — the notification-service stub must not have been called.
        client.get("/api/v3/master/roles", headers=admin_headers)
        assert stub_httpx["calls"] == []

    def test_master_divisions_bypasses(
        self, client, admin_headers, proxy_on, stub_httpx,
    ):
        # Project-management master slice → local handler.
        resp = client.get("/api/v3/master/divisions", headers=admin_headers)
        assert resp.status_code == 200
        assert stub_httpx["calls"] == []


# ---------------------------------------------------------------------------
# CORS preflight handling — proxy must NOT forward OPTIONS
# ---------------------------------------------------------------------------

class TestCorsPreflightBypass:
    """OPTIONS preflights stop at the monolith — same contract as the
    user-service proxy. Forwarding them to notification-service would
    return 405 and break browser-side template-management UI."""

    def test_options_on_notification_templates_not_forwarded(
        self, client, proxy_on, stub_httpx,
    ):
        resp = client.options(
            "/api/v3/master/notification_templates",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert stub_httpx["calls"] == [], (
            f"OPTIONS leaked to notification-service: {stub_httpx['calls']}"
        )
        assert resp.status_code in (200, 204), resp.text

    def test_get_after_options_still_forwards(
        self, client, admin_headers, proxy_on, stub_httpx,
    ):
        stub_httpx["next_response"] = _StubResponse(
            status_code=200,
            body=b'{"data":{"_embedded":{"elements":[]}},"status":200}',
        )
        client.options(
            "/api/v3/master/notification_templates",
            headers={"Origin": "http://localhost:3000",
                     "Access-Control-Request-Method": "GET"},
        )
        resp = client.get(
            "/api/v3/master/notification_templates", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert len(stub_httpx["calls"]) == 1
        assert stub_httpx["calls"][0]["method"] == "GET"


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

class TestProxyFailure:
    def test_connection_error_returns_503(
        self, client, admin_headers, proxy_on, stub_httpx,
    ):
        stub_httpx["raise_on_request"] = httpx.ConnectError("connection refused")
        resp = client.get(
            "/api/v3/master/notification_templates", headers=admin_headers,
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["errorIdentifier"] == "notification_service_unavailable"

    def test_timeout_returns_503(
        self, client, admin_headers, proxy_on, stub_httpx,
    ):
        stub_httpx["raise_on_request"] = httpx.ReadTimeout("read timeout")
        resp = client.get(
            "/api/v3/master/notification_templates", headers=admin_headers,
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["errorIdentifier"] == "notification_service_unavailable"
