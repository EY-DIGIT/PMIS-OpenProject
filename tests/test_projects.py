"""Tests for project management endpoints.

After the UUID + ProjectCode migration, every URL uses ``{project_uuid}``
(which is the project's ``id`` — a UUID string). The server generates
``id`` and ``projectCode`` on insert; neither is accepted in the request
body (except for PUT-upsert, where the id comes from the URL).
"""
import pytest


class TestCreateProject:
    """POST /api/v3/projects/create"""

    def test_create_project(self, client, admin_user, admin_headers):
        resp = client.post(
            "/api/v3/projects/create",
            json={
                "name": "Project One",
                "description": "First project",
                "active": True,
                "public": False,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Project One"
        assert data["_type"] == "Project"
        # Server-generated public handles:
        assert "id" in data and data["id"]
        assert "projectCode" in data and data["projectCode"].startswith("UIDAI-PR")

    def test_create_project_with_new_fields(self, client, admin_user, admin_headers):
        resp = client.post(
            "/api/v3/projects/create",
            json={
                "name": "New Fields Project",
                "status": "new",
                "category": "MSAP",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["category"] == "MSAP"
        assert data["isVersion"] is False


class TestSaveProject:
    """POST /api/v3/projects/{id}/save — Step-1 'Save Project' button."""

    def _attach_milestone(self, db_session, project):
        """Directly insert a minimal milestone so the save guard is satisfied."""
        from datetime import datetime, timezone, timedelta
        from app.infrastructure.db.models.milestone import MilestoneModel
        now = datetime.now(timezone.utc)
        # sample_project has no start_date; set it so downstream queries stay sane.
        from app.infrastructure.db.models.project import ProjectModel
        db_session.query(ProjectModel).filter_by(id=project.id).update(
            {"start_date": now + timedelta(days=1), "end_date": now + timedelta(days=90)}
        )
        db_session.add(MilestoneModel(
            project_id=project.id,
            name="M1",
            start_date=now + timedelta(days=2),
            end_date=now + timedelta(days=60),
            position=0,
        ))
        db_session.commit()

    def test_save_without_milestone_rejected(
        self, client, admin_user, admin_headers, sample_project
    ):
        resp = client.post(f"/api/v3/projects/{sample_project.id}/save", headers=admin_headers)
        assert resp.status_code == 422
        body = resp.json()
        assert "milestone" in body["error"]["message"].lower()

    def test_save_with_milestone_flips_new_to_draft(
        self, client, admin_user, admin_headers, db_session, sample_project
    ):
        self._attach_milestone(db_session, sample_project)
        resp = client.post(f"/api/v3/projects/{sample_project.id}/save", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "draft"

    def test_save_is_idempotent_after_draft(
        self, client, admin_user, admin_headers, db_session, sample_project
    ):
        self._attach_milestone(db_session, sample_project)
        first = client.post(f"/api/v3/projects/{sample_project.id}/save", headers=admin_headers)
        assert first.status_code == 200 and first.json()["data"]["status"] == "draft"
        second = client.post(f"/api/v3/projects/{sample_project.id}/save", headers=admin_headers)
        assert second.status_code == 200
        assert second.json()["data"]["status"] == "draft"

    def test_save_nonexistent_returns_404(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/projects/99999/save", headers=admin_headers)
        assert resp.status_code == 404


class TestPublishProject:
    """POST /api/v3/projects/{uuid}/publish"""

    def test_publish_new_project(self, client, admin_user, admin_headers, sample_project):
        resp = client.post(
            f"/api/v3/projects/{sample_project.id}/publish",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "published"

    def test_publish_is_idempotent_rejected(self, client, admin_user, admin_headers, sample_project):
        first = client.post(f"/api/v3/projects/{sample_project.id}/publish", headers=admin_headers)
        assert first.status_code == 200
        second = client.post(f"/api/v3/projects/{sample_project.id}/publish", headers=admin_headers)
        assert second.status_code == 409

    def test_publish_keeps_baseline_patchable(self, client, admin_user, admin_headers, sample_project):
        """Baselines remain editable after publish — changes propagate to active versions."""
        client.post(f"/api/v3/projects/{sample_project.id}/publish", headers=admin_headers)
        resp = client.patch(
            f"/api/v3/projects/{sample_project.id}",
            json={"name": "Renamed After Publish"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["name"] == "Renamed After Publish"


class TestCloseProject:
    """POST /api/v3/projects/{uuid}/close"""

    def test_close_project(self, client, admin_user, admin_headers, sample_project):
        resp = client.post(
            f"/api/v3/projects/{sample_project.id}/close",
            json={"reason": "no longer needed"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "closed"


class TestCreateVersion:
    """POST /api/v3/projects/{uuid}/versions/create"""

    def test_create_version_from_published_baseline(
        self, client, admin_user, admin_headers, sample_project
    ):
        client.post(f"/api/v3/projects/{sample_project.id}/publish", headers=admin_headers)
        resp = client.post(
            f"/api/v3/projects/{sample_project.id}/versions/create",
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["isVersion"] is True
        assert data["versionNo"] == 1
        # Each version row gets a fresh id (UUID) + its own projectCode.
        assert data["id"] != sample_project.id
        assert data["projectCode"] != sample_project.project_code

    def test_create_version_rejects_unpublished(
        self, client, admin_user, admin_headers, sample_project
    ):
        resp = client.post(
            f"/api/v3/projects/{sample_project.id}/versions/create",
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_one_active_version_per_baseline(
        self, client, admin_user, admin_headers, sample_project
    ):
        client.post(f"/api/v3/projects/{sample_project.id}/publish", headers=admin_headers)
        first = client.post(
            f"/api/v3/projects/{sample_project.id}/versions/create",
            headers=admin_headers,
        )
        assert first.status_code == 201
        second = client.post(
            f"/api/v3/projects/{sample_project.id}/versions/create",
            headers=admin_headers,
        )
        assert second.status_code == 409


class TestUpsert:
    """PUT /api/v3/projects/{uuid} — wizard idempotent create-or-update."""

    def test_upsert_inserts_on_first_call(self, client, admin_user, admin_headers):
        import uuid as _uuid
        new_uuid = str(_uuid.uuid4())
        resp = client.put(
            f"/api/v3/projects/{new_uuid}",
            json={"name": "Wizard Demo", "owner": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["id"] == new_uuid
        assert data["_created"] is True
        assert data["projectCode"].startswith("UIDAI-PR")

    def test_upsert_updates_on_second_call(self, client, admin_user, admin_headers):
        import uuid as _uuid
        new_uuid = str(_uuid.uuid4())
        client.put(
            f"/api/v3/projects/{new_uuid}",
            json={"name": "Wizard v1", "owner": "admin"},
            headers=admin_headers,
        )
        resp = client.put(
            f"/api/v3/projects/{new_uuid}",
            json={"name": "Wizard v2", "owner": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "Wizard v2"
        assert data["_created"] is False
        assert data["id"] == new_uuid


class TestDeleteCascadesToVersions:
    """DELETE /api/v3/projects/{id} should also soft-delete all live versions
    when the target is a baseline. Deleting a version alone must NOT touch
    the baseline or sibling versions."""

    def _publish(self, client, headers, pid):
        r = client.post(f"/api/v3/projects/{pid}/publish", headers=headers)
        assert r.status_code == 200, r.text

    def _new_version(self, client, headers, baseline_id):
        r = client.post(f"/api/v3/projects/{baseline_id}/versions/create", headers=headers)
        assert r.status_code == 201, r.text
        return r.json()["data"]["id"]

    def test_delete_baseline_with_no_versions(
        self, client, admin_user, admin_headers, sample_project
    ):
        resp = client.delete(
            f"/api/v3/projects/{sample_project.id}", headers=admin_headers
        )
        assert resp.status_code == 204
        # 404 after delete
        g = client.get(f"/api/v3/projects/{sample_project.id}", headers=admin_headers)
        assert g.status_code == 404

    def test_delete_baseline_cascades_to_versions(
        self, client, admin_user, admin_headers, sample_project
    ):
        # Version 1 — live, active
        self._publish(client, admin_headers, sample_project.id)
        v1_id = self._new_version(client, admin_headers, sample_project.id)
        # Suspend v1 so we can create v2
        s = client.post(f"/api/v3/projects/{v1_id}/suspend", headers=admin_headers)
        assert s.status_code == 200
        # Version 2 — new, active
        v2_id = self._new_version(client, admin_headers, sample_project.id)

        # Soft-delete the baseline. Should take v1 and v2 with it.
        resp = client.delete(
            f"/api/v3/projects/{sample_project.id}", headers=admin_headers
        )
        assert resp.status_code == 204

        for proj_id, label in (
            (sample_project.id, "baseline"),
            (v1_id, "v1"),
            (v2_id, "v2"),
        ):
            g = client.get(f"/api/v3/projects/{proj_id}", headers=admin_headers)
            assert g.status_code == 404, f"{label} should be 404 after baseline delete"

    def test_delete_version_does_not_touch_baseline_or_siblings(
        self, client, admin_user, admin_headers, sample_project
    ):
        self._publish(client, admin_headers, sample_project.id)
        v1_id = self._new_version(client, admin_headers, sample_project.id)
        # Suspend v1 so we can spawn v2
        client.post(f"/api/v3/projects/{v1_id}/suspend", headers=admin_headers)
        v2_id = self._new_version(client, admin_headers, sample_project.id)

        # Delete just v2 — baseline + v1 must stay live.
        resp = client.delete(f"/api/v3/projects/{v2_id}", headers=admin_headers)
        assert resp.status_code == 204

        assert (
            client.get(f"/api/v3/projects/{v2_id}", headers=admin_headers).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v3/projects/{sample_project.id}", headers=admin_headers
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/v3/projects/{v1_id}", headers=admin_headers).status_code
            == 200
        )
