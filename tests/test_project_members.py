"""Tests for project member management endpoints."""
import pytest


class TestAddMember:
    """POST /api/v3/projects/{project_id}/memberships"""

    def test_add_member(self, client, admin_user, member_user, admin_headers, sample_project):
        resp = client.post(f"/api/v3/projects/{sample_project.id}/memberships/create", json={
            "user": {"id": member_user.id},
            "roles": [],
        }, headers=admin_headers)
        assert resp.status_code == 201

    def test_add_member_duplicate(self, client, admin_user, member_user, admin_headers, sample_project):
        client.post(f"/api/v3/projects/{sample_project.id}/memberships/create", json={
            "user": {"id": member_user.id},
            "roles": [],
        }, headers=admin_headers)
        resp = client.post(f"/api/v3/projects/{sample_project.id}/memberships/create", json={
            "user": {"id": member_user.id},
            "roles": [],
        }, headers=admin_headers)
        assert resp.status_code == 409


class TestListMembers:
    """GET /api/v3/projects/{project_id}/memberships"""

    def test_list_members(self, client, admin_user, member_user, admin_headers, sample_project):
        client.post(f"/api/v3/projects/{sample_project.id}/memberships/create", json={
            "user": {"id": member_user.id}, "roles": [],
        }, headers=admin_headers)
        resp = client.get(f"/api/v3/projects/{sample_project.id}/memberships", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] >= 1


class TestDeleteMember:
    """DELETE /api/v3/memberships/{id}"""

    def test_delete_member(self, client, admin_user, member_user, admin_headers, sample_project):
        create = client.post(f"/api/v3/projects/{sample_project.id}/memberships/create", json={
            "user": {"id": member_user.id}, "roles": [],
        }, headers=admin_headers)
        member_id = create.json()["data"]["id"]
        resp = client.delete(
            f"/api/v3/memberships/{member_id}",
            headers=admin_headers,
        )
        assert resp.status_code in [200, 204]
