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
    """Token introspection endpoint."""

    def test_introspect_valid_token(self, client, admin_user, admin_token):
        resp = client.post("/api/v3/users/introspect", json={
            "access_token": admin_token,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["active"] is True

    def test_introspect_no_token(self, client):
        resp = client.post("/api/v3/users/introspect", json={})
        assert resp.status_code in [400, 401, 422]
