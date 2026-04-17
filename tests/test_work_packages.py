"""Tests for work package CRUD endpoints (basic operations).

Note: With the hierarchy enforcement, top-level work packages are
milestones and require start_date/end_date.
"""
import pytest
from datetime import datetime, timedelta, timezone


def _future(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _create_milestone(client, project_id, headers, subject="Test Milestone"):
    """Helper to create a top-level milestone."""
    resp = client.post(f"/api/v3/projects/{project_id}/work_packages", json={
        "subject": subject,
        "startDate": _future(10),
        "endDate": _future(90),
        "status": "new",
        "priority": "high",
        "doneRatio": 0,
    }, headers=headers)
    return resp


class TestCreateWorkPackage:
    """POST /api/v3/projects/{project_id}/work_packages"""

    def test_create_milestone(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        resp = _create_milestone(client, sample_project.id, admin_headers, "Implement feature")
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["subject"] == "Implement feature"
        assert data["_type"] == "WorkPackage"
        assert data["startDate"] is not None

    def test_create_wp_invalid_status(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages", json={
            "subject": "Bad status",
            "startDate": _future(10),
            "endDate": _future(90),
            "status": "invalid_status",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_wp_invalid_priority(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages", json={
            "subject": "Bad priority",
            "startDate": _future(10),
            "endDate": _future(90),
            "priority": "super_urgent",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_wp_missing_subject(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages", json={
            "startDate": _future(10),
            "endDate": _future(90),
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_wp_nonexistent_project(self, client, admin_user, admin_headers, builtin_wp_types):
        resp = client.post("/api/v3/projects/99999/work_packages", json={
            "subject": "Orphan",
            "startDate": _future(10),
            "endDate": _future(90),
        }, headers=admin_headers)
        assert resp.status_code in [400, 404]


class TestListWorkPackages:
    """GET /api/v3/projects/{project_id}/work_packages"""

    def test_list_work_packages(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        _create_milestone(client, sample_project.id, admin_headers)
        resp = client.get(
            f"/api/v3/projects/{sample_project.id}/work_packages?offset=1&pageSize=20",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] >= 1


class TestGetWorkPackage:
    """GET /api/v3/work_packages/{id}"""

    def test_get_work_package(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        create = _create_milestone(client, sample_project.id, admin_headers, "Get me")
        wp_id = create.json()["data"]["id"]
        resp = client.get(f"/api/v3/work_packages/{wp_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["subject"] == "Get me"


class TestUpdateWorkPackage:
    """PATCH /api/v3/work_packages/{id}"""

    def test_update_work_package(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        create = _create_milestone(client, sample_project.id, admin_headers, "Update me")
        wp_id = create.json()["data"]["id"]
        resp = client.patch(f"/api/v3/work_packages/{wp_id}", json={
            "subject": "Updated",
            "status": "in_progress",
            "doneRatio": 50,
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["subject"] == "Updated"


class TestDeleteWorkPackage:
    """DELETE /api/v3/work_packages/{id}"""

    def test_delete_work_package(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        create = _create_milestone(client, sample_project.id, admin_headers, "Delete me")
        wp_id = create.json()["data"]["id"]
        resp = client.delete(f"/api/v3/work_packages/{wp_id}", headers=admin_headers)
        assert resp.status_code in [200, 204]
