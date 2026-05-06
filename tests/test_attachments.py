"""Tests for the standalone-attachment endpoints (doc 35: collapsed onto comments).

After doc 35 there's no separate ``attachments`` table. The
``POST/GET/DELETE /<entity>/{id}/attachments`` endpoints still exist
on the wire but route into the unified comments services — a "standalone
attachment" is a comment row with NULL body and a one-element
``attachments`` JSON array.

The streaming-download endpoint ``GET /attachments/{id}/download`` is
gone. Clients fetch bytes directly from ``attachments[i].url`` on the
comment row (or from the local-fallback ``GET /files/{key}`` route in
dev).

This file focuses on the standalone-attachment lifecycle:
  * POST file (no body)         → 201 with NULL body + 1 attachment URL
  * GET list                     → only file-only rows (body is NULL)
  * DELETE                       → soft-deletes the comment row
  * No download endpoint         → asserted 404 for legacy clients
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.models.milestone import MilestoneModel
import app.infrastructure.storage as storage_pkg
from app.infrastructure.storage.file_storage import FileStorage
from app.infrastructure.storage import reset_file_client_for_tests


# ---------------------------------------------------------------------------
# Shared fixtures — temp storage + sample milestone target
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_storage(tmp_path, monkeypatch):
    tmp = FileStorage(base_path=str(tmp_path / "storage"), subdir_strategy="year_month")
    tmp.ensure_ready()
    monkeypatch.setattr(storage_pkg.file_storage, "_storage", tmp)
    # Doc 35: the file client wraps the low-level storage; reset it so
    # each test sees the freshly-redirected storage.
    reset_file_client_for_tests()
    yield tmp
    reset_file_client_for_tests()


@pytest.fixture(scope="function")
def sample_milestone(db_session, sample_project):
    m = MilestoneModel(
        id=str(uuid4()),
        project_id=sample_project.id,
        name="M for attachments",
        description="-",
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
# Upload
# ===========================================================================

class TestUploadAttachment:

    def test_upload_success_creates_body_null_comment(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        """Doc 35: upload creates a comment row whose body is NULL and
        whose ``attachments`` JSON array carries one entry. The wire
        shape is the comment shape (so the FE iterates ``attachments``
        the same way it does for body+files comments)."""
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["_type"] == "Comment"
        assert body["targetKind"] == "milestone"
        assert body["targetId"] == sample_milestone.id
        # File-only send: body is empty / null.
        assert (body.get("body") or "") == ""
        # Single attachment in the JSON list, with the URL the FE fetches.
        atts = body["attachments"]
        assert len(atts) == 1
        att = atts[0]
        assert att["filename"] == "doc.pdf"
        assert att["mimeType"] == "application/pdf"
        assert att["sizeBytes"] == len(b"%PDF-1.4")
        assert att["url"]  # non-empty

    def test_upload_target_not_found(
        self, client, admin_user, admin_headers, temp_storage,
    ):
        resp = client.post(
            f"/api/v3/milestones/{uuid4()}/attachments",
            headers=admin_headers,
            files={"file": ("x.pdf", b"ok", "application/pdf")},
        )
        assert resp.status_code == 404

    def test_upload_disallowed_extension(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        )
        assert resp.status_code == 422
        assert "disallowed extension" in resp.text

    def test_upload_unauthenticated(self, client, sample_milestone, temp_storage):
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            files={"file": ("a.pdf", b"x", "application/pdf")},
        )
        assert resp.status_code == 401


# ===========================================================================
# List standalone (= body-NULL comment rows for that target)
# ===========================================================================

class TestListStandaloneAttachments:

    def test_list_empty(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        resp = client.get(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_list_excludes_comment_attachments(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        """Doc 35: the standalone listing must show only body-NULL rows.
        A comment row with body+files belongs in ``/comments``, not here."""
        # Upload one standalone (body-NULL row).
        client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("standalone.pdf", b"a", "application/pdf")},
        )
        # Post a comment WITH a file (body present + files): goes into
        # the same comments table but with body, so it's filtered out
        # of the standalone listing.
        client.post(
            f"/api/v3/milestones/{sample_milestone.id}/comments",
            headers=admin_headers,
            data={"body": "with file"},
            files=[("files", ("via_comment.pdf", b"b", "application/pdf"))],
        )
        resp = client.get(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
        )
        body = resp.json()["data"]
        assert body["total"] == 1
        sole = body["_embedded"]["elements"][0]
        assert sole["attachments"][0]["filename"] == "standalone.pdf"
        # And it is body-null.
        assert (sole.get("body") or "") == ""


# ===========================================================================
# Download endpoint REMOVED (doc 35)
# ===========================================================================

class TestDownloadEndpointRemoved:

    def test_legacy_download_route_returns_404(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        """Pre-doc-35 the BE streamed bytes via /attachments/{id}/download.
        After doc 35 the route is gone — clients fetch from the URL
        stored on the comment row's ``attachments[].url`` directly."""
        resp = client.get(
            f"/api/v3/attachments/{uuid4()}/download",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_uploaded_file_url_is_resolvable_via_local_fallback(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        """Sanity: the URL stored on the row must actually serve bytes
        when the local fallback is enabled (the dev / no-external-server
        case). Production deployments with FILE_SERVER_PUBLIC_BASE_URL
        set point the URL elsewhere; that's covered by separate tests."""
        up = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("hello.pdf", b"hello world", "application/pdf")},
        )
        url = up.json()["data"]["attachments"][0]["url"]
        # The URL is a relative storage_key in the local-fallback case
        # (no FILE_SERVER_PUBLIC_BASE_URL set in tests). The fallback
        # route lives at /files/{key:path}.
        if not url.startswith("http"):
            fetch_url = f"/files/{url}"
        else:
            fetch_url = url
        resp = client.get(fetch_url)
        assert resp.status_code == 200
        assert resp.content == b"hello world"


# ===========================================================================
# Delete (alias for delete-comment)
# ===========================================================================

class TestDeleteAttachment:

    def _upload(self, client, headers, milestone_id):
        """Doc 35: the response carries the comment-row id. Treat it as
        the attachment-id for downstream DELETE / GET calls."""
        r = client.post(
            f"/api/v3/milestones/{milestone_id}/attachments",
            headers=headers,
            files={"file": ("f.pdf", b"x", "application/pdf")},
        )
        assert r.status_code == 201
        return r.json()["data"]["id"]

    def test_uploader_can_delete(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        aid = self._upload(client, admin_headers, sample_milestone.id)
        resp = client.delete(f"/api/v3/attachments/{aid}", headers=admin_headers)
        assert resp.status_code == 200
        # Subsequent list excludes it (soft-deleted).
        list_resp = client.get(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
        )
        assert list_resp.json()["data"]["total"] == 0

    def test_member_cannot_delete_admins(
        self, client, admin_user, admin_headers, member_user, member_token,
        sample_milestone, temp_storage,
    ):
        member_headers = {"Authorization": f"Bearer {member_token}"}
        aid = self._upload(client, admin_headers, sample_milestone.id)
        resp = client.delete(f"/api/v3/attachments/{aid}", headers=member_headers)
        assert resp.status_code == 403

    def test_admin_can_delete_others(
        self, client, admin_user, admin_headers, member_user, member_token,
        sample_milestone, temp_storage,
    ):
        member_headers = {"Authorization": f"Bearer {member_token}"}
        aid = self._upload(client, member_headers, sample_milestone.id)
        resp = client.delete(f"/api/v3/attachments/{aid}", headers=admin_headers)
        assert resp.status_code == 200

    def test_delete_nonexistent(
        self, client, admin_user, admin_headers, temp_storage,
    ):
        resp = client.delete(
            f"/api/v3/attachments/{uuid4()}", headers=admin_headers,
        )
        assert resp.status_code == 404
