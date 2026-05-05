"""Doc 30: milestone create accepts inline comment + attachments via
multipart, alongside the existing JSON path.

Reported flow: when the user creates a project + milestone in one
"Save & Next" form and includes a comment / file in the milestone
form, the FE has no milestone_id yet to use for the standalone
``/comments`` or ``/attachments`` endpoints. Pre-fix, the FE tried
``/projects/{id}/comments`` (404) or had to do a save-then-attach
two-call flow.

Fix: the milestone create endpoint accepts EITHER ``application/json``
(legacy — milestone fields only) OR ``multipart/form-data`` (new —
milestone fields as form fields, plus optional ``body`` (comment text)
and ``files`` (file uploads)). Same URL, dispatch on Content-Type.

These tests cover:
  * JSON path is unchanged (regression).
  * Multipart with no body / no files works (just creates milestone).
  * Multipart with body only creates milestone + empty-attachments comment.
  * Multipart with body + files creates milestone + comment + bound attachments.
  * Multipart with files only creates milestone + standalone attachments
    (no comment row).
  * Pre-validation rejects bad files BEFORE the milestone is persisted.
  * Multipart with malformed array fields (``dependsOn``, ``vendors``)
    returns 422 cleanly.
  * Multipart with the same calendar dates as the project still works
    (composes correctly with doc 29's IST normalization).
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.infrastructure.db.models.milestone import MilestoneModel
from app.infrastructure.db.models.comment import CommentModel
from app.infrastructure.db.models.attachment import AttachmentModel
import app.infrastructure.storage as storage_pkg
from app.infrastructure.storage.file_storage import FileStorage


# ---------------------------------------------------------------------------
# Fixtures (mirror test_comments.py so the storage layer is patched
# and writes don't escape the test sandbox)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_storage(tmp_path, monkeypatch):
    tmp = FileStorage(
        base_path=str(tmp_path / "storage"),
        subdir_strategy="year_month",
    )
    tmp.ensure_ready()
    monkeypatch.setattr(storage_pkg.file_storage, "_storage", tmp)
    yield tmp


@pytest.fixture(scope="function")
def dated_project(db_session, sample_project):
    """The shared ``sample_project`` fixture omits start_date / end_date.
    Milestone create requires the project to have a start date — patch
    the row in place so we don't have to spin up a separate project."""
    sample_project.start_date = datetime(2026, 5, 1)
    sample_project.end_date = datetime(2026, 12, 31)
    db_session.add(sample_project)
    db_session.commit()
    db_session.refresh(sample_project)
    return sample_project


def _create_url(project_id):
    return f"/api/v3/projects/{project_id}/milestones/create"


# ===========================================================================
# JSON path — unchanged
# ===========================================================================

class TestJsonPathRegression:
    def test_json_create_works_unchanged(
        self, client, admin_user, admin_headers, dated_project,
    ):
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            json={
                "name": "M-json",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["name"] == "M-json"
        # Doc 30: JSON path doesn't add comment/standaloneAttachments fields.
        assert "comment" not in d
        assert "standaloneAttachments" not in d

    def test_json_create_ignores_body_files_keys(
        self, client, admin_user, admin_headers, dated_project,
    ):
        """JSON path uses Pydantic's default ``extra='ignore'`` — extra
        keys like ``body`` / ``files`` in JSON are silently dropped (no
        comment / attachment is created)."""
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            json={
                "name": "M-json-ignored",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "body": "this is ignored on the JSON path",
                "files": ["this is also ignored"],
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert "comment" not in d
        assert "standaloneAttachments" not in d


# ===========================================================================
# Multipart — minimum fields, no inline attachments
# ===========================================================================

class TestMultipartNoAttachments:
    def test_multipart_empty_form_creates_milestone_only(
        self, client, admin_user, admin_headers, dated_project, temp_storage,
    ):
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-multipart-empty",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["name"] == "M-multipart-empty"
        assert "comment" not in d
        assert "standaloneAttachments" not in d


# ===========================================================================
# Multipart — body only (no files)
# ===========================================================================

class TestMultipartBodyOnly:
    def test_body_only_creates_milestone_and_comment_no_attachments(
        self, client, admin_user, admin_headers, dated_project,
        temp_storage, db_session,
    ):
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-body-only",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "body": "Initial planning note for this milestone.",
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["name"] == "M-body-only"
        # Comment payload embedded.
        assert "comment" in d
        assert d["comment"]["body"] == "Initial planning note for this milestone."
        assert d["comment"]["attachments"] == []
        # No standalone attachments key (since files only goes to that branch).
        assert "standaloneAttachments" not in d

        # DB sanity: 1 milestone, 1 comment row anchored to it, 0 attachment rows.
        ms_id = d["id"]
        assert (
            db_session.query(CommentModel)
            .filter(CommentModel.target_kind == "milestone")
            .filter(CommentModel.target_id == ms_id)
            .count()
        ) == 1
        assert (
            db_session.query(AttachmentModel)
            .filter(AttachmentModel.target_id == ms_id)
            .count()
        ) == 0


# ===========================================================================
# Multipart — body + files
# ===========================================================================

class TestMultipartBodyAndFiles:
    def test_body_with_files_creates_comment_with_bound_attachments(
        self, client, admin_user, admin_headers, dated_project,
        temp_storage, db_session,
    ):
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-body-files",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "body": "See attached spec",
            },
            files=[
                ("files", ("spec.pdf", b"%PDF-1.4 fake spec", "application/pdf")),
                ("files", ("notes.txt", b"plain notes", "text/plain")),
            ],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        # Comment carries the body AND the bound files.
        assert d["comment"]["body"] == "See attached spec"
        atts = d["comment"]["attachments"]
        assert len(atts) == 2
        names = {a["originalFilename"] for a in atts}
        assert names == {"spec.pdf", "notes.txt"}
        # No standalone attachments — files are bound to the comment.
        assert "standaloneAttachments" not in d

        # DB: 1 comment, 2 attachments, both with comment_id set, target_kind/id NULL.
        ms_id = d["id"]
        comment_rows = (
            db_session.query(CommentModel)
            .filter(CommentModel.target_id == ms_id)
            .all()
        )
        assert len(comment_rows) == 1
        cid = comment_rows[0].id
        att_rows = (
            db_session.query(AttachmentModel)
            .filter(AttachmentModel.comment_id == cid)
            .all()
        )
        assert len(att_rows) == 2
        for a in att_rows:
            assert a.target_kind is None
            assert a.target_id is None


# ===========================================================================
# Multipart — files only (no body)
# ===========================================================================

class TestMultipartFilesOnly:
    def test_files_only_creates_standalone_attachments(
        self, client, admin_user, admin_headers, dated_project,
        temp_storage, db_session,
    ):
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-files-only",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
            },
            files=[
                ("files", ("contract.pdf", b"%PDF-1.4 contract", "application/pdf")),
            ],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        # No comment row — files-only goes straight to standalone path.
        assert "comment" not in d
        assert "standaloneAttachments" in d
        sa = d["standaloneAttachments"]
        assert len(sa) == 1
        assert sa[0]["originalFilename"] == "contract.pdf"

        # DB: 0 comments, 1 attachment with target_kind/target_id set, comment_id NULL.
        ms_id = d["id"]
        assert (
            db_session.query(CommentModel)
            .filter(CommentModel.target_id == ms_id)
            .count()
        ) == 0
        att_rows = (
            db_session.query(AttachmentModel)
            .filter(AttachmentModel.target_kind == "milestone")
            .filter(AttachmentModel.target_id == ms_id)
            .all()
        )
        assert len(att_rows) == 1
        assert att_rows[0].comment_id is None


# ===========================================================================
# Multipart — error paths (validation + pre-flight checks)
# ===========================================================================

class TestMultipartValidationErrors:
    def test_disallowed_extension_rejects_before_milestone_create(
        self, client, admin_user, admin_headers, dated_project,
        temp_storage, db_session,
    ):
        """Bad file extension must be caught BEFORE the milestone is
        created. Pre-doc-30 the comment service would catch it AFTER
        the milestone insert, leaving an orphan."""
        pre_count = db_session.query(MilestoneModel).count()
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-bad-ext",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "body": "with malware",
            },
            files=[
                ("files", ("evil.exe", b"MZ\x00", "application/octet-stream")),
            ],
        )
        assert resp.status_code == 422, resp.text
        # No milestone was created.
        post_count = db_session.query(MilestoneModel).count()
        assert post_count == pre_count

    def test_oversize_file_rejects_before_milestone_create(
        self, client, admin_user, admin_headers, dated_project,
        temp_storage, db_session, monkeypatch,
    ):
        """File larger than ATTACHMENTS_MAX_BYTES rejects before insert."""
        # Bring the cap right down to make a tiny "oversize" payload.
        monkeypatch.setattr(settings, "ATTACHMENTS_MAX_BYTES", 5)
        pre_count = db_session.query(MilestoneModel).count()
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-oversize",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
            },
            files=[
                ("files", ("big.txt", b"this is more than 5 bytes", "text/plain")),
            ],
        )
        assert resp.status_code == 422, resp.text
        post_count = db_session.query(MilestoneModel).count()
        assert post_count == pre_count

    def test_malformed_dependsOn_returns_422(
        self, client, admin_user, admin_headers, dated_project, temp_storage,
    ):
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-bad-deps",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "dependsOn": "not-json-just-a-string",
            },
        )
        assert resp.status_code == 422, resp.text

    def test_malformed_vendors_returns_422(
        self, client, admin_user, admin_headers, dated_project, temp_storage,
    ):
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-bad-vendors",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "vendors": "{not-json}",
            },
        )
        assert resp.status_code == 422

    def test_dependsOn_array_decoded_correctly(
        self, client, admin_user, admin_headers, dated_project, temp_storage,
    ):
        """JSON-encoded dependsOn array gets decoded + resolved against
        existing milestones — same behavior as the JSON path.

        Doc 31 (post-rebase) added milestone-specific dep-date rules:
          source.start_date >= target.start_date  (equality OK)
          source.end_date   >  target.end_date    (strict)
        Both must hold. The dates below are deliberately chosen so the
        dependent ends strictly later than the target — the test's
        focus is JSON-array decoding, not the dep-date rules
        themselves (those have their own coverage in test_doc31_*).
        """
        # Target: shorter end than the dependent so the strict
        # end-after rule passes downstream.
        m1 = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            json={
                "name": "M-target",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-15T00:00:00+05:30",
            },
        ).json()["data"]
        # Dependent: same start (equality OK), end strictly later than M1.
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-dependent",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "dependsOn": json.dumps([m1["displayCode"]]),
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["dependsOn"] == [m1["id"]]
        assert d["dependsOnDisplay"] == [m1["displayCode"]]

    def test_invalid_milestone_field_returns_422(
        self, client, admin_user, admin_headers, dated_project, temp_storage,
    ):
        # name missing — Pydantic validator should fire.
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
            },
        )
        assert resp.status_code == 422


# ===========================================================================
# Composes correctly with doc 29 (calendar-date normalization)
# ===========================================================================

class TestComposesWithDoc29:
    def test_same_calendar_dates_as_project_via_multipart(
        self, client, admin_user, admin_headers, dated_project, temp_storage,
    ):
        """Multipart path goes through the same Pydantic validators as
        JSON, so doc 29's IstCalendarDate normalization applies. Same-
        calendar-date project + milestone (which would have been the
        original bug pre-doc-29) is accepted."""
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-same-dates",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "body": "with same dates as project",
            },
            files=[
                ("files", ("note.pdf", b"%PDF-1.4 note", "application/pdf")),
            ],
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["comment"]["body"] == "with same dates as project"
        assert len(d["comment"]["attachments"]) == 1


# ===========================================================================
# Empty-string optional fields + JSON-safe Pydantic error envelopes
#
# Swagger UI's "Try it out" auto-fills every form input with a blank string
# when the user clears a placeholder, so a multipart POST routinely arrives
# with ``status=`` (empty), ``description=`` (empty), etc. Pre-fix:
#   1. The parser passed the empty string through to Pydantic, which rejected
#      it (e.g. status='' is not in the enum), turning a benign "field omitted"
#      into a 422.
#   2. Worse — Pydantic v2 errors carry a ``ctx`` dict that may contain the
#      raw underlying ``ValueError``, which is not JSON-serializable. The
#      422 envelope rendering then crashed with
#      ``TypeError: Object of type ValueError is not JSON serializable``,
#      surfacing as a 500 instead of the intended 422.
# Fix: parser skips empty strings for optional fields; ``_sanitize_pydantic_errors``
# strips ``ctx`` and stringifies any leftover Exception values.
# ===========================================================================

class TestEmptyOptionalFieldsAndSafeErrors:
    def test_empty_optional_fields_treated_as_omitted(
        self, client, admin_user, admin_headers, dated_project, temp_storage,
    ):
        """``status=`` and ``description=`` (empty strings) must be ignored,
        not rejected — Swagger UI sends them by default when the user
        clears a placeholder."""
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-empty-optionals",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "description": "",   # empty optional → must be skipped
                "status": "",        # empty optional → must be skipped
                "dependsOn": "",     # empty optional array → must be skipped
                "vendors": "",       # empty optional array → must be skipped
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        # Defaults flowed through: status defaults to ``not_completed`` at
        # the service layer.
        assert d["status"] == "not_completed"
        # Empty arrays default to [] (no rejection, no None-blow-up).
        assert d["dependsOn"] == []
        assert d["vendors"] == []

    def test_invalid_status_returns_422_not_500(
        self, client, admin_user, admin_headers, dated_project, temp_storage,
    ):
        """A non-empty BUT invalid ``status`` must surface as a 422 with a
        JSON-safe error envelope. Pre-fix this returned 500 because
        Pydantic's ``ctx`` field carried a raw ValueError instance and the
        error renderer choked on ``json.dumps``."""
        resp = client.post(
            _create_url(dated_project.id),
            headers=admin_headers,
            data={
                "name": "M-bad-status",
                "startDate": "2026-05-04T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
                "status": "not_a_real_status",
            },
        )
        assert resp.status_code == 422, resp.text
        # Envelope must be valid JSON (would have been a 500 pre-fix).
        body = resp.json()
        # Outer envelope: {data, message, error, status}; the HAL+JSON
        # error payload lives under ``error``.
        assert body.get("status") == 422
        err = body.get("error") or {}
        assert err.get("_type") == "Error"
        assert err.get("errorIdentifier") == "validation_error"
        details = err.get("_embedded", {}).get("details", {})
        errors = details.get("errors", [])
        assert isinstance(errors, list) and len(errors) >= 1
        for err in errors:
            assert "ctx" not in err, "ctx must be stripped (not JSON-safe)"
            for k, v in err.items():
                # Sanity: every value round-trips through json.
                json.dumps(v)
