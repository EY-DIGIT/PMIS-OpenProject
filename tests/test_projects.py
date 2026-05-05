"""Tests for project management endpoints.

After the UUID + ProjectCode migration, every URL uses ``{project_uuid}``
(which is the project's ``id`` — a UUID string). The server generates
``id`` and ``projectCode`` on insert; neither is accepted in the request
body (except for PUT-upsert, where the id comes from the URL).
"""
import pytest


def _attach_milestone_with_activity(db_session, project):
    """Doc 27 publish gate: a project needs at least one milestone and
    every milestone needs at least one activity to be publishable. This
    helper sets the project's date window plus one milestone with one
    activity in a single shot."""
    from datetime import datetime, timezone, timedelta
    from app.infrastructure.db.models.activity import ActivityModel
    from app.infrastructure.db.models.milestone import MilestoneModel
    from app.infrastructure.db.models.project import ProjectModel
    now = datetime.now(timezone.utc)
    db_session.query(ProjectModel).filter_by(id=project.id).update(
        {"start_date": now + timedelta(days=1), "end_date": now + timedelta(days=90)}
    )
    m = MilestoneModel(
        project_id=project.id,
        name="M1",
        start_date=now + timedelta(days=2),
        end_date=now + timedelta(days=60),
        position=0,
    )
    db_session.add(m)
    db_session.flush()
    db_session.add(ActivityModel(
        project_id=project.id,
        milestone_id=m.id,
        name="A1",
        type="standard",
        start_date=now + timedelta(days=3),
        end_date=now + timedelta(days=50),
        position=0,
    ))
    db_session.commit()


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
                "owner": "tmd1",
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
                "owner": "tmd2",
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

    def test_publish_new_project(self, client, admin_user, admin_headers, db_session, sample_project):
        _attach_milestone_with_activity(db_session, sample_project)
        resp = client.post(
            f"/api/v3/projects/{sample_project.id}/publish",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "published"

    def test_publish_is_idempotent_rejected(self, client, admin_user, admin_headers, db_session, sample_project):
        _attach_milestone_with_activity(db_session, sample_project)
        first = client.post(f"/api/v3/projects/{sample_project.id}/publish", headers=admin_headers)
        assert first.status_code == 200
        second = client.post(f"/api/v3/projects/{sample_project.id}/publish", headers=admin_headers)
        assert second.status_code == 409

    def test_publish_keeps_baseline_patchable(self, client, admin_user, admin_headers, db_session, sample_project):
        """Baselines remain editable after publish (per the editable-field
        whitelist in transitions.py). Propagation of those edits to active
        versions is exercised separately in test_baseline_version_propagation.py."""
        _attach_milestone_with_activity(db_session, sample_project)
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
        self, client, admin_user, admin_headers, db_session, sample_project
    ):
        _attach_milestone_with_activity(db_session, sample_project)
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
        self, client, admin_user, admin_headers, db_session, sample_project
    ):
        _attach_milestone_with_activity(db_session, sample_project)
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
            json={"name": "Wizard Demo", "owner": "tmd1"},
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
            json={"name": "Wizard v1", "owner": "tmd1"},
            headers=admin_headers,
        )
        resp = client.put(
            f"/api/v3/projects/{new_uuid}",
            json={"name": "Wizard v2", "owner": "tmd1"},
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

    def _publish(self, client, headers, db_session, project):
        # Doc 27: a project must have ≥1 milestone with ≥1 activity to publish.
        _attach_milestone_with_activity(db_session, project)
        r = client.post(f"/api/v3/projects/{project.id}/publish", headers=headers)
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
        self, client, admin_user, admin_headers, db_session, sample_project
    ):
        # Version 1 — live, active
        self._publish(client, admin_headers, db_session, sample_project)
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
        self, client, admin_user, admin_headers, db_session, sample_project
    ):
        self._publish(client, admin_headers, db_session, sample_project)
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


# ---------------------------------------------------------------------------
# Doc 17/18 contract coverage: sort order, /projects/all, delete side-effects,
# inclusive end-date.
# ---------------------------------------------------------------------------


def _create_baseline(client, headers, *, name, days_offset=0):
    """Create a project via the API. days_offset shifts the start date so
    callers can ensure distinct created_at timestamps when they need to
    assert sort order."""
    from datetime import datetime, timedelta, timezone
    iso = lambda d: (
        datetime.now(timezone.utc) + timedelta(days=d)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.post(
        "/api/v3/projects/create",
        json={
            "name": name,
            "owner": "tmd1",
            "startDate": iso(2 + days_offset),
            "endDate": iso(60 + days_offset),
        },
        headers=headers,
    )
    assert resp.status_code == 201, (name, resp.text)
    return resp.json()["data"]


class TestListNewestFirstSort:
    """`GET /projects` returns rows in `created_at DESC, id DESC` order
    so the FE Search Project table shows the newest project at row 0
    (doc 17 §1)."""

    def test_projects_list_newest_first(self, client, admin_user, admin_headers):
        first  = _create_baseline(client, admin_headers, name="ZZZ-First")
        second = _create_baseline(client, admin_headers, name="AAA-Second")
        third  = _create_baseline(client, admin_headers, name="MMM-Third")

        resp = client.get("/api/v3/projects", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["data"]["_embedded"]["elements"]
        # Three created in the test, plus whatever sample_project fixtures
        # may exist. Filter to the ones we just created.
        ids = [p["id"] for p in items if p["id"] in (first["id"], second["id"], third["id"])]
        assert ids == [third["id"], second["id"], first["id"]], (
            "Expected newest-first ordering"
        )


class TestProjectsAllEndpoint:
    """`GET /projects/all` returns soft-deleted rows too (doc 17 §6)."""

    def test_all_includes_deleted_with_deletedAt_set(
        self, client, admin_user, admin_headers,
    ):
        live = _create_baseline(client, admin_headers, name="Live Project")
        gone = _create_baseline(client, admin_headers, name="Deleted Project")

        # Soft-delete one.
        d = client.delete(f"/api/v3/projects/{gone['id']}", headers=admin_headers)
        assert d.status_code == 204

        # Default list excludes the deleted one.
        live_resp = client.get("/api/v3/projects", headers=admin_headers)
        live_ids = {p["id"] for p in live_resp.json()["data"]["_embedded"]["elements"]}
        assert live["id"] in live_ids
        assert gone["id"] not in live_ids

        # /projects/all includes both.
        all_resp = client.get("/api/v3/projects/all", headers=admin_headers)
        assert all_resp.status_code == 200, all_resp.text
        all_items = all_resp.json()["data"]["_embedded"]["elements"]
        all_ids = {p["id"] for p in all_items}
        assert live["id"] in all_ids
        assert gone["id"] in all_ids

        # The deleted row carries deletedAt populated.
        deleted_row = [p for p in all_items if p["id"] == gone["id"]][0]
        assert deleted_row["deletedAt"] is not None

    def test_delete_flips_status_to_closed(
        self, client, admin_user, admin_headers,
    ):
        """Soft-delete now also stamps status='closed' so the post-delete
        view reflects a terminal state (doc 17 §6)."""
        p = _create_baseline(client, admin_headers, name="To Be Closed")
        assert p["status"] == "new"
        client.delete(f"/api/v3/projects/{p['id']}", headers=admin_headers)
        all_items = client.get(
            "/api/v3/projects/all", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"]
        deleted = [x for x in all_items if x["id"] == p["id"]][0]
        assert deleted["status"] == "closed"

    def test_delete_disconnects_vendor_mappings(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Soft-delete drops project_vendors rows (doc 17 §6)."""
        from app.infrastructure.db.models.vendor import VendorModel
        from app.infrastructure.db.models.project_vendor import ProjectVendorModel
        v = VendorModel(name="VFor-Disconnect", active=True)
        db_session.add(v)
        db_session.commit()
        # Create project with the vendor attached.
        from datetime import datetime, timedelta, timezone
        iso = lambda d: (
            datetime.now(timezone.utc) + timedelta(days=d)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        p = client.post(
            "/api/v3/projects/create",
            json={
                "name": "Mapped P", "owner": "tmd1",
                "startDate": iso(2), "endDate": iso(30),
                "vendorIds": [v.id],
            },
            headers=admin_headers,
        ).json()["data"]
        # Confirm mapping row exists.
        mapping = (
            db_session.query(ProjectVendorModel)
            .filter_by(project_id=p["id"]).count()
        )
        assert mapping == 1

        # Delete and verify the mapping was dropped.
        client.delete(f"/api/v3/projects/{p['id']}", headers=admin_headers)
        db_session.expire_all()
        post = (
            db_session.query(ProjectVendorModel)
            .filter_by(project_id=p["id"]).count()
        )
        assert post == 0


class TestProjectInclusiveDateValidation:
    """`end_date == start_date` is now allowed on projects (doc 17 §2)."""

    def test_create_with_equal_start_and_end_succeeds(
        self, client, admin_user, admin_headers,
    ):
        from datetime import datetime, timedelta, timezone
        same_date = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        resp = client.post(
            "/api/v3/projects/create",
            json={
                "name": "Single-Day Project", "owner": "tmd1",
                "startDate": same_date, "endDate": same_date,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text

    def test_create_with_end_before_start_still_rejected(
        self, client, admin_user, admin_headers,
    ):
        """Strictly-before is still a 422 — only equal is the relaxation."""
        from datetime import datetime, timedelta, timezone
        start = (datetime.now(timezone.utc) + timedelta(days=10)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        end = (datetime.now(timezone.utc) + timedelta(days=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        resp = client.post(
            "/api/v3/projects/create",
            json={
                "name": "Backwards", "owner": "tmd1",
                "startDate": start, "endDate": end,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestProjectPastStartDate:
    """Doc 24 part 1: ``startDate`` is allowed in the past (project entered
    after work has already begun). ``endDate`` keeps the future-only rule."""

    def test_past_start_with_future_end_succeeds(
        self, client, admin_user, admin_headers,
    ):
        from datetime import datetime, timedelta, timezone
        past_start = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        future_end = (
            datetime.now(timezone.utc) + timedelta(days=60)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = client.post(
            "/api/v3/projects/create",
            json={
                "name": "Already started", "owner": "tmd1",
                "startDate": past_start, "endDate": future_end,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text

    def test_past_end_still_rejected(
        self, client, admin_user, admin_headers,
    ):
        from datetime import datetime, timedelta, timezone
        past_start = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        past_end = (
            datetime.now(timezone.utc) - timedelta(days=5)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = client.post(
            "/api/v3/projects/create",
            json={
                "name": "Already finished", "owner": "tmd1",
                "startDate": past_start, "endDate": past_end,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "future" in resp.text.lower()
