"""Tests for project-level file attachments.

The wire surface (see ``app/api/v3/projects/routes.py``):

  * ``POST /api/v3/projects/create``                — JSON unchanged;
    multipart now accepts ``files[]`` for inline attach at create time.
  * ``GET  /api/v3/projects/{id}``                  — response carries
    ``attachments[]`` array with the file metadata.
  * ``GET  /api/v3/projects/{id}/attachments``      — dedicated
    listing endpoint for the attachments tab.
  * ``POST /api/v3/projects/{id}/attachments``      — multipart, files
    only, for adding more after the project exists.
  * ``DELETE /api/v3/comments/{comment_id}``        — soft-delete an
    attached file (storage is the comments table; each upload is one
    comment row, ``body=NULL``).

Storage: the comments table with ``target_kind="project"``. FE never
sees a /comments URL for projects.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

import app.infrastructure.storage as storage_pkg
from app.infrastructure.storage.file_storage import FileStorage
from app.infrastructure.storage import reset_file_client_for_tests


PDF_HEADER = b"%PDF-1.4 test\n"
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


@pytest.fixture(scope="function")
def temp_storage(tmp_path, monkeypatch):
    tmp = FileStorage(
        base_path=str(tmp_path / "storage"),
        subdir_strategy="year_month",
    )
    tmp.ensure_ready()
    monkeypatch.setattr(storage_pkg.file_storage, "_storage", tmp)
    reset_file_client_for_tests()
    yield tmp
    reset_file_client_for_tests()


# ---------------------------------------------------------------------------
# POST /projects/create (multipart variant)
# ---------------------------------------------------------------------------

class TestCreateProjectWithInlineAttachments:
    def test_json_create_unchanged(
        self, client, admin_user, admin_headers, temp_storage,
    ):
        """JSON path keeps working; no attachments expected."""
        r = client.post(
            "/api/v3/projects/create",
            headers=admin_headers,
            json={
                "name": "JSON project",
                "owner": "tmd1",
                "startDate": "2026-07-01T00:00:00+05:30",
                "endDate": "2026-12-31T00:00:00+05:30",
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["name"] == "JSON project"
        # Multipart-only field; JSON path doesn't include it.
        assert "attachments" not in data

    def test_multipart_create_without_files_works(
        self, client, admin_user, admin_headers, temp_storage,
    ):
        r = client.post(
            "/api/v3/projects/create",
            headers=admin_headers,
            data={
                "name": "Multipart no files",
                "owner": "tmd1",
                "startDate": "2026-07-01T00:00:00+05:30",
                "endDate": "2026-12-31T00:00:00+05:30",
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["name"] == "Multipart no files"
        # Eager attachment fetch ran but found nothing.
        assert data.get("attachments") == []

    def test_multipart_create_with_files_attaches(
        self, client, admin_user, admin_headers, temp_storage,
    ):
        r = client.post(
            "/api/v3/projects/create",
            headers=admin_headers,
            data={
                "name": "Multipart with files",
                "owner": "tmd1",
                "startDate": "2026-07-01T00:00:00+05:30",
                "endDate": "2026-12-31T00:00:00+05:30",
            },
            files=[
                ("files", ("charter.pdf", PDF_HEADER, "application/pdf")),
                ("files", ("logo.png", PNG_HEADER, "image/png")),
            ],
        )
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        atts = data["attachments"]
        assert len(atts) == 2
        names = {a["filename"] for a in atts}
        assert names == {"charter.pdf", "logo.png"}
        # Sniffed MIME persisted, not the client-declared one.
        mime_by_name = {a["filename"]: a["mimeType"] for a in atts}
        assert mime_by_name["charter.pdf"] == "application/pdf"
        assert mime_by_name["logo.png"] == "image/png"

    def test_multipart_create_rejects_disguised_exe(
        self, client, admin_user, admin_headers, temp_storage,
    ):
        """Magic-byte sniff inherited from Workstream A — disguised
        binary rejected with the project never being created."""
        r = client.post(
            "/api/v3/projects/create",
            headers=admin_headers,
            data={
                "name": "Bad-file project",
                "owner": "tmd1",
                "startDate": "2026-07-01T00:00:00+05:30",
                "endDate": "2026-12-31T00:00:00+05:30",
            },
            files=[
                ("files", ("evil.pdf", b"MZ\x90\x00" + b"\x00" * 60,
                           "application/pdf")),
            ],
        )
        assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# GET /projects/{id}/attachments
# ---------------------------------------------------------------------------

class TestListProjectAttachments:
    def test_list_empty_initially(
        self, client, admin_user, admin_headers, sample_project, temp_storage,
    ):
        r = client.get(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["total"] == 0
        assert data["_embedded"]["elements"] == []

    def test_404_on_unknown_project(
        self, client, admin_user, admin_headers, temp_storage,
    ):
        r = client.get(
            f"/api/v3/projects/{uuid4()}/attachments",
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# POST /projects/{id}/attachments (post-create upload)
# ---------------------------------------------------------------------------

class TestUploadProjectAttachmentsAfterCreate:
    def test_upload_then_list(
        self, client, admin_user, admin_headers, sample_project, temp_storage,
    ):
        # Upload a file post-create.
        up = client.post(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
            files=[("files", ("rfp.pdf", PDF_HEADER, "application/pdf"))],
        )
        assert up.status_code == 201, up.text
        created = up.json()["data"]
        assert created["total"] == 1
        assert created["_embedded"]["elements"][0]["filename"] == "rfp.pdf"

        # The list endpoint should now return it.
        listed = client.get(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
        ).json()["data"]
        assert listed["total"] == 1
        assert listed["_embedded"]["elements"][0]["filename"] == "rfp.pdf"

    def test_empty_files_rejected(
        self, client, admin_user, admin_headers, sample_project, temp_storage,
    ):
        r = client.post(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
            files=[],
        )
        assert r.status_code == 422, r.text
        assert "required" in r.text.lower()

    def test_disguised_file_rejected_post_create(
        self, client, admin_user, admin_headers, sample_project, temp_storage,
    ):
        r = client.post(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
            files=[("files", ("evil.pdf",
                              b"MZ\x90\x00" + b"\x00" * 60,
                              "application/pdf"))],
        )
        assert r.status_code == 422, r.text

    def test_404_on_unknown_project(
        self, client, admin_user, admin_headers, temp_storage,
    ):
        r = client.post(
            f"/api/v3/projects/{uuid4()}/attachments",
            headers=admin_headers,
            files=[("files", ("doc.pdf", PDF_HEADER, "application/pdf"))],
        )
        assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# GET /projects/{id} includes attachments[]
# ---------------------------------------------------------------------------

class TestProjectDetailIncludesAttachments:
    def test_attachments_eagerly_loaded(
        self, client, admin_user, admin_headers, sample_project, temp_storage,
    ):
        client.post(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
            files=[("files", ("scope.pdf", PDF_HEADER, "application/pdf"))],
        )
        r = client.get(
            f"/api/v3/projects/{sample_project.id}",
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        atts = r.json()["data"]["attachments"]
        assert len(atts) == 1
        assert atts[0]["filename"] == "scope.pdf"


# ---------------------------------------------------------------------------
# Delete flow — same DELETE /comments/{id} as M/A/T/S
# ---------------------------------------------------------------------------

class TestDeleteProjectAttachment:
    def test_delete_via_comment_endpoint(
        self, client, admin_user, admin_headers, sample_project, temp_storage,
    ):
        up = client.post(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
            files=[("files", ("temp.pdf", PDF_HEADER, "application/pdf"))],
        )
        comment_id = up.json()["data"]["_embedded"]["elements"][0]["id"]
        # Storage is the comments table — DELETE on the comment id
        # removes the attachment.
        r = client.delete(
            f"/api/v3/comments/{comment_id}",
            headers=admin_headers,
        )
        assert r.status_code in (200, 204), r.text
        # List endpoint no longer sees it.
        listed = client.get(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
        ).json()["data"]
        assert listed["total"] == 0
