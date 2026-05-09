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

    def test_create_project_accepts_optional_owner(self, client, admin_user, admin_headers):
        # Doc 38: ``category`` / ``isPublic`` were removed from the request
        # schema (Option B deprecation). Owner is still accepted.
        resp = client.post(
            "/api/v3/projects/create",
            json={
                "name": "New Fields Project",
                "status": "new",
                "owner": "tmd2",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["owner"] == "tmd2"


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


# Doc 33: TestCreateVersion removed — /versions/create no longer exists.


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


class TestDeleteProject:
    """DELETE /api/v3/projects/{id}. Doc 33: cascade-to-versions behavior
    is gone since versions no longer exist."""

    def test_delete_project(
        self, client, admin_user, admin_headers, sample_project
    ):
        resp = client.delete(
            f"/api/v3/projects/{sample_project.id}", headers=admin_headers
        )
        assert resp.status_code == 204
        # 404 after delete
        g = client.get(f"/api/v3/projects/{sample_project.id}", headers=admin_headers)
        assert g.status_code == 404


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


class TestListScopedToCaller:
    """Doc 44 round 4: GET /api/v3/projects filters to only the
    projects the caller is associated with. admin / super_admin still
    see everything; everyone else sees the union of:
      - project_members rows for their user_id
      - project-scoped user_role_assignments rows
      - org-scoped user_role_assignments rows joined to project_vendors
    """

    def test_admin_sees_all_projects(
        self, client, admin_user, admin_headers,
    ):
        """admin holds the legacy 'admin' role; user_has_admin_role
        returns True; no scope filter applied."""
        a = _create_baseline(client, admin_headers, name="Scope-Test-A")
        b = _create_baseline(client, admin_headers, name="Scope-Test-B")
        resp = client.get("/api/v3/projects?pageSize=100", headers=admin_headers)
        assert resp.status_code == 200
        ids = {p["id"] for p in resp.json()["data"]["_embedded"]["elements"]}
        assert a["id"] in ids and b["id"] in ids

    def test_member_sees_only_assigned_projects_via_project_members(
        self, client, admin_user, admin_headers, member_user, member_headers,
        db_session,
    ):
        """A non-admin caller with a project_members row for project A
        but not for project B sees only A in the listing.

        Doc 44 round 8: non-admin tiers see only published projects, so
        flip A and B to ``status='published'`` before the assertion —
        otherwise the new pre-publish hide would suppress both."""
        from app.infrastructure.db.models.project import ProjectModel
        from app.infrastructure.db.models.project_member import (
            ProjectMemberModel,
        )
        a = _create_baseline(client, admin_headers, name="Scope-PM-A")
        b = _create_baseline(client, admin_headers, name="Scope-PM-B")
        db_session.add(ProjectMemberModel(
            project_id=a["id"], user_id=member_user.id, roles=[],
        ))
        for pid in (a["id"], b["id"]):
            db_session.query(ProjectModel).filter(ProjectModel.id == pid).update(
                {"status": "published"},
            )
        db_session.commit()

        resp = client.get("/api/v3/projects?pageSize=100", headers=member_headers)
        assert resp.status_code == 200, resp.text
        ids = {p["id"] for p in resp.json()["data"]["_embedded"]["elements"]}
        assert a["id"] in ids
        assert b["id"] not in ids

    def test_member_sees_project_via_user_role_assignments(
        self, client, admin_user, admin_headers, member_user, member_headers,
        db_session,
    ):
        """A doc-41 project-scoped user_role_assignments row also makes
        the project visible — it's a separate path from project_members
        but counts the same way for scope.

        Doc 44 round 8: non-admin tiers see only published projects, so
        flip both projects to ``status='published'`` before asserting."""
        from app.infrastructure.db.models.project import ProjectModel
        from app.infrastructure.db.models.role import RoleModel
        from app.infrastructure.db.models.user_role_assignment import (
            UserRoleAssignmentModel,
        )
        a = _create_baseline(client, admin_headers, name="Scope-URA-A")
        b = _create_baseline(client, admin_headers, name="Scope-URA-B")
        pm_role_id = (
            db_session.query(RoleModel)
            .filter(RoleModel.name == "project_member").one().id
        )
        db_session.add(UserRoleAssignmentModel(
            user_id=member_user.id, role_id=pm_role_id, project_id=a["id"],
        ))
        for pid in (a["id"], b["id"]):
            db_session.query(ProjectModel).filter(ProjectModel.id == pid).update(
                {"status": "published"},
            )
        db_session.commit()

        resp = client.get("/api/v3/projects?pageSize=100", headers=member_headers)
        assert resp.status_code == 200, resp.text
        ids = {p["id"] for p in resp.json()["data"]["_embedded"]["elements"]}
        assert a["id"] in ids
        assert b["id"] not in ids

    def test_member_with_no_assignments_sees_no_projects(
        self, client, admin_user, admin_headers, member_user, member_headers,
    ):
        """A non-admin caller with no membership and no role-assignment
        rows on any project gets an empty listing (instead of every
        project as before)."""
        _create_baseline(client, admin_headers, name="Scope-Empty-A")
        _create_baseline(client, admin_headers, name="Scope-Empty-B")
        resp = client.get("/api/v3/projects?pageSize=100", headers=member_headers)
        assert resp.status_code == 200, resp.text
        elements = resp.json()["data"]["_embedded"]["elements"]
        # Filter to the projects we created in this test (other tests'
        # fixtures may add background projects).
        assert elements == [] or all(
            p["name"] not in ("Scope-Empty-A", "Scope-Empty-B")
            for p in elements
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
