"""Doc 30 part 2: extend the milestone create + inline-comment/files
pattern across activities, tasks, subtasks, and nested subtasks.

Each create endpoint now dispatches on Content-Type:
  * ``application/json``       → existing path, unchanged.
  * ``multipart/form-data``    → milestone-fields-equivalent + optional
                                 ``body`` (comment text) and ``files``
                                 (uploads). With body → comment row
                                 carrying the attachments. Without body
                                 (files only) → standalone attachments
                                 against the new entity.

Endpoints exercised here:
  * POST /milestones/{id}/activities/standard/create
  * POST /milestones/{id}/activities/resource/count/create
  * POST /milestones/{id}/activities/resource/details/create
  * POST /milestones/{id}/activities/transactional/create
  * POST /activities/{id}/tasks/create
  * POST /tasks/{id}/subtasks/create
  * POST /subtasks/{id}/subtasks/create        (nested, doc 24)

The shared multipart machinery lives in ``app/api/v3/_inline_attachments``;
these tests are the cross-entity contract against it. The milestone
suite covers the same machinery in
``test_doc30_milestone_inline_attachments`` — these tests focus on
proving the same behaviour holds for the four downstream entities.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.infrastructure.db.models.milestone import MilestoneModel
from app.infrastructure.db.models.activity import ActivityModel
from app.infrastructure.db.models.task import TaskModel
from app.infrastructure.db.models.subtask import SubtaskModel
from app.infrastructure.db.models.comment import CommentModel
# Doc 35: AttachmentModel removed (collapsed onto CommentModel.attachments JSON column).
from app.infrastructure.db.models.resource_type import ResourceTypeModel
import app.infrastructure.storage as storage_pkg
from app.infrastructure.storage.file_storage import FileStorage
from app.infrastructure.storage import reset_file_client_for_tests


# ---------------------------------------------------------------------------
# Storage fixture (per-test sandbox so the test never touches the real
# attachments directory).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_storage(tmp_path, monkeypatch):
    tmp = FileStorage(
        base_path=str(tmp_path / "storage"),
        subdir_strategy="year_month",
    )
    tmp.ensure_ready()
    monkeypatch.setattr(storage_pkg.file_storage, "_storage", tmp)
    # Doc 35: the file client wraps the low-level storage; reset it so
    # each test sees the freshly-redirected storage.
    reset_file_client_for_tests()
    yield tmp
    reset_file_client_for_tests()


# ---------------------------------------------------------------------------
# Hierarchy fixtures: project → milestone → activity (standard) → task →
# subtask. Each downstream test takes the slice it needs.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def dated_project(db_session, sample_project):
    """Same trick as the milestone tests: pin a wide date range on the
    shared sample_project so every downstream node has a date window
    the dependency-resolver / date-clamping is happy with."""
    sample_project.start_date = datetime(2026, 5, 1)
    sample_project.end_date = datetime(2026, 12, 31)
    db_session.add(sample_project)
    db_session.commit()
    db_session.refresh(sample_project)
    return sample_project


@pytest.fixture(scope="function")
def standard_milestone(db_session, dated_project):
    now = datetime.now(timezone.utc)
    m = MilestoneModel(
        id=str(uuid4()), project_id=dated_project.id,
        name="M1", description="-",
        start_date=datetime(2026, 5, 1),
        end_date=datetime(2026, 12, 31),
        position=1, status="not_completed",
        created_at=now, updated_at=now,
    )
    db_session.add(m); db_session.commit(); db_session.refresh(m)
    return m


@pytest.fixture(scope="function")
def standard_activity(db_session, dated_project, standard_milestone):
    now = datetime.now(timezone.utc)
    a = ActivityModel(
        id=str(uuid4()), project_id=dated_project.id,
        milestone_id=standard_milestone.id,
        name="A1", description="-", type="standard",
        start_date=datetime(2026, 5, 1),
        end_date=datetime(2026, 12, 31),
        position=1,
        created_at=now, updated_at=now,
    )
    db_session.add(a); db_session.commit(); db_session.refresh(a)
    return a


# ---------------------------------------------------------------------------
# Versioned project — required for task / subtask creates.
#
# The BE rejects task/subtask writes against baseline projects (the user
# is meant to create a version snapshot first, edit there, then publish
# the diff back). Mirrors the helper in test_nested_subtasks.
# ---------------------------------------------------------------------------

def _future_iso(days_from_today: int) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(days=days_from_today)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


@pytest.fixture(scope="function")
def version_activity_id(client, admin_headers):
    """Create a baseline project → milestone → activity, publish, then
    create a version. Return the version's activity id (the version
    twin of A1) so task creates target the writable version."""
    # Baseline project.
    pr = client.post(
        "/api/v3/projects/create",
        json={
            "name": "Doc30 A/T/S host", "owner": "tmd1",
            "startDate": _future_iso(1), "endDate": _future_iso(120),
        },
        headers=admin_headers,
    )
    assert pr.status_code == 201, pr.text
    pid = pr.json()["data"]["id"]
    # Milestone + activity on baseline.
    mr = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={"name": "M1", "startDate": _future_iso(2), "endDate": _future_iso(100)},
        headers=admin_headers,
    )
    assert mr.status_code == 201, mr.text
    mid = mr.json()["data"]["id"]
    ar = client.post(
        f"/api/v3/milestones/{mid}/activities/standard/create",
        json={"name": "A1", "startDate": _future_iso(3), "endDate": _future_iso(80)},
        headers=admin_headers,
    )
    assert ar.status_code == 201, ar.text
    # Post-doc-33 follow-up: T/S writes are gated on the project being
    # ``published``. Publish here so the downstream task / subtask
    # fixtures can create rows.
    pub = client.post(f"/api/v3/projects/{pid}/publish", headers=admin_headers)
    assert pub.status_code == 200, pub.text
    tree = client.get(f"/api/v3/projects/{pid}/tree", headers=admin_headers).json()["data"]
    return tree["milestones"][0]["activities"][0]["id"]


@pytest.fixture(scope="function")
def version_task_id(client, admin_headers, version_activity_id):
    """Top-level task in the version-only project, so subtask creates can target it."""
    tr = client.post(
        f"/api/v3/activities/{version_activity_id}/tasks/create",
        json={"name": "T1", "startDate": _future_iso(4), "endDate": _future_iso(70)},
        headers=admin_headers,
    )
    assert tr.status_code == 201, tr.text
    return tr.json()["data"]["id"]


@pytest.fixture(scope="function")
def version_subtask_id(client, admin_headers, version_task_id):
    """A real top-level subtask in the version project — its id is the
    parent for nested-subtask multipart creates."""
    sr = client.post(
        f"/api/v3/tasks/{version_task_id}/subtasks/create",
        json={"name": "S1", "startDate": _future_iso(5), "endDate": _future_iso(60)},
        headers=admin_headers,
    )
    assert sr.status_code == 201, sr.text
    return sr.json()["data"]["id"]


@pytest.fixture(scope="function")
def resource_type_row(db_session):
    """A single resource-type row for resource/details activity tests."""
    now = datetime.now(timezone.utc)
    rt = ResourceTypeModel(
        id=str(uuid4()),
        code=f"rt-{uuid4().hex[:6]}",
        name="Engineer",
        active=True,
        created_at=now, updated_at=now,
    )
    db_session.add(rt); db_session.commit(); db_session.refresh(rt)
    return rt


# ---------------------------------------------------------------------------
# Common test inputs
# ---------------------------------------------------------------------------

_DATES = {
    "startDate": "2026-06-01T00:00:00+05:30",
    "endDate":   "2026-06-30T00:00:00+05:30",
}


# ===========================================================================
# Activities — standard
# ===========================================================================

class TestActivityStandardMultipart:
    def _url(self, milestone_id):
        return f"/api/v3/milestones/{milestone_id}/activities/standard/create"

    def test_json_path_unchanged(
        self, client, admin_user, admin_headers, standard_milestone, temp_storage,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            json={"name": "A-json", **_DATES},
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["name"] == "A-json"
        assert "comment" not in d
        assert "standaloneAttachments" not in d

    def test_multipart_no_attachments(
        self, client, admin_user, admin_headers, standard_milestone, temp_storage,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-mp", **_DATES},
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert "comment" not in d
        assert "standaloneAttachments" not in d

    def test_body_with_files_creates_comment_with_attachments(
        self, client, admin_user, admin_headers, standard_milestone,
        temp_storage, db_session,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-body+files", **_DATES, "body": "see spec"},
            files=[
                ("files", ("a.pdf", b"%PDF-1.4 a", "application/pdf")),
            ],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["comment"]["body"] == "see spec"
        assert len(d["comment"]["attachments"]) == 1
        assert d["comment"]["attachments"][0]["filename"] == "a.pdf"

    def test_files_only_creates_body_null_comment(
        self, client, admin_user, admin_headers, standard_milestone,
        temp_storage, db_session,
    ):
        """Doc 35: files-only sends now produce a comment row with NULL
        body. The legacy ``standaloneAttachments`` response key is gone."""
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-files-only", **_DATES},
            files=[("files", ("x.pdf", b"%PDF-1.4 x", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert "comment" in d
        assert (d["comment"].get("body") or "") == ""
        assert len(d["comment"]["attachments"]) == 1
        assert d["comment"]["attachments"][0]["filename"] == "x.pdf"
        assert "standaloneAttachments" not in d

    def test_bad_extension_rejected_pre_create(
        self, client, admin_user, admin_headers, standard_milestone,
        temp_storage, db_session,
    ):
        pre = db_session.query(ActivityModel).count()
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-bad", **_DATES, "body": "evil"},
            files=[("files", ("evil.exe", b"MZ\x00", "application/octet-stream"))],
        )
        assert resp.status_code == 422, resp.text
        post = db_session.query(ActivityModel).count()
        assert post == pre, "bad extension must not orphan an activity"

    def test_dependsOn_array_decoded_correctly(
        self, client, admin_user, admin_headers, standard_milestone,
        temp_storage, db_session,
    ):
        """Doc 27 (post-rebase) requires source.start_date >= target.end_date
        for activity dependencies. The test's focus is JSON-array decoding,
        not the dep-date rule itself (covered separately in test_doc30_dep_dates),
        so we explicitly date the target to end before the dependent starts.
        """
        # Target ends mid-June; dependent starts at target's end (equality OK).
        target = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            json={
                "name": "A-target",
                "startDate": "2026-06-01T00:00:00+05:30",
                "endDate":   "2026-06-15T00:00:00+05:30",
            },
        ).json()["data"]
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={
                "name": "A-dep",
                "startDate": "2026-06-15T00:00:00+05:30",
                "endDate":   "2026-06-30T00:00:00+05:30",
                "dependsOn": json.dumps([target["id"]]),
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["dependsOn"] == [target["id"]]

    def test_invalid_status_returns_422_not_500(
        self, client, admin_user, admin_headers, standard_milestone, temp_storage,
    ):
        """Sanitized-error regression: bad enum value must surface as 422,
        not 500. Pydantic's ctx.error (a ValueError) is not JSON-safe and
        used to crash the envelope renderer."""
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-badstatus", **_DATES, "status": "definitely_not_a_status"},
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        err = body.get("error") or {}
        details = err.get("_embedded", {}).get("details", {})
        for e in details.get("errors", []):
            assert "ctx" not in e

    def test_empty_optional_fields_treated_as_omitted(
        self, client, admin_user, admin_headers, standard_milestone, temp_storage,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={
                "name": "A-empties", **_DATES,
                "description": "", "status": "", "dependsOn": "",
            },
        )
        assert resp.status_code == 201, resp.text


# ===========================================================================
# Activities — resource/count
# ===========================================================================

class TestActivityResourceCountMultipart:
    def _url(self, milestone_id):
        return f"/api/v3/milestones/{milestone_id}/activities/resource/count/create"

    def test_multipart_creates_count_activity(
        self, client, admin_user, admin_headers, standard_milestone, temp_storage,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-rc", **_DATES, "resourceCount": "5"},
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["resourceMode"] == "count"
        assert d["resourceCount"] == 5

    def test_multipart_count_with_inline_comment(
        self, client, admin_user, admin_headers, standard_milestone,
        temp_storage, db_session,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={
                "name": "A-rc-cmt", **_DATES,
                "resourceCount": "3",
                "body": "team of 3",
            },
            files=[("files", ("plan.pdf", b"%PDF-1.4 plan", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["comment"]["body"] == "team of 3"
        assert len(d["comment"]["attachments"]) == 1

    def test_missing_resource_count_rejected(
        self, client, admin_user, admin_headers, standard_milestone, temp_storage,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-rc-bad", **_DATES},
        )
        assert resp.status_code == 422


# ===========================================================================
# Activities — resource/details (nested ``resource`` JSON-encoded)
# ===========================================================================

class TestActivityResourceDetailsMultipart:
    def _url(self, milestone_id):
        return f"/api/v3/milestones/{milestone_id}/activities/resource/details/create"

    def test_multipart_creates_details_activity(
        self, client, admin_user, admin_headers, standard_milestone,
        resource_type_row, temp_storage,
    ):
        resource_block = {
            "resourceName": "Alice",
            "typeOfResourceId": resource_type_row.id,
            "division": "tmd1",
        }
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={
                "name": "A-rd", **_DATES,
                "resource": json.dumps(resource_block),
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["resourceMode"] == "details"
        assert d["resource"]["resourceName"] == "Alice"
        assert d["resource"]["typeOfResourceId"] == resource_type_row.id
        assert d["resource"]["division"] == "tmd1"

    def test_multipart_malformed_resource_returns_422(
        self, client, admin_user, admin_headers, standard_milestone, temp_storage,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-rd-bad", **_DATES, "resource": "not-json"},
        )
        assert resp.status_code == 422


# ===========================================================================
# Activities — transactional
# ===========================================================================

class TestActivityTransactionalMultipart:
    def _url(self, milestone_id):
        return f"/api/v3/milestones/{milestone_id}/activities/transactional/create"

    def test_multipart_creates_transactional_with_files(
        self, client, admin_user, admin_headers, standard_milestone,
        temp_storage, db_session,
    ):
        resp = client.post(
            self._url(standard_milestone.id),
            headers=admin_headers,
            data={"name": "A-tx", **_DATES},
            files=[("files", ("ledger.pdf", b"%PDF-1.4 L", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["type"] == "transactional"
        # Doc 35: files-only ⇒ comment row with NULL body, attachments JSON list.
        assert "comment" in d
        assert (d["comment"].get("body") or "") == ""
        assert len(d["comment"]["attachments"]) == 1
        assert "standaloneAttachments" not in d


# ===========================================================================
# Tasks
# ===========================================================================

class TestTaskMultipart:
    """Tasks need a versioned project (baseline projects forbid task
    writes), so all tests pull ``version_activity_id`` from the fixture
    chain."""
    def _url(self, activity_id):
        return f"/api/v3/activities/{activity_id}/tasks/create"

    def test_json_path_unchanged(
        self, client, admin_user, admin_headers, version_activity_id, temp_storage,
    ):
        resp = client.post(
            self._url(version_activity_id),
            headers=admin_headers,
            json={"name": "T-json", "startDate": _future_iso(5), "endDate": _future_iso(60)},
        )
        assert resp.status_code == 201, resp.text
        assert "comment" not in resp.json()["data"]

    def test_multipart_no_attachments(
        self, client, admin_user, admin_headers, version_activity_id, temp_storage,
    ):
        resp = client.post(
            self._url(version_activity_id),
            headers=admin_headers,
            data={"name": "T-mp", "startDate": _future_iso(5), "endDate": _future_iso(60)},
        )
        assert resp.status_code == 201, resp.text

    def test_multipart_body_and_files(
        self, client, admin_user, admin_headers, version_activity_id,
        temp_storage, db_session,
    ):
        resp = client.post(
            self._url(version_activity_id),
            headers=admin_headers,
            data={
                "name": "T-bf",
                "startDate": _future_iso(5), "endDate": _future_iso(60),
                "body": "task notes",
            },
            files=[("files", ("t.pdf", b"%PDF-1.4 t", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["comment"]["body"] == "task notes"
        assert len(d["comment"]["attachments"]) == 1

    def test_multipart_files_only(
        self, client, admin_user, admin_headers, version_activity_id,
        temp_storage, db_session,
    ):
        """Doc 35: files-only ⇒ comment row with NULL body."""
        resp = client.post(
            self._url(version_activity_id),
            headers=admin_headers,
            data={"name": "T-files", "startDate": _future_iso(5), "endDate": _future_iso(60)},
            files=[("files", ("x.pdf", b"%PDF-1.4 x", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert "comment" in d
        assert (d["comment"].get("body") or "") == ""
        assert len(d["comment"]["attachments"]) == 1
        assert "standaloneAttachments" not in d

    def test_bad_extension_does_not_orphan_task(
        self, client, admin_user, admin_headers, version_activity_id,
        temp_storage, db_session,
    ):
        pre = db_session.query(TaskModel).count()
        resp = client.post(
            self._url(version_activity_id),
            headers=admin_headers,
            data={
                "name": "T-bad",
                "startDate": _future_iso(5), "endDate": _future_iso(60),
                "body": "evil",
            },
            files=[("files", ("evil.exe", b"MZ\x00", "application/octet-stream"))],
        )
        assert resp.status_code == 422, resp.text
        post = db_session.query(TaskModel).count()
        assert post == pre

    def test_empty_optionals_treated_as_omitted(
        self, client, admin_user, admin_headers, version_activity_id, temp_storage,
    ):
        resp = client.post(
            self._url(version_activity_id),
            headers=admin_headers,
            data={
                "name": "T-empties",
                "startDate": _future_iso(5), "endDate": _future_iso(60),
                "description": "", "resourceMode": "", "dependsOn": "",
            },
        )
        assert resp.status_code == 201, resp.text


# ===========================================================================
# Subtasks — task-scoped
# ===========================================================================

class TestSubtaskTaskScopedMultipart:
    def _url(self, task_id):
        return f"/api/v3/tasks/{task_id}/subtasks/create"

    def test_json_path_unchanged(
        self, client, admin_user, admin_headers, version_task_id, temp_storage,
    ):
        resp = client.post(
            self._url(version_task_id),
            headers=admin_headers,
            json={"name": "S-json", "startDate": _future_iso(6), "endDate": _future_iso(55)},
        )
        assert resp.status_code == 201, resp.text

    def test_multipart_body_and_files(
        self, client, admin_user, admin_headers, version_task_id,
        temp_storage, db_session,
    ):
        resp = client.post(
            self._url(version_task_id),
            headers=admin_headers,
            data={
                "name": "S-bf",
                "startDate": _future_iso(6), "endDate": _future_iso(55),
                "body": "sub notes",
            },
            files=[("files", ("s.pdf", b"%PDF-1.4 s", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["comment"]["body"] == "sub notes"
        assert len(d["comment"]["attachments"]) == 1

    def test_multipart_files_only(
        self, client, admin_user, admin_headers, version_task_id,
        temp_storage, db_session,
    ):
        """Doc 35: files-only ⇒ comment row with NULL body."""
        resp = client.post(
            self._url(version_task_id),
            headers=admin_headers,
            data={"name": "S-files", "startDate": _future_iso(6), "endDate": _future_iso(55)},
            files=[("files", ("y.pdf", b"%PDF-1.4 y", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert "comment" in d
        assert (d["comment"].get("body") or "") == ""
        assert len(d["comment"]["attachments"]) == 1
        assert "standaloneAttachments" not in d

    def test_bad_extension_does_not_orphan_subtask(
        self, client, admin_user, admin_headers, version_task_id,
        temp_storage, db_session,
    ):
        pre = db_session.query(SubtaskModel).count()
        resp = client.post(
            self._url(version_task_id),
            headers=admin_headers,
            data={
                "name": "S-bad",
                "startDate": _future_iso(6), "endDate": _future_iso(55),
                "body": "evil",
            },
            files=[("files", ("evil.exe", b"MZ\x00", "application/octet-stream"))],
        )
        assert resp.status_code == 422
        post = db_session.query(SubtaskModel).count()
        assert post == pre


# ===========================================================================
# Subtasks — nested under another subtask
# ===========================================================================

class TestSubtaskNestedMultipart:
    def _url(self, parent_subtask_id):
        return f"/api/v3/subtasks/{parent_subtask_id}/subtasks/create"

    def test_json_path_unchanged(
        self, client, admin_user, admin_headers, version_subtask_id, temp_storage,
    ):
        resp = client.post(
            self._url(version_subtask_id),
            headers=admin_headers,
            json={"name": "S2-json", "startDate": _future_iso(7), "endDate": _future_iso(50)},
        )
        assert resp.status_code == 201, resp.text
        # Nested subtask has parentSubtaskId set to the parent's id.
        assert resp.json()["data"]["parentSubtaskId"] == version_subtask_id

    def test_multipart_with_body(
        self, client, admin_user, admin_headers, version_subtask_id,
        temp_storage, db_session,
    ):
        resp = client.post(
            self._url(version_subtask_id),
            headers=admin_headers,
            data={
                "name": "S2-bf",
                "startDate": _future_iso(7), "endDate": _future_iso(50),
                "body": "nested notes",
            },
            files=[("files", ("n.pdf", b"%PDF-1.4 n", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["parentSubtaskId"] == version_subtask_id
        assert d["comment"]["body"] == "nested notes"
        assert len(d["comment"]["attachments"]) == 1

    def test_multipart_files_only_creates_body_null_comment(
        self, client, admin_user, admin_headers, version_subtask_id,
        temp_storage, db_session,
    ):
        """Doc 35: files-only ⇒ comment row with NULL body."""
        resp = client.post(
            self._url(version_subtask_id),
            headers=admin_headers,
            data={"name": "S2-files", "startDate": _future_iso(7), "endDate": _future_iso(50)},
            files=[("files", ("z.pdf", b"%PDF-1.4 z", "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["parentSubtaskId"] == version_subtask_id
        assert "comment" in d
        assert (d["comment"].get("body") or "") == ""
        assert len(d["comment"]["attachments"]) == 1
        assert "standaloneAttachments" not in d

    def test_bad_extension_does_not_orphan_nested_subtask(
        self, client, admin_user, admin_headers, version_subtask_id,
        temp_storage, db_session,
    ):
        pre = db_session.query(SubtaskModel).count()
        resp = client.post(
            self._url(version_subtask_id),
            headers=admin_headers,
            data={
                "name": "S2-bad",
                "startDate": _future_iso(7), "endDate": _future_iso(50),
                "body": "evil",
            },
            files=[("files", ("evil.exe", b"MZ\x00", "application/octet-stream"))],
        )
        assert resp.status_code == 422
        post = db_session.query(SubtaskModel).count()
        assert post == pre


# ===========================================================================
# Cross-cutting: dispatch helper handles both Content-Types correctly
# (already covered per-entity above; this test just confirms the
# malformed-JSON-on-JSON-path branch still produces a clean 422).
# ===========================================================================

class TestDispatchEdgeCases:
    def test_malformed_json_returns_422_not_500(
        self, client, admin_user, admin_headers, standard_milestone, temp_storage,
    ):
        resp = client.post(
            f"/api/v3/milestones/{standard_milestone.id}/activities/standard/create",
            headers={**admin_headers, "Content-Type": "application/json"},
            content=b"{not valid json",
        )
        assert resp.status_code == 422, resp.text
