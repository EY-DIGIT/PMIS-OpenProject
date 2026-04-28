"""Tests for the new catalog endpoints + categoryOtherReason validation
+ task/subtask type inheritance.

Three groups of tests for the doc-15 work:

- ``TestStatusTransitionsCatalog`` — GET /project_status_transitions and the
  invalid_status guard on project create.
- ``TestProjectOwnersCatalog``     — GET /project_owners, POST /project_owners/create,
  DELETE /project_owners/{user_id}, and owner-whitelist enforcement on
  project create.
- ``TestCategoryOtherReason``      — categoryOtherReason required when
  category='others' and forbidden otherwise (covers create + upsert).
- ``TestTaskSubtaskTypeInheritance`` — type field is no longer on the create
  body; the service derives it from the parent activity / parent task and
  enforces the resource-mode shape against the inherited type.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.models.project_owner import ProjectOwnerModel
from app.infrastructure.db.models.project_status_transition import (
    ProjectStatusTransitionModel,
)
from app.infrastructure.db.models.user import UserModel


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_status_transitions(db_session):
    """Seed a small subset of the in-code transitions so the catalog probe
    in the create-project service has rows to validate against."""
    rows = [
        (None, "new", False, False),
        ("new", "draft", False, False),
        ("draft", "new", False, False),
        ("new", "published", True, False),
        ("draft", "published", True, False),
        ("published", "closed", True, False),
        ("new", "suspended", False, True),
    ]
    for from_s, to_s, admin_only, version_only in rows:
        db_session.add(ProjectStatusTransitionModel(
            from_status=from_s, to_status=to_s,
            requires_admin=admin_only, version_only=version_only,
            active=True,
        ))
    db_session.commit()


def _add_admin_owner(db_session, admin_user):
    """Seed the project_owners catalog with the admin user so the create-
    project owner validator allows owner='admin'."""
    db_session.add(ProjectOwnerModel(
        user_id=admin_user.id, display_name="Admin", active=True,
    ))
    db_session.commit()


def _create_project_body(owner="admin", status="new", **over):
    body = {
        "name": "P", "owner": owner, "status": status,
        "startDate": _iso(2), "endDate": _iso(60),
    }
    body.update(over)
    return body


# ---------------------------------------------------------------------------
# Status transitions catalog
# ---------------------------------------------------------------------------


class TestStatusTransitionsCatalog:
    def test_endpoint_lists_seeded_rows(self, client, admin_headers, db_session):
        _seed_status_transitions(db_session)
        resp = client.get("/api/v3/project_status_transitions", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["_embedded"]["elements"]
        # At least the rows we seeded should be present.
        edges = {(r["fromStatus"], r["toStatus"]) for r in items}
        assert (None, "new") in edges
        assert ("new", "draft") in edges
        assert ("new", "published") in edges
        # version-only flag round-trips correctly.
        suspend_row = [r for r in items if r["toStatus"] == "suspended"][0]
        assert suspend_row["versionOnly"] is True

    def test_create_project_rejects_invalid_status_against_catalog(
        self, client, admin_user, admin_headers, db_session,
    ):
        # Seed a catalog that does NOT include 'inprogress'.
        _seed_status_transitions(db_session)
        body = _create_project_body(status="inprogress")
        resp = client.post("/api/v3/projects/create", json=body, headers=admin_headers)
        # Pydantic schema rejects at 422 (in-code list is also tight); the
        # service-layer catalog check would also flag it as invalid_status.
        assert resp.status_code == 422

    def test_create_project_accepts_status_in_catalog(
        self, client, admin_user, admin_headers, db_session,
    ):
        _seed_status_transitions(db_session)
        _add_admin_owner(db_session, admin_user)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(status="new"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Project owners catalog
# ---------------------------------------------------------------------------


class TestProjectOwnersCatalog:
    def test_list_initially_empty(self, client, admin_headers):
        resp = client.get("/api/v3/project_owners", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 0
        assert body["_embedded"]["elements"] == []

    def test_admin_can_add_owner_by_login(self, client, admin_user, admin_headers):
        resp = client.post(
            "/api/v3/project_owners/create",
            json={"login": "admin", "displayName": "System Admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["login"] == "admin"
        assert body["displayName"] == "System Admin"
        assert body["active"] is True

    def test_unknown_login_404s(self, client, admin_headers):
        resp = client.post(
            "/api/v3/project_owners/create",
            json={"login": "no_such_user"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_create_project_rejects_owner_not_in_whitelist_when_catalog_populated(
        self, client, admin_user, member_user, admin_headers, db_session,
    ):
        # Populate catalog with member_user only.
        db_session.add(ProjectOwnerModel(
            user_id=member_user.id, display_name="Member", active=True,
        ))
        db_session.commit()
        # Now try to create a project owned by 'admin' — should fail because
        # 'admin' is not in the whitelist.
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="admin"),
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "whitelist" in resp.json()["error"]["message"].lower()

    def test_deactivate_owner(self, client, admin_user, admin_headers, db_session):
        _add_admin_owner(db_session, admin_user)
        resp = client.delete(
            f"/api/v3/project_owners/{admin_user.id}", headers=admin_headers,
        )
        assert resp.status_code == 200
        # List now empty.
        list_resp = client.get("/api/v3/project_owners", headers=admin_headers)
        assert list_resp.json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# categoryOtherReason
# ---------------------------------------------------------------------------


class TestCategoryOtherReason:
    """Upsert-path coverage for categoryOtherReason. The create-path tests
    live in tests/test_new_features.py::TestCategoryOthers (which has more
    thorough coverage of every (category, categoryOther, reason) combo).
    Keeping only the upsert case here so the two files don't duplicate.
    """

    def test_upsert_others_requires_reason(self, client, admin_user, admin_headers):
        new_uuid = str(uuid4())
        resp = client.put(
            f"/api/v3/projects/{new_uuid}",
            json=_create_project_body(
                category="others", categoryOther="New cat",
            ),
            headers=admin_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Divisions catalog
# ---------------------------------------------------------------------------


class TestDivisionsCatalog:
    """GET /divisions surfaces the in-code DIVISION_CHOICES so the FE can
    populate dropdowns without hard-coding labels."""

    def test_endpoint_returns_three_divisions_with_labels(self, client, admin_headers):
        resp = client.get("/api/v3/divisions", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        items = body["_embedded"]["elements"]
        assert len(items) == 3
        codes = [i["code"] for i in items]
        assert codes == ["tmd1", "tmd2", "others"]
        labels = {i["code"]: i["label"] for i in items}
        assert labels == {"tmd1": "TMD1", "tmd2": "TMD2", "others": "Others"}
        # Only the 'others' entry should advertise the free-text follow-up.
        requires_other = {i["code"]: i["requiresOther"] for i in items}
        assert requires_other == {"tmd1": False, "tmd2": False, "others": True}

    def test_endpoint_requires_authentication(self, client):
        resp = client.get("/api/v3/divisions")
        assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# PATCH editable-field whitelist (doc 18 expansion)
# ---------------------------------------------------------------------------


class TestPatchEditableFields:
    """The PATCH whitelist now matches the HTML edit-project flow: baselines
    can edit category + categoryOther + categoryOtherReason + actual dates;
    versions can NOT edit name / start_date / category. Status is rejected
    on both — clients use the dedicated publish/close/suspend endpoints."""

    def _create_baseline(self, client, admin_user, admin_headers, db_session, **overrides):
        _add_admin_owner(db_session, admin_user)
        _seed_status_transitions(db_session)
        body = _create_project_body(**overrides)
        resp = client.post(
            "/api/v3/projects/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]

    def test_baseline_can_patch_category(
        self, client, admin_user, admin_headers, db_session,
    ):
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session, category="MSAP",
        )
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"category": "MSIP"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["category"] == "MSIP"

    def test_baseline_can_patch_to_others_with_reason(
        self, client, admin_user, admin_headers, db_session,
    ):
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session, category="MSAP",
        )
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={
                "category": "others",
                "categoryOther": "Internal R&D",
                "categoryOtherReason": "Pilot bucket pending approval.",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["category"] == "others"
        assert d["categoryOther"] == "Internal R&D"
        assert d["categoryOtherReason"] == "Pilot bucket pending approval."

    def test_baseline_patch_to_others_without_reason_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session, category="MSAP",
        )
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"category": "others", "categoryOther": "X"},
            headers=admin_headers,
        )
        # Missing categoryOtherReason → 422 from the symmetric check.
        assert resp.status_code == 422, resp.text

    def test_baseline_status_patch_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Status changes go through publish/close/suspend, not PATCH."""
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session,
        )
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"status": "published"},
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()["error"]
        assert body["errorIdentifier"] == "invalid_field"
        assert "status" in body["_embedded"]["details"]["rejected"]

    def test_version_status_patch_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Versions also reject PATCH on status (and on category /
        project_code / baseline_id, which were never editable)."""
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session,
        )
        client.post(f"/api/v3/projects/{p['id']}/publish", headers=admin_headers)
        v = client.post(
            f"/api/v3/projects/{p['id']}/versions/create", headers=admin_headers,
        ).json()["data"]
        for field, value in (
            ("status", "closed"),
            ("category", "MSIP"),
            ("name", "should-not-work"),
            ("start_date", _iso(99)),
        ):
            resp = client.patch(
                f"/api/v3/projects/{v['id']}",
                json={field: value},
                headers=admin_headers,
            )
            assert resp.status_code == 422, (field, resp.text)
            body = resp.json()["error"]
            assert body["errorIdentifier"] == "invalid_field", (field, body)


# ---------------------------------------------------------------------------
# Task / subtask type inheritance
# ---------------------------------------------------------------------------


def _create_baseline_with_resource_activity(client, admin_headers):
    """Helper: project + milestone + resource/details activity, then publish
    + version so we can create tasks (tasks live on versions only)."""
    p = client.post(
        "/api/v3/projects/create",
        json=_create_project_body(),
        headers=admin_headers,
    ).json()["data"]
    pid = p["id"]
    mid = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={"name": "M", "startDate": _iso(3), "endDate": _iso(40)},
        headers=admin_headers,
    ).json()["data"]["id"]
    # Standard activity for the simple inheritance test.
    a_std = client.post(
        f"/api/v3/milestones/{mid}/activities/standard/create",
        json={"name": "A-std", "startDate": _iso(4), "endDate": _iso(20)},
        headers=admin_headers,
    ).json()["data"]["id"]
    # Resource/count activity for the resource-inheritance test.
    a_res = client.post(
        f"/api/v3/milestones/{mid}/activities/resource/count/create",
        json={
            "name": "A-res", "startDate": _iso(4), "endDate": _iso(20),
            "resourceCount": 2,
        },
        headers=admin_headers,
    ).json()["data"]["id"]

    # Publish + version so tasks become creatable.
    client.post(f"/api/v3/projects/{pid}/publish", headers=admin_headers)
    v = client.post(
        f"/api/v3/projects/{pid}/versions/create", headers=admin_headers,
    ).json()["data"]
    vid = v["id"]
    # Look up the version's clones of the activities.
    ms = client.get(
        f"/api/v3/projects/{vid}/milestones", headers=admin_headers,
    ).json()["data"]["_embedded"]["elements"]
    version_mid = ms[0]["id"]
    acts = client.get(
        f"/api/v3/milestones/{version_mid}/activities", headers=admin_headers,
    ).json()["data"]["_embedded"]["elements"]
    by_type = {a["type"]: a["id"] for a in acts}
    return pid, vid, by_type["standard"], by_type["resource"]


class TestTaskSubtaskTypeInheritance:
    def test_task_inherits_standard_type(self, client, admin_user, admin_headers):
        _, _, std_aid, _ = _create_baseline_with_resource_activity(client, admin_headers)
        resp = client.post(
            f"/api/v3/activities/{std_aid}/tasks/create",
            json={"name": "T", "startDate": _iso(5), "endDate": _iso(15)},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["type"] == "standard"
        assert body["resourceMode"] is None

    def test_task_under_resource_activity_requires_mode(
        self, client, admin_user, admin_headers,
    ):
        _, _, _, res_aid = _create_baseline_with_resource_activity(client, admin_headers)
        # Body omits resourceMode — must be rejected because the inherited
        # type is 'resource' and a mode is required for resource tasks.
        resp = client.post(
            f"/api/v3/activities/{res_aid}/tasks/create",
            json={"name": "T", "startDate": _iso(5), "endDate": _iso(15)},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "resourcemode" in resp.text.lower()

    def test_task_under_resource_activity_count_mode(
        self, client, admin_user, admin_headers,
    ):
        _, _, _, res_aid = _create_baseline_with_resource_activity(client, admin_headers)
        resp = client.post(
            f"/api/v3/activities/{res_aid}/tasks/create",
            json={
                "name": "T", "startDate": _iso(5), "endDate": _iso(15),
                "resourceMode": "count", "resourceCount": 2,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["type"] == "resource"
        assert body["resourceMode"] == "count"
        assert body["resourceCount"] == 2

    def test_task_under_standard_activity_rejects_resource_fields(
        self, client, admin_user, admin_headers,
    ):
        _, _, std_aid, _ = _create_baseline_with_resource_activity(client, admin_headers)
        resp = client.post(
            f"/api/v3/activities/{std_aid}/tasks/create",
            json={
                "name": "T", "startDate": _iso(5), "endDate": _iso(15),
                "resourceMode": "count", "resourceCount": 1,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "resourcemode" in resp.text.lower()

    def test_subtask_inherits_type_from_parent_task(
        self, client, admin_user, admin_headers,
    ):
        _, _, std_aid, _ = _create_baseline_with_resource_activity(client, admin_headers)
        # Create a standard task.
        tid = client.post(
            f"/api/v3/activities/{std_aid}/tasks/create",
            json={"name": "T", "startDate": _iso(5), "endDate": _iso(15)},
            headers=admin_headers,
        ).json()["data"]["id"]
        # Subtask under it: type omitted from body.
        resp = client.post(
            f"/api/v3/tasks/{tid}/subtasks/create",
            json={"name": "ST", "startDate": _iso(6), "endDate": _iso(12)},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["type"] == "standard"
