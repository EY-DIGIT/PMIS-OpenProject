"""Tests for standalone attachments — upload, download, list, delete.

Comment-bound attachments are exercised in test_comments.py via the
"create with files" scenarios; this file focuses on the standalone
attachment lifecycle (no comment).
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.models.milestone import MilestoneModel
import app.infrastructure.storage as storage_pkg
from app.infrastructure.storage.file_storage import FileStorage


# ---------------------------------------------------------------------------
# Shared fixtures — temp storage + sample milestone target
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_storage(tmp_path, monkeypatch):
    tmp = FileStorage(base_path=str(tmp_path / "storage"), subdir_strategy="year_month")
    tmp.ensure_ready()
    monkeypatch.setattr(storage_pkg.file_storage, "_storage", tmp)
    yield tmp


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

    def test_upload_success(self, client, admin_user, admin_headers,
                            sample_milestone, temp_storage):
        resp = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["_type"] == "Attachment"
        assert body["originalFilename"] == "doc.pdf"
        assert body["targetKind"] == "milestone"
        assert body["targetId"] == sample_milestone.id
        assert body["commentId"] is None
        assert body["sizeBytes"] == len(b"%PDF-1.4")
        assert body["uploadedBy"]["id"] == admin_user.id

    def test_upload_target_not_found(self, client, admin_user, admin_headers,
                                     temp_storage):
        resp = client.post(
            f"/api/v3/milestones/{uuid4()}/attachments",
            headers=admin_headers,
            files={"file": ("x.pdf", b"ok", "application/pdf")},
        )
        assert resp.status_code == 404

    def test_upload_disallowed_extension(self, client, admin_user, admin_headers,
                                         sample_milestone, temp_storage):
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
# List standalone
# ===========================================================================

class TestListStandaloneAttachments:

    def test_list_empty(self, client, admin_user, admin_headers,
                        sample_milestone, temp_storage):
        resp = client.get(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_list_excludes_comment_attachments(self, client, admin_user,
                                               admin_headers, sample_milestone,
                                               temp_storage):
        # Upload one standalone
        client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("standalone.pdf", b"a", "application/pdf")},
        )
        # Post a comment with an attachment (should NOT appear in standalone list)
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
        assert body["_embedded"]["elements"][0]["originalFilename"] == "standalone.pdf"


# ===========================================================================
# Download
# ===========================================================================

class TestDownloadAttachment:

    def _upload(self, client, headers, milestone_id, name="d.pdf", content=b"hello"):
        r = client.post(
            f"/api/v3/milestones/{milestone_id}/attachments",
            headers=headers,
            files={"file": (name, content, "application/pdf")},
        )
        assert r.status_code == 201
        return r.json()["data"]["id"]

    def test_download_streams_content(self, client, admin_user, admin_headers,
                                      sample_milestone, temp_storage):
        aid = self._upload(client, admin_headers, sample_milestone.id,
                           "report.pdf", b"the bytes")
        resp = client.get(
            f"/api/v3/attachments/{aid}/download",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.content == b"the bytes"
        cd = resp.headers.get("content-disposition", "")
        assert "report.pdf" in cd

    def test_download_not_found(self, client, admin_user, admin_headers,
                                temp_storage):
        resp = client.get(
            f"/api/v3/attachments/{uuid4()}/download",
            headers=admin_headers,
        )
        assert resp.status_code == 404


# ===========================================================================
# Delete
# ===========================================================================

class TestDeleteAttachment:

    def _upload(self, client, headers, milestone_id):
        r = client.post(
            f"/api/v3/milestones/{milestone_id}/attachments",
            headers=headers,
            files={"file": ("f.pdf", b"x", "application/pdf")},
        )
        assert r.status_code == 201
        return r.json()["data"]["id"]

    def test_uploader_can_delete(self, client, admin_user, admin_headers,
                                 sample_milestone, temp_storage):
        aid = self._upload(client, admin_headers, sample_milestone.id)
        resp = client.delete(f"/api/v3/attachments/{aid}", headers=admin_headers)
        assert resp.status_code == 200
        # subsequent download fails (soft-deleted hides it)
        dl = client.get(
            f"/api/v3/attachments/{aid}/download", headers=admin_headers,
        )
        assert dl.status_code == 404

    def test_member_cannot_delete_admins(self, client, admin_user, admin_headers,
                                         member_user, member_token,
                                         sample_milestone, temp_storage):
        member_headers = {"Authorization": f"Bearer {member_token}"}
        aid = self._upload(client, admin_headers, sample_milestone.id)
        resp = client.delete(f"/api/v3/attachments/{aid}", headers=member_headers)
        assert resp.status_code == 403

    def test_admin_can_delete_others(self, client, admin_user, admin_headers,
                                     member_user, member_token,
                                     sample_milestone, temp_storage):
        member_headers = {"Authorization": f"Bearer {member_token}"}
        aid = self._upload(client, member_headers, sample_milestone.id)
        resp = client.delete(f"/api/v3/attachments/{aid}", headers=admin_headers)
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client, admin_user, admin_headers,
                                temp_storage):
        resp = client.delete(f"/api/v3/attachments/{uuid4()}",
                             headers=admin_headers)
        assert resp.status_code == 404
