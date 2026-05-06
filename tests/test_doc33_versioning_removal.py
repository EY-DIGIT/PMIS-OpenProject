"""Doc 33 — versioning removal + vendor role + audit expansion.

Stage 1 of the doc 33 work covered:
- Removed /versions/create + /suspend endpoints, the ``suspended`` status,
  and the entire baseline_version_sync propagation module.
- Tasks + subtasks are now writable directly on the project (no longer
  version-only).
- New ``vendor`` role seeded with project-content-edit permissions,
  excluding lifecycle / RBAC / master-data.
- Audit expansion: T/S create + delete now record on
  ``project_audit_logs``. Dep-edge changes (M/A) record their own
  audit entry. New ``actor_role`` column on the audit log.

These tests pin the new contract.
"""
from datetime import datetime, timedelta, timezone

from app.infrastructure.db.models.project_audit_log import ProjectAuditLogModel


def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _make_project(client, headers, *, name="P"):
    r = client.post(
        "/api/v3/projects/create",
        json={
            "name": name, "owner": "tmd1",
            "startDate": _iso(1), "endDate": _iso(120),
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _make_milestone(client, headers, pid):
    r = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={"name": "M1", "startDate": _iso(2), "endDate": _iso(60)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _make_activity(client, headers, mid):
    r = client.post(
        f"/api/v3/milestones/{mid}/activities/standard/create",
        json={"name": "A1", "startDate": _iso(3), "endDate": _iso(50)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _publish(client, headers, pid):
    """Publish a project so tasks / subtasks can be created on it.

    Required by the post-doc-33 follow-up that gates T/S writes on
    ``status == 'published'``. Pre-publish, T/S create returns 422.
    """
    r = client.post(f"/api/v3/projects/{pid}/publish", headers=headers)
    assert r.status_code == 200, r.text


def _make_published_project_with_activity(client, headers):
    """Bootstrap helper: project + milestone + activity + publish.
    Returns ``(pid, mid, aid)`` ready for T/S creates."""
    pid = _make_project(client, headers)
    mid = _make_milestone(client, headers, pid)
    aid = _make_activity(client, headers, mid)
    _publish(client, headers, pid)
    return pid, mid, aid


# ===========================================================================
# Removed endpoints
# ===========================================================================

class TestRemovedEndpoints:
    def test_versions_create_endpoint_removed(self, client, admin_user, admin_headers):
        pid = _make_project(client, admin_headers)
        resp = client.post(
            f"/api/v3/projects/{pid}/versions/create", headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_suspend_endpoint_removed(self, client, admin_user, admin_headers):
        pid = _make_project(client, admin_headers)
        resp = client.post(
            f"/api/v3/projects/{pid}/suspend", headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_suspended_status_rejected_on_create(self, client, admin_user, admin_headers):
        resp = client.post(
            "/api/v3/projects/create",
            json={
                "name": "P-suspended",
                "owner": "tmd1",
                "status": "suspended",
                "startDate": _iso(1),
                "endDate": _iso(60),
            },
            headers=admin_headers,
        )
        # Pydantic-level rejection — status not in PROJECT_STATUS_CHOICES.
        assert resp.status_code == 422


# ===========================================================================
# Response shape
# ===========================================================================

class TestResponseShape:
    def test_project_response_has_no_version_fields(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        resp = client.get(f"/api/v3/projects/{pid}", headers=admin_headers)
        body = resp.json()["data"]
        for removed in ("isVersion", "versionOf", "baselineId", "versionNo"):
            assert removed not in body, (
                f"Doc 33: response should not include {removed} field"
            )


# ===========================================================================
# T/S writes are gated on project.status == 'published'
#
# Post-doc-33 follow-up: tasks + subtasks can only be added once the
# project has been published (the senior's "publish, then add T/S"
# rule). Pre-publish (status=new or draft), T/S create returns
# 422 ``publish_required``. Post-publish, the same calls succeed.
# ===========================================================================

class TestTaskSubtaskRequirePublish:
    def test_task_create_rejected_before_publish(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        aid = _make_activity(client, admin_headers, mid)
        # No publish — task create should fail with the publish-required gate.
        resp = client.post(
            f"/api/v3/activities/{aid}/tasks/create",
            json={
                "name": "T1",
                "startDate": _iso(4),
                "endDate": _iso(40),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        # The gate carries a structured details payload.
        body = resp.json()
        err = body.get("error") or {}
        details = err.get("_embedded", {}).get("details", {})
        assert details.get("errorIdentifier") == "publish_required"
        assert details.get("requiredStatus") == "published"

    def test_subtask_create_rejected_before_publish_via_orm_seeded_task(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        """Subtask create on a non-published project is rejected.

        We can't build a task on a non-published project via the public
        API (the same gate blocks task create too). To exercise the
        subtask gate in isolation, we seed a task directly via the ORM
        on the shared sample_project (which stays in ``new``) and try
        to create a subtask under it through the API.
        """
        from datetime import datetime
        from uuid import uuid4
        from app.infrastructure.db.models.activity import ActivityModel
        from app.infrastructure.db.models.milestone import MilestoneModel
        from app.infrastructure.db.models.task import TaskModel

        # Pin a date range on the sample project (it ships without one).
        sample_project.start_date = datetime(2026, 5, 1)
        sample_project.end_date = datetime(2026, 12, 31)
        db_session.add(sample_project)
        db_session.commit()

        # Seed M / A / T directly via ORM so the publish gate doesn't
        # interfere with the test's setup.
        m = MilestoneModel(
            id=str(uuid4()),
            project_id=sample_project.id,
            name="M", description="-",
            start_date=datetime(2026, 5, 1), end_date=datetime(2026, 12, 31),
            position=1, status="not_completed",
        )
        db_session.add(m); db_session.flush()
        a = ActivityModel(
            id=str(uuid4()), project_id=sample_project.id, milestone_id=m.id,
            name="A", type="standard",
            start_date=datetime(2026, 5, 1), end_date=datetime(2026, 12, 31),
            position=1,
        )
        db_session.add(a); db_session.flush()
        t = TaskModel(
            id=str(uuid4()), project_id=sample_project.id, activity_id=a.id,
            name="T", type="standard",
            start_date=datetime(2026, 5, 1), end_date=datetime(2026, 12, 31),
            position=1,
        )
        db_session.add(t); db_session.commit()

        # Sample project is still in ``new`` (never published) — subtask
        # create against the seeded task must fail with publish_required.
        resp = client.post(
            f"/api/v3/tasks/{t.id}/subtasks/create",
            json={"name": "S-blocked", "startDate": _iso(5), "endDate": _iso(30)},
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        details = resp.json().get("error", {}).get("_embedded", {}).get("details", {})
        assert details.get("errorIdentifier") == "publish_required"

    def test_task_creatable_after_publish(
        self, client, admin_user, admin_headers,
    ):
        pid, mid, aid = _make_published_project_with_activity(
            client, admin_headers,
        )
        resp = client.post(
            f"/api/v3/activities/{aid}/tasks/create",
            json={"name": "T1", "startDate": _iso(4), "endDate": _iso(40)},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text

    def test_subtask_creatable_after_publish(
        self, client, admin_user, admin_headers,
    ):
        pid, mid, aid = _make_published_project_with_activity(
            client, admin_headers,
        )
        t = client.post(
            f"/api/v3/activities/{aid}/tasks/create",
            json={"name": "T", "startDate": _iso(4), "endDate": _iso(40)},
            headers=admin_headers,
        )
        tid = t.json()["data"]["id"]
        resp = client.post(
            f"/api/v3/tasks/{tid}/subtasks/create",
            json={"name": "S1", "startDate": _iso(5), "endDate": _iso(30)},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text


# ===========================================================================
# Audit expansion (T/S writes on project_audit_logs)
# ===========================================================================

class TestAuditExpansion:
    def test_task_create_recorded_in_project_audit(
        self, client, admin_user, admin_headers, db_session,
    ):
        pid, _mid, aid = _make_published_project_with_activity(
            client, admin_headers,
        )
        client.post(
            f"/api/v3/activities/{aid}/tasks/create",
            json={"name": "AuditedT", "startDate": _iso(4), "endDate": _iso(40)},
            headers=admin_headers,
        )
        rows = (
            db_session.query(ProjectAuditLogModel)
            .filter(ProjectAuditLogModel.project_id == pid)
            .filter(ProjectAuditLogModel.action == "task.create")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].after["name"] == "AuditedT"

    def test_subtask_create_recorded(
        self, client, admin_user, admin_headers, db_session,
    ):
        pid, _mid, aid = _make_published_project_with_activity(
            client, admin_headers,
        )
        t = client.post(
            f"/api/v3/activities/{aid}/tasks/create",
            json={"name": "T", "startDate": _iso(4), "endDate": _iso(40)},
            headers=admin_headers,
        )
        tid = t.json()["data"]["id"]
        client.post(
            f"/api/v3/tasks/{tid}/subtasks/create",
            json={"name": "AuditedS", "startDate": _iso(5), "endDate": _iso(30)},
            headers=admin_headers,
        )
        rows = (
            db_session.query(ProjectAuditLogModel)
            .filter(ProjectAuditLogModel.project_id == pid)
            .filter(ProjectAuditLogModel.action == "subtask.create")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].after["name"] == "AuditedS"

    def test_task_delete_recorded(
        self, client, admin_user, admin_headers, db_session,
    ):
        pid, _mid, aid = _make_published_project_with_activity(
            client, admin_headers,
        )
        t = client.post(
            f"/api/v3/activities/{aid}/tasks/create",
            json={"name": "T-del", "startDate": _iso(4), "endDate": _iso(40)},
            headers=admin_headers,
        )
        tid = t.json()["data"]["id"]
        client.delete(f"/api/v3/tasks/{tid}", headers=admin_headers)
        rows = (
            db_session.query(ProjectAuditLogModel)
            .filter(ProjectAuditLogModel.project_id == pid)
            .filter(ProjectAuditLogModel.action == "task.soft_delete")
            .all()
        )
        assert len(rows) == 1

    def test_actor_role_column_exists(self, db_session):
        """The new actor_role column accepts a value."""
        # Just verify the column can be queried — the SQLite drift healer
        # auto-adds nullable columns from the model.
        from sqlalchemy import inspect
        cols = {c["name"] for c in inspect(db_session.bind).get_columns("project_audit_logs")}
        assert "actor_role" in cols


# ===========================================================================
# Vendor role
# ===========================================================================

class TestVendorRole:
    def test_vendor_role_seeded(self, client, admin_user, admin_headers, db_session):
        from app.infrastructure.db.models.role import RoleModel
        # The /master/roles seed populates 'vendor' too post-doc-33.
        vendor = (
            db_session.query(RoleModel)
            .filter(RoleModel.name == "vendor")
            .first()
        )
        assert vendor is not None, "Doc 33: vendor role must be seeded"

    def test_vendor_role_holds_project_content_perms(
        self, client, admin_user, admin_headers, db_session,
    ):
        from app.infrastructure.db.models.role import RoleModel
        from app.infrastructure.db.models.permission import PermissionModel
        from app.infrastructure.db.models.role_permission import RolePermissionModel
        vendor_id = (
            db_session.query(RoleModel.id)
            .filter(RoleModel.name == "vendor")
            .scalar()
        )
        codes = {
            r[0]
            for r in db_session.query(RolePermissionModel.permission_code)
            .filter(RolePermissionModel.role_id == vendor_id)
            .all()
        }
        # Vendor SHOULD have M/A/T/S CRUD.
        for must_have in (
            "milestones:create", "activities:create",
            "tasks:create", "subtasks:create",
            "comments:create", "attachments:create",
        ):
            assert must_have in codes, f"vendor missing {must_have}"
        # Vendor should NOT have lifecycle / RBAC / master-data permissions.
        for must_not_have in (
            "projects:create", "projects:publish", "projects:close",
            "projects:delete", "projects:delete_all",
            "rbac:assign", "roles:create", "permissions:manage",
            "master_data:manage",
        ):
            assert must_not_have not in codes, f"vendor should not hold {must_not_have}"


# ===========================================================================
# Status machine — published → draft (doc 33: published is a checkpoint)
# ===========================================================================

class TestPublishedToDraft:
    def test_published_to_draft_is_a_legal_transition(self):
        """Doc 33: published → draft is now a legal edge in the in-code
        ``_LEGAL_TRANSITIONS`` constant (publish is a checkpoint, not a
        freeze). The catalog is seeded from this constant on app boot."""
        from app.api.v3.projects.services.transitions import (
            _LEGAL_TRANSITIONS,
            STATUS_PUBLISHED,
            STATUS_DRAFT,
        )
        assert (STATUS_PUBLISHED, STATUS_DRAFT) in _LEGAL_TRANSITIONS

    def test_publish_succeeds_with_milestone_and_activity(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        _make_activity(client, admin_headers, mid)
        pub = client.post(
            f"/api/v3/projects/{pid}/publish", headers=admin_headers,
        )
        assert pub.status_code == 200, pub.text
        assert pub.json()["data"]["status"] == "published"
