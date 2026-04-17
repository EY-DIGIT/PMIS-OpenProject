"""Tests for project management endpoints."""
import pytest


class TestCreateProject:
    """POST /api/v3/projects"""

    def test_create_project(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/projects", json={
            "identifier": "proj-1",
            "name": "Project One",
            "description": "First project",
            "active": True,
            "public": False,
        }, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["identifier"] == "proj-1"
        assert data["name"] == "Project One"
        assert data["_type"] == "Project"

    def test_create_project_with_new_fields(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/projects", json={
            "identifier": "proj-new",
            "name": "New Fields Project",
            "status": "in_progress",
            "category": "MSAP",
        }, headers=admin_headers)
        assert resp.status_code == 201

    def test_create_project_duplicate_identifier(self, client, admin_user, admin_headers, sample_project):
        resp = client.post("/api/v3/projects", json={
            "identifier": "test-project",
            "name": "Duplicate",
        }, headers=admin_headers)
        assert resp.status_code == 409

    def test_create_project_invalid_status(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/projects", json={
            "identifier": "bad-status",
            "name": "Bad Status",
            "status": "invalid_status",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_project_invalid_category(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/projects", json={
            "identifier": "bad-cat",
            "name": "Bad Category",
            "category": "INVALID",
        }, headers=admin_headers)
        assert resp.status_code == 422


class TestListProjects:
    """GET /api/v3/projects"""

    def test_list_projects(self, client, admin_user, admin_headers, sample_project):
        resp = client.get("/api/v3/projects?offset=1&pageSize=20", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["_type"] == "Collection"
        assert body["total"] >= 1

    def test_list_projects_filter_active(self, client, admin_user, admin_headers, sample_project):
        resp = client.get("/api/v3/projects?active=true", headers=admin_headers)
        assert resp.status_code == 200


class TestGetProject:
    """GET /api/v3/projects/{id}"""

    def test_get_project(self, client, admin_user, admin_headers, sample_project):
        resp = client.get(f"/api/v3/projects/{sample_project.id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["identifier"] == "test-project"

    def test_get_nonexistent_project(self, client, admin_user, admin_headers):
        resp = client.get("/api/v3/projects/99999", headers=admin_headers)
        assert resp.status_code in [200, 404]


class TestUpdateProject:
    """PATCH /api/v3/projects/{id}"""

    def test_update_project(self, client, admin_user, admin_headers, sample_project):
        resp = client.patch(f"/api/v3/projects/{sample_project.id}", json={
            "name": "Updated Project",
            "active": False,
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Updated Project"


class TestDeleteProject:
    """DELETE /api/v3/projects/{id}"""

    def test_delete_project(self, client, admin_user, admin_headers, sample_project):
        resp = client.delete(f"/api/v3/projects/{sample_project.id}", headers=admin_headers)
        assert resp.status_code in [200, 204]
