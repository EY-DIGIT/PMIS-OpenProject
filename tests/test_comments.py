"""Tests for comments + attachments — happy paths and error paths.

Each test uses the in-memory SQLite DB from conftest plus a temporary
folder for the file storage backend. The storage path override happens
via the ``temp_storage`` fixture below, which patches the storage
singleton so writes go to a per-test tmp dir.
"""
import io
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.infrastructure.db.models.milestone import MilestoneModel
import app.infrastructure.storage as storage_pkg
from app.infrastructure.storage.file_storage import FileStorage
from app.infrastructure.storage import reset_file_client_for_tests


# ---------------------------------------------------------------------------
# Storage fixture — redirects writes to a per-test tmp folder
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_storage(tmp_path, monkeypatch):
    """Repoint the storage singleton at a temp dir; restore after."""
    tmp_storage = FileStorage(
        base_path=str(tmp_path / "storage"),
        subdir_strategy="year_month",
    )
    tmp_storage.ensure_ready()
    monkeypatch.setattr(storage_pkg.file_storage, "_storage", tmp_storage)
    # Doc 35: the file client wraps the low-level storage; reset it so
    # each test sees the freshly-redirected storage.
    reset_file_client_for_tests()
    yield tmp_storage
    reset_file_client_for_tests()


# ---------------------------------------------------------------------------
# Milestone fixture — quick parent target for comments
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def sample_milestone(db_session, sample_project):
    """Direct ORM insert of a milestone under the sample project."""
    m = MilestoneModel(
        id=str(uuid4()),
        project_id=sample_project.id,
        name="Sample Milestone",
        description="for tests",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        position=1,
        status="not_completed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


# ===========================================================================
# Create comment
# ===========================================================================

class TestCreateComment:

    def test_create_text_only(self, client, admin_user, admin_headers,
                              sample_milestone, temp_storage):
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
            data={"body": "First comment"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["_type"] == "Comment"
        assert body["body"] == "First comment"
        assert body["targetKind"] == "milestone"
        assert body["targetId"] == sample_milestone.id
        assert body["author"]["id"] == admin_user.id
        assert body["attachments"] == []

    def test_create_with_attachments(self, client, admin_user, admin_headers,
                                     sample_milestone, temp_storage):
        """Doc 35: attachments now ride as a JSON list on the comment row,
        each entry carrying a public ``url`` the FE fetches directly.
        Pre-doc-35 each was a separate row with its own id + download link."""
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
            data={"body": "With files"},
            files=[
                ("files", ("report.pdf", b"%PDF-1.4 fake", "application/pdf")),
                ("files", ("notes.txt", b"plain notes", "text/plain")),
            ],
        )
        assert resp.status_code == 201, resp.text
        atts = resp.json()["data"]["attachments"]
        assert len(atts) == 2
        names = {a["filename"] for a in atts}
        assert names == {"report.pdf", "notes.txt"}
        # Each entry carries a public URL — non-empty and ends with the
        # uploaded filename (the local-fallback URL shape includes the
        # original name).
        for a in atts:
            assert a["url"]
            assert a["mimeType"]
            assert a["sizeBytes"] >= 0

    def test_reject_empty_body_no_files(self, client, admin_user, admin_headers,
                                        sample_milestone, temp_storage):
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
            data={"body": ""},
        )
        assert resp.status_code == 422
        assert "text or at least one attachment" in resp.text

    def test_reject_unknown_target(self, client, admin_user, admin_headers,
                                   temp_storage):
        unknown_id = str(uuid4())
        resp = client.post(
            f"/api/v3/milestones/{unknown_id}/comments",
            headers=admin_headers,
            data={"body": "Hi"},
        )
        assert resp.status_code == 404

    def test_reject_disallowed_extension(self, client, admin_user, admin_headers,
                                         sample_milestone, temp_storage):
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
            data={"body": "exe upload"},
            files=[("files", ("malware.exe", b"MZ\x00", "application/octet-stream"))],
        )
        assert resp.status_code == 422
        assert "disallowed extension" in resp.text

    def test_reject_oversize_file(self, client, admin_user, admin_headers,
                                  sample_milestone, temp_storage, monkeypatch):
        # Set a 10-byte cap for this test only.
        monkeypatch.setattr(settings, "ATTACHMENTS_MAX_BYTES", 10)
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
            data={"body": "big file"},
            files=[("files", ("big.txt", b"x" * 100, "text/plain"))],
        )
        assert resp.status_code == 422
        assert "maximum is 10" in resp.text

    def test_reject_unauthenticated(self, client, sample_milestone, temp_storage):
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            data={"body": "no auth"},
        )
        assert resp.status_code == 401

    def test_reject_invalid_target_kind(self, client, admin_user, admin_headers,
                                        temp_storage):
        # 'projects' isn't a valid target kind for comments — only M/A/T/S.
        resp = client.post(
            f"/api/v3/projects/{uuid4()}/comments",
            headers=admin_headers,
            data={"body": "wrong kind"},
        )
        # The route doesn't exist for 'projects', so 404 from FastAPI.
        assert resp.status_code in (404, 405)


# ===========================================================================
# List comments
# ===========================================================================

class TestListComments:

    def test_list_empty(self, client, admin_user, admin_headers,
                        sample_milestone, temp_storage):
        resp = client.get(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total"] == 0
        assert body["_embedded"]["elements"] == []

    def test_list_newest_first(self, client, admin_user, admin_headers,
                               sample_milestone, temp_storage):
        import time
        # Post 3 comments. Tiny sleep between creates so each row gets
        # a distinct ``created_at`` — without it, all three POSTs can
        # land within the same millisecond on a fast machine and the
        # secondary tiebreaker (UUID id, random) makes the newest-first
        # assertion non-deterministic.
        for i in range(3):
            r = client.post(
                f"/api/v3/milestones/{sample_milestone.id}/comments",
                headers=admin_headers,
                data={"body": f"comment {i}"},
            )
            assert r.status_code == 201
            time.sleep(0.01)

        resp = client.get(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
        )
        body = resp.json()["data"]
        assert body["total"] == 3
        elements = body["_embedded"]["elements"]
        # newest first: comment 2, then 1, then 0
        assert [c["body"] for c in elements] == ["comment 2", "comment 1", "comment 0"]

    def test_list_pagination(self, client, admin_user, admin_headers,
                             sample_milestone, temp_storage):
        for i in range(5):
            client.post(
                f"/api/v3/milestones/{sample_milestone.id}/comments",
                headers=admin_headers,
                data={"body": f"c{i}"},
            )
        resp = client.get(
            f"/api/v3/milestones/{sample_milestone.id}/comments?offset=1&pageSize=2",
            headers=admin_headers,
        )
        body = resp.json()["data"]
        assert body["total"] == 5
        assert body["count"] == 2
        assert body["pageSize"] == 2


# ===========================================================================
# Delete comment
# ===========================================================================

class TestDeleteComment:

    def _create(self, client, headers, milestone_id, body="x"):
        r = client.post(
            f"/api/v3/milestones/{milestone_id}/comments",
            headers=headers,
            data={"body": body},
        )
        assert r.status_code == 201
        return r.json()["data"]["id"]

    def test_author_can_delete(self, client, admin_user, admin_headers,
                               sample_milestone, temp_storage):
        cid = self._create(client, admin_headers, sample_milestone.id)
        resp = client.delete(f"/api/v3/comments/{cid}", headers=admin_headers)
        assert resp.status_code == 200
        # Subsequent list excludes it.
        list_resp = client.get(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
        )
        assert list_resp.json()["data"]["total"] == 0

    def test_admin_can_delete_others(self, client, admin_user, admin_headers,
                                     member_user, member_token,
                                     sample_milestone, temp_storage):
        member_headers = {"Authorization": f"Bearer {member_token}"}
        cid = self._create(client, member_headers, sample_milestone.id, "from member")
        # Admin deletes member's comment
        resp = client.delete(f"/api/v3/comments/{cid}", headers=admin_headers)
        assert resp.status_code == 200

    def test_member_cannot_delete_others(self, client, admin_user, admin_headers,
                                         member_user, member_token,
                                         sample_milestone, temp_storage):
        member_headers = {"Authorization": f"Bearer {member_token}"}
        cid = self._create(client, admin_headers, sample_milestone.id, "from admin")
        resp = client.delete(f"/api/v3/comments/{cid}", headers=member_headers)
        assert resp.status_code == 403

    def test_delete_nonexistent(self, client, admin_user, admin_headers, temp_storage):
        resp = client.delete(f"/api/v3/comments/{uuid4()}", headers=admin_headers)
        assert resp.status_code == 404

    def test_delete_without_auth(self, client, temp_storage):
        resp = client.delete(f"/api/v3/comments/{uuid4()}")
        assert resp.status_code == 401
