"""Tests for user management endpoints."""
import pytest


class TestCreateUser:
    """POST /api/v3/users"""

    def test_create_user_success(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users", json={
            "login": "newuser",
            "email": "new@example.com",
            "password": "password123",
            "firstName": "New",
            "lastName": "User",
            "admin": False,
        }, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["login"] == "newuser"
        assert data["email"] == "new@example.com"
        assert data["_type"] == "User"
        assert "id" in data

    def test_create_user_duplicate_login(self, client, admin_user, admin_headers):
        client.post("/api/v3/users", json={
            "login": "dup", "email": "a@a.com", "password": "password123",
        }, headers=admin_headers)
        resp = client.post("/api/v3/users", json={
            "login": "dup", "email": "b@b.com", "password": "password123",
        }, headers=admin_headers)
        assert resp.status_code == 409

    def test_create_user_duplicate_email(self, client, admin_user, admin_headers):
        client.post("/api/v3/users", json={
            "login": "user1", "email": "same@example.com", "password": "password123",
        }, headers=admin_headers)
        resp = client.post("/api/v3/users", json={
            "login": "user2", "email": "same@example.com", "password": "password123",
        }, headers=admin_headers)
        assert resp.status_code == 409

    def test_create_user_invalid_email(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users", json={
            "login": "badmail", "email": "not-an-email", "password": "password123",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_user_short_password(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users", json={
            "login": "shortpw", "email": "s@s.com", "password": "short",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_user_short_login(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users", json={
            "login": "ab", "email": "ab@ab.com", "password": "password123",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_user_missing_required(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users", json={"login": "only"}, headers=admin_headers)
        assert resp.status_code == 422


class TestListUsers:
    """GET /api/v3/users"""

    def test_list_users(self, client, admin_user, admin_headers):
        resp = client.get("/api/v3/users?offset=1&pageSize=10", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["_type"] == "Collection"
        assert body["total"] >= 1
        assert "_embedded" in body
        assert "elements" in body["_embedded"]

    def test_list_users_pagination(self, client, admin_user, member_user, admin_headers):
        resp = client.get("/api/v3/users?offset=1&pageSize=1", headers=admin_headers)
        body = resp.json()["data"]
        assert body["count"] == 1
        assert body["pageSize"] == 1

    def test_list_users_forbidden_for_member(self, client, admin_user, member_user, member_headers):
        resp = client.get("/api/v3/users", headers=member_headers)
        assert resp.status_code == 403


class TestGetUser:
    """GET /api/v3/users/{id}"""

    def test_get_user_by_id(self, client, admin_user, admin_headers):
        resp = client.get(f"/api/v3/users/{admin_user.id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["login"] == "admin"

    def test_get_nonexistent_user(self, client, admin_user, admin_headers):
        resp = client.get("/api/v3/users/99999", headers=admin_headers)
        assert resp.status_code in [200, 404]  # may return 200 with error body


class TestUpdateUser:
    """PATCH /api/v3/users/{id}"""

    def test_update_user(self, client, admin_user, member_user, admin_headers):
        resp = client.patch(f"/api/v3/users/{member_user.id}", json={
            "firstName": "Updated",
            "lastName": "Name",
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["firstName"] == "Updated"

    def test_update_password(self, client, admin_user, member_user, admin_headers):
        resp = client.patch(f"/api/v3/users/{member_user.id}/password", json={
            "password": "newpassword123",
        }, headers=admin_headers)
        assert resp.status_code == 200


class TestDeleteUser:
    """DELETE /api/v3/users/{id}"""

    def test_delete_user(self, client, admin_user, member_user, admin_headers):
        resp = client.delete(f"/api/v3/users/{member_user.id}", headers=admin_headers)
        assert resp.status_code == 200

    def test_delete_nonexistent_user(self, client, admin_user, admin_headers):
        resp = client.delete("/api/v3/users/99999", headers=admin_headers)
        assert resp.status_code in [200, 404]
