"""Tests for the three big behavior changes:

1. Endpoint renaming — POST creates live under ``/create`` suffix.
2. Baseline-only vs version-only write guards for M/A/T/S.
3. Baseline M/A changes propagate to active-version twins + audit log.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _create_project(client, headers, name="P"):
    return client.post(
        "/api/v3/projects/create",
        json={
            "name": name,
            "owner": "admin",
            "startDate": _iso(1),
            "endDate": _iso(120),
        },
        headers=headers,
    )


def _create_milestone(client, headers, project_id, name="M1", days_start=3, days_end=30):
    return client.post(
        f"/api/v3/projects/{project_id}/milestones/create",
        json={
            "name": name,
            "startDate": _iso(days_start),
            "endDate": _iso(days_end),
        },
        headers=headers,
    )


def _create_activity(client, headers, milestone_id, name="A1", days_start=4, days_end=20):
    return client.post(
        f"/api/v3/milestones/{milestone_id}/activities/standard/create",
        json={
            "name": name,
            "startDate": _iso(days_start),
            "endDate": _iso(days_end),
        },
        headers=headers,
    )


class TestEndpointRenaming:
    """Legacy bare POST paths no longer exist; /create is required."""

    def test_old_projects_post_is_gone(self, client, admin_user, admin_headers):
        """POST /api/v3/projects (without /create) should now 404 or 405."""
        resp = client.post(
            "/api/v3/projects",
            json={"name": "Old Style", "owner": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code in (404, 405), resp.text

    def test_new_projects_create_endpoint_works(self, client, admin_user, admin_headers):
        resp = _create_project(client, admin_headers)
        assert resp.status_code == 201, resp.text


class TestBaselineOnlyGuard:
    """Milestones and activities cannot be added to a version."""

    def _baseline_and_version(self, client, admin_headers):
        p = _create_project(client, admin_headers).json()["data"]
        mid = _create_milestone(client, admin_headers, p["id"]).json()["data"]["id"]
        _create_activity(client, admin_headers, mid)
        pub = client.post(
            f"/api/v3/projects/{p['id']}/publish", headers=admin_headers
        )
        assert pub.status_code == 200, pub.text
        v = client.post(
            f"/api/v3/projects/{p['id']}/versions/create", headers=admin_headers
        )
        assert v.status_code == 201, v.text
        return p["id"], v.json()["data"]["id"]

    def test_cannot_create_milestone_on_version(self, client, admin_user, admin_headers):
        _, vid = self._baseline_and_version(client, admin_headers)
        resp = _create_milestone(client, admin_headers, vid, name="ShouldFail")
        assert resp.status_code == 403, resp.text
        assert "version" in resp.text.lower() or "baseline" in resp.text.lower()

    def test_cannot_create_activity_on_version_milestone(
        self, client, admin_user, admin_headers, db_session
    ):
        _, vid = self._baseline_and_version(client, admin_headers)
        # Find the cloned milestone on the version.
        from app.infrastructure.db.models.milestone import MilestoneModel
        version_ms = (
            db_session.query(MilestoneModel)
            .filter(MilestoneModel.project_id == vid)
            .first()
        )
        assert version_ms is not None
        resp = _create_activity(client, admin_headers, version_ms.id, name="ShouldFail")
        assert resp.status_code == 403, resp.text


class TestVersionOnlyGuard:
    """Tasks and subtasks cannot be added on a baseline."""

    def test_cannot_create_task_on_baseline_activity(self, client, admin_user, admin_headers):
        p = _create_project(client, admin_headers).json()["data"]
        mid = _create_milestone(client, admin_headers, p["id"]).json()["data"]["id"]
        aid = _create_activity(client, admin_headers, mid).json()["data"]["id"]
        resp = client.post(
            f"/api/v3/activities/{aid}/tasks/create",
            json={
                "name": "T1",
                "type": "standard",
                "startDate": _iso(5),
                "endDate": _iso(15),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 403, resp.text


class TestPublishedBaselineEditable:
    """Baselines remain editable after publish (Phase 3)."""

    def test_patch_published_baseline(self, client, admin_user, admin_headers):
        p = _create_project(client, admin_headers).json()["data"]
        _create_milestone(client, admin_headers, p["id"])
        client.post(f"/api/v3/projects/{p['id']}/publish", headers=admin_headers)
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"name": "Renamed Post-Publish"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["name"] == "Renamed Post-Publish"


class TestBaselineToVersionPropagation:
    """Baseline M/A edits propagate to active versions and audit each row."""

    def _setup(self, client, admin_headers):
        """Return (baseline_id, milestone_id, activity_id, version_id, version_milestone_id, version_activity_id)."""
        from app.infrastructure.db.models.milestone import MilestoneModel
        from app.infrastructure.db.models.activity import ActivityModel
        # Baseline
        p = _create_project(client, admin_headers).json()["data"]
        mid = _create_milestone(client, admin_headers, p["id"]).json()["data"]["id"]
        aid = _create_activity(client, admin_headers, mid).json()["data"]["id"]
        # Publish + version
        client.post(f"/api/v3/projects/{p['id']}/publish", headers=admin_headers)
        v = client.post(
            f"/api/v3/projects/{p['id']}/versions/create", headers=admin_headers
        ).json()["data"]
        return p["id"], mid, aid, v["id"]

    def _find_twin_milestone(self, db_session, baseline_milestone_id, version_project_id):
        from app.infrastructure.db.models.milestone import MilestoneModel
        return (
            db_session.query(MilestoneModel)
            .filter(MilestoneModel.project_id == version_project_id)
            .filter(MilestoneModel.cloned_from_id == baseline_milestone_id)
            .first()
        )

    def _find_twin_activity(self, db_session, baseline_activity_id, version_project_id):
        from app.infrastructure.db.models.activity import ActivityModel
        return (
            db_session.query(ActivityModel)
            .filter(ActivityModel.project_id == version_project_id)
            .filter(ActivityModel.cloned_from_id == baseline_activity_id)
            .first()
        )

    def test_version_clone_stamps_cloned_from_id(
        self, client, admin_user, admin_headers, db_session
    ):
        _, mid, aid, vid = self._setup(client, admin_headers)
        twin_m = self._find_twin_milestone(db_session, mid, vid)
        twin_a = self._find_twin_activity(db_session, aid, vid)
        assert twin_m is not None, "version milestone should reference baseline milestone"
        assert twin_a is not None, "version activity should reference baseline activity"
        assert twin_a.milestone_id == twin_m.id, "activity attaches to the cloned milestone"

    def test_baseline_milestone_update_propagates(
        self, client, admin_user, admin_headers, db_session
    ):
        _, mid, _, vid = self._setup(client, admin_headers)
        resp = client.patch(
            f"/api/v3/milestones/{mid}",
            json={"name": "Baseline Renamed"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        # Clear session cache before re-querying.
        db_session.expire_all()
        twin = self._find_twin_milestone(db_session, mid, vid)
        assert twin.name == "Baseline Renamed"

    def test_baseline_milestone_status_does_not_propagate(
        self, client, admin_user, admin_headers, db_session
    ):
        """status is version-local — should NOT propagate."""
        _, mid, _, vid = self._setup(client, admin_headers)
        resp = client.patch(
            f"/api/v3/milestones/{mid}",
            json={"status": "completed"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        db_session.expire_all()
        twin = self._find_twin_milestone(db_session, mid, vid)
        # Version twin keeps 'not_completed' — the baseline status change
        # stays scoped to the baseline.
        assert twin.status == "not_completed"

    def test_baseline_activity_update_propagates(
        self, client, admin_user, admin_headers, db_session
    ):
        _, _, aid, vid = self._setup(client, admin_headers)
        resp = client.patch(
            f"/api/v3/activities/{aid}",
            json={"name": "Activity Renamed"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        twin = self._find_twin_activity(db_session, aid, vid)
        assert twin.name == "Activity Renamed"

    def test_baseline_new_milestone_propagates(
        self, client, admin_user, admin_headers, db_session
    ):
        """A milestone added AFTER a version exists should mirror into the version."""
        baseline_id, _, _, vid = self._setup(client, admin_headers)
        new = _create_milestone(
            client, admin_headers, baseline_id, name="LateMilestone",
            days_start=5, days_end=25,
        )
        assert new.status_code == 201, new.text
        new_id = new.json()["data"]["id"]
        db_session.expire_all()
        twin = self._find_twin_milestone(db_session, new_id, vid)
        assert twin is not None, "new baseline milestone must mint a version twin"
        assert twin.name == "LateMilestone"

    def test_baseline_milestone_delete_cascades_to_version(
        self, client, admin_user, admin_headers, db_session
    ):
        _, mid, _, vid = self._setup(client, admin_headers)
        resp = client.delete(f"/api/v3/milestones/{mid}", headers=admin_headers)
        assert resp.status_code in (200, 204), resp.text
        db_session.expire_all()
        # Version twin should also be soft-deleted.
        from app.infrastructure.db.models.milestone import MilestoneModel
        twin = (
            db_session.query(MilestoneModel)
            .filter(MilestoneModel.project_id == vid)
            .filter(MilestoneModel.cloned_from_id == mid)
            .first()
        )
        assert twin is not None
        assert twin.deleted_at is not None

    def test_baseline_cascade_does_not_touch_suspended_version(
        self, client, admin_user, admin_headers, db_session
    ):
        """Suspended versions are dormant and do NOT receive propagation."""
        baseline_id, mid, _, vid = self._setup(client, admin_headers)
        # Suspend the version.
        s = client.post(f"/api/v3/projects/{vid}/suspend", headers=admin_headers)
        assert s.status_code == 200, s.text
        # Edit the baseline milestone.
        resp = client.patch(
            f"/api/v3/milestones/{mid}",
            json={"name": "AfterSuspend"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        twin = self._find_twin_milestone(db_session, mid, vid)
        # Twin keeps its original name.
        assert twin.name != "AfterSuspend"

    def test_cascade_writes_audit_entries(
        self, client, admin_user, admin_headers, db_session
    ):
        """Each version twin touched by a baseline edit gets a cascade audit row."""
        from app.infrastructure.db.models.project_audit_log import ProjectAuditLogModel
        _, mid, _, vid = self._setup(client, admin_headers)
        client.patch(
            f"/api/v3/milestones/{mid}",
            json={"name": "AuditCheck"},
            headers=admin_headers,
        )
        cascade_rows = (
            db_session.query(ProjectAuditLogModel)
            .filter(ProjectAuditLogModel.project_id == vid)
            .filter(ProjectAuditLogModel.action == "milestone.update.cascade_from_baseline")
            .all()
        )
        assert len(cascade_rows) >= 1, "cascade audit row missing on version project"
