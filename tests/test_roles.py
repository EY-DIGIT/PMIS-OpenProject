"""Tests for role management endpoints."""
import pytest


class TestCreateRole:
    """POST /api/v3/roles"""

    def test_create_role(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/roles", json={
            "name": "Editor",
            "permissions": ["projects:read", "projects:update"],
            "builtin": False,
        }, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Editor"
        assert data["_type"] == "Role"

    def test_create_duplicate_role(self, client, admin_user, admin_headers):
        client.post("/api/v3/roles", json={
            "name": "DupRole", "permissions": [], "builtin": False,
        }, headers=admin_headers)
        resp = client.post("/api/v3/roles", json={
            "name": "DupRole", "permissions": [], "builtin": False,
        }, headers=admin_headers)
        assert resp.status_code == 409

    def test_create_role_forbidden_without_auth(self, client, admin_user):
        resp = client.post("/api/v3/roles", json={
            "name": "NoAuth", "permissions": [],
        })
        assert resp.status_code == 401


class TestListRoles:
    """GET /api/v3/roles"""

    def test_list_roles(self, client, admin_user, admin_headers):
        client.post("/api/v3/roles", json={
            "name": "ListTest", "permissions": [], "builtin": False,
        }, headers=admin_headers)
        resp = client.get("/api/v3/roles?offset=1&pageSize=20", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["_type"] == "Collection"
        assert body["total"] >= 1


class TestGetRole:
    """GET /api/v3/roles/{id}"""

    def test_get_role(self, client, admin_user, admin_headers):
        create = client.post("/api/v3/roles", json={
            "name": "GetMe", "permissions": [], "builtin": False,
        }, headers=admin_headers)
        role_id = create.json()["data"]["id"]
        resp = client.get(f"/api/v3/roles/{role_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "GetMe"


class TestUpdateRole:
    """PATCH /api/v3/roles/{id}"""

    def test_update_role(self, client, admin_user, admin_headers):
        create = client.post("/api/v3/roles", json={
            "name": "UpdateMe", "permissions": [], "builtin": False,
        }, headers=admin_headers)
        role_id = create.json()["data"]["id"]
        resp = client.patch(f"/api/v3/roles/{role_id}", json={
            "name": "Updated",
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated"


class TestDeleteRole:
    """DELETE /api/v3/roles/{id}"""

    def test_delete_role(self, client, admin_user, admin_headers):
        create = client.post("/api/v3/roles", json={
            "name": "DeleteMe", "permissions": [], "builtin": False,
        }, headers=admin_headers)
        role_id = create.json()["data"]["id"]
        resp = client.delete(f"/api/v3/roles/{role_id}", headers=admin_headers)
        assert resp.status_code in [200, 204]
