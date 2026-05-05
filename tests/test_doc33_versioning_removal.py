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
# T/S writable on project (no version required)
# ===========================================================================

class TestTaskSubtaskOnProject:
    def test_task_creatable_on_project_directly(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        aid = _make_activity(client, admin_headers, mid)
        # No publish, no version creation — just create the task.
        resp = client.post(
            f"/api/v3/activities/{aid}/tasks/create",
            json={
                "name": "T1",
                "startDate": _iso(4),
                "endDate": _iso(40),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text

    def test_subtask_creatable_on_project_directly(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        aid = _make_activity(client, admin_headers, mid)
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
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        aid = _make_activity(client, admin_headers, mid)
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
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        aid = _make_activity(client, admin_headers, mid)
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
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        aid = _make_activity(client, admin_headers, mid)
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
