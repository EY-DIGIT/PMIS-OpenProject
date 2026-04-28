"""Tests for authentication endpoints and flows."""
import pytest


class TestHealthAndRoot:
    """Public endpoints that require no authentication."""

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["_type"] == "Health"

    def test_root_endpoint(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["_type"] == "Root"
        assert "_links" in data
        assert "self" in data["_links"]


class TestLogin:
    """Login endpoint tests."""

    def test_login_success(self, client, admin_user):
        resp = client.post("/api/v3/users/login", json={
            "login": "admin",
            "password": "admin123",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "access_token" in body["data"]
        assert body["data"]["token_type"] == "bearer"
        assert body["data"]["user"]["login"] == "admin"

    def test_login_invalid_password(self, client, admin_user):
        resp = client.post("/api/v3/users/login", json={
            "login": "admin",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client, admin_user):
        resp = client.post("/api/v3/users/login", json={
            "login": "nobody",
            "password": "password123",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v3/users/login", json={"login": "admin"})
        assert resp.status_code == 422

    def test_login_empty_body(self, client):
        resp = client.post("/api/v3/users/login", json={})
        assert resp.status_code == 422


class TestProtectedAccess:
    """Verify authentication middleware blocks unauthenticated requests."""

    def test_no_token_returns_401(self, client, admin_user):
        resp = client.get("/api/v3/users/me")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client, admin_user):
        resp = client.get(
            "/api/v3/users/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    def test_malformed_header_returns_401(self, client, admin_user):
        resp = client.get(
            "/api/v3/users/me",
            headers={"Authorization": "NotBearer token"},
        )
        assert resp.status_code == 401

    def test_valid_token_returns_user(self, client, admin_user, admin_headers):
        resp = client.get("/api/v3/users/me", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["login"] == "admin"
        assert body["data"]["_type"] == "User"


class TestIntrospect:
    """Token introspection endpoint (RFC 7662 read-only metadata)."""

    def test_introspect_valid_token(self, client, admin_user, admin_token):
        resp = client.post("/api/v3/users/introspect", json={
            "access_token": admin_token,
        })
        assert resp.status_code == 200
        body = resp.json()
        d = body["data"]
        assert d["active"] is True
        assert d["tokenType"] == "access"
        assert d["sub"] == "admin"
        assert d["userId"] == admin_user.id
        assert d["isAdmin"] is True
        # Expiry / issued-at must be ISO 8601 strings the FE can parse.
        assert d["expiresAt"] and "T" in d["expiresAt"]
        assert d["issuedAt"] and "T" in d["issuedAt"]
        assert d["jti"]

    def test_introspect_no_token(self, client):
        resp = client.post("/api/v3/users/introspect", json={})
        assert resp.status_code in [400, 401, 422]

    def test_introspect_garbage_token_returns_inactive(self, client):
        """Unparseable token → 200 with active=false (RFC 7662 semantics)."""
        resp = client.post(
            "/api/v3/users/introspect",
            json={"access_token": "not-a-jwt"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["active"] is False
        assert body["tokenType"] == "access"

    def test_introspect_both_tokens_returns_split_shape(self, client, admin_user):
        """Supplying both access + refresh produces a split response with
        a per-token result under access / refresh keys."""
        login = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"},
        )
        assert login.status_code == 200
        ld = login.json()["data"]

        resp = client.post(
            "/api/v3/users/introspect",
            json={
                "access_token": ld["access_token"],
                "refresh_token": ld["refresh_token"],
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["access"]["active"] is True
        assert body["access"]["tokenType"] == "access"
        assert body["refresh"]["active"] is True
        assert body["refresh"]["tokenType"] == "refresh"


class TestLoginMetadata:
    """Login response now carries token-expiry metadata so the FE doesn't
    have to decode the JWT to schedule a refresh."""

    def test_login_response_includes_expiry_metadata(self, client, admin_user):
        resp = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["accessTokenExpiresAt"] and "T" in d["accessTokenExpiresAt"]
        assert d["accessTokenIssuedAt"] and "T" in d["accessTokenIssuedAt"]
        assert d["refreshTokenExpiresAt"] and "T" in d["refreshTokenExpiresAt"]
        assert d["refreshTokenIssuedAt"] and "T" in d["refreshTokenIssuedAt"]
        assert isinstance(d["expiresInSeconds"], int)
        assert d["expiresInSeconds"] > 0


class TestRefresh:
    """Dedicated POST /users/refresh — rotation-only endpoint."""

    def _login(self, client):
        resp = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]

    def test_refresh_rotates_tokens(self, client, admin_user):
        """Valid refresh token → fresh access + refresh pair, both
        different from the originals."""
        ld = self._login(client)
        resp = client.post(
            "/api/v3/users/refresh",
            json={"refresh_token": ld["refresh_token"]},
        )
        assert resp.status_code == 200, resp.text
        nd = resp.json()["data"]
        assert nd["_type"] == "Refresh"
        assert nd["access_token"]
        assert nd["refresh_token"]
        assert nd["access_token"] != ld["access_token"]
        assert nd["refresh_token"] != ld["refresh_token"]
        assert nd["accessTokenExpiresAt"] and "T" in nd["accessTokenExpiresAt"]
        assert nd["refreshTokenExpiresAt"] and "T" in nd["refreshTokenExpiresAt"]
        assert isinstance(nd["expiresInSeconds"], int)
        assert nd["user"]["login"] == "admin"

    def test_refresh_old_token_rejected_after_rotation(self, client, admin_user):
        """After a successful refresh, the OLD refresh token is no longer
        usable (its jti was rotated out of the user row)."""
        ld = self._login(client)
        first = client.post(
            "/api/v3/users/refresh",
            json={"refresh_token": ld["refresh_token"]},
        )
        assert first.status_code == 200

        # Re-using the original refresh now fails.
        second = client.post(
            "/api/v3/users/refresh",
            json={"refresh_token": ld["refresh_token"]},
        )
        assert second.status_code == 401, second.text

    def test_refresh_garbage_token_returns_401(self, client):
        resp = client.post(
            "/api/v3/users/refresh",
            json={"refresh_token": "not-a-jwt"},
        )
        assert resp.status_code == 401, resp.text

    def test_refresh_missing_body_returns_422(self, client):
        resp = client.post("/api/v3/users/refresh", json={})
        # Pydantic catches missing required field → 422
        assert resp.status_code == 422, resp.text

    def test_refresh_uses_access_token_as_refresh_returns_401(self, client, admin_user, admin_token):
        """Posting an access_token as refresh_token must fail — they're
        different audiences (different secrets / claims)."""
        resp = client.post(
            "/api/v3/users/refresh",
            json={"refresh_token": admin_token},
        )
        assert resp.status_code == 401, resp.text
