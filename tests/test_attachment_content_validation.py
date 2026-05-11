"""Tests for the magic-byte content-sniff guard on file uploads.

Covers:
  * Direct unit tests on ``app.shared.file_signature.detect_and_verify``
    — positive (valid PDF / JPEG / PNG / ZIP-as-DOCX / plain text) and
    negative (disguised EXE / ELF / ZIP-as-PDF / empty / null-bytes in
    text / non-UTF-8 in text).
  * Integration tests on the standalone-attachment HTTP endpoint
    (``POST /milestones/{id}/attachments``) — verifies the guard wires
    up correctly through the create_comment service.

Sample magic-byte snippets used here are hand-crafted (small bytes
prefixes). filetype only needs the first 261 bytes for its widest
signature so tiny snippets are sufficient.
"""
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import pytest

from app.core.errors import ValidationError
from app.infrastructure.db.models.milestone import MilestoneModel
from app.shared.file_signature import detect_and_verify
import app.infrastructure.storage as storage_pkg
from app.infrastructure.storage.file_storage import FileStorage
from app.infrastructure.storage import reset_file_client_for_tests


# ---------------------------------------------------------------------------
# Magic-byte / content snippets — minimal valid prefixes per format.
# ---------------------------------------------------------------------------
PDF_HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8  # PNG starts with this 8-byte signature
JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 8
GIF_HEADER = b"GIF89a" + b"\x00" * 8
# Minimal ZIP — PK signature + an end-of-central-directory record.
# Office docs (.docx/.xlsx/.pptx) are ZIP archives so this also serves
# as the positive case for them when filetype detects ``application/zip``.
ZIP_BYTES = (
    b"PK\x05\x06" + b"\x00" * 18  # end-of-central-directory only
)
# Disguise payloads — common binary magic that should never appear under
# the listed-allowed extensions.
PE_EXE = b"MZ\x90\x00" + b"\x00" * 60   # Windows PE/EXE header
ELF_BIN = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8  # Linux ELF header


# ---------------------------------------------------------------------------
# Shared fixtures — same temp storage + milestone target used in
# test_attachments.py, lifted here so this file is self-contained.
# ---------------------------------------------------------------------------

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


@pytest.fixture(scope="function")
def sample_milestone(db_session, sample_project):
    m = MilestoneModel(
        id=str(uuid4()),
        project_id=sample_project.id,
        name="M for content-sniff tests",
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
# Direct unit tests on detect_and_verify
# ===========================================================================

class TestDetectAndVerifyPositive:
    def test_valid_pdf(self):
        mime, ext = detect_and_verify(BytesIO(PDF_HEADER), "doc.pdf")
        assert mime == "application/pdf"
        assert ext == "pdf"

    def test_valid_jpeg(self):
        mime, _ = detect_and_verify(BytesIO(JPEG_HEADER), "photo.jpg")
        assert mime == "image/jpeg"

    def test_valid_jpeg_with_jpeg_extension(self):
        mime, _ = detect_and_verify(BytesIO(JPEG_HEADER), "photo.jpeg")
        assert mime == "image/jpeg"

    def test_valid_png(self):
        mime, _ = detect_and_verify(BytesIO(PNG_HEADER), "img.png")
        assert mime == "image/png"

    def test_valid_gif(self):
        mime, _ = detect_and_verify(BytesIO(GIF_HEADER), "anim.gif")
        assert mime == "image/gif"

    def test_zip_as_docx_passes(self):
        """Office docs are zip-based; filetype detects them as
        ``application/zip``. The allowlist for ``.docx`` allows both
        ``application/zip`` and the Office MIME so legitimate Office
        files don't get rejected."""
        mime, _ = detect_and_verify(BytesIO(ZIP_BYTES), "report.docx")
        assert mime == "application/zip"

    def test_zip_as_xlsx_passes(self):
        mime, _ = detect_and_verify(BytesIO(ZIP_BYTES), "data.xlsx")
        assert mime == "application/zip"

    def test_zip_as_pptx_passes(self):
        mime, _ = detect_and_verify(BytesIO(ZIP_BYTES), "deck.pptx")
        assert mime == "application/zip"

    def test_valid_text_ascii(self):
        mime, _ = detect_and_verify(
            BytesIO(b"Hello world\nThis is a plain text file."), "notes.txt",
        )
        assert mime == "text/plain"

    def test_valid_text_utf8_with_unicode(self):
        mime, _ = detect_and_verify(
            BytesIO("नमस्ते\nहिन्दी text".encode("utf-8")), "hindi.txt",
        )
        assert mime == "text/plain"

    def test_valid_csv(self):
        mime, _ = detect_and_verify(
            BytesIO(b"id,name,value\n1,alpha,42\n"), "data.csv",
        )
        assert mime == "text/plain"

    def test_rewinds_stream(self):
        """After verification the stream must be at offset 0 so the
        storage layer can read from the start."""
        buf = BytesIO(PDF_HEADER)
        detect_and_verify(buf, "doc.pdf")
        assert buf.tell() == 0


class TestDetectAndVerifyNegative:
    def test_disguised_exe_as_pdf(self):
        with pytest.raises(ValidationError) as exc:
            detect_and_verify(BytesIO(PE_EXE), "evil.pdf")
        msg = str(exc.value).lower()
        assert "content does not match" in msg
        assert ".pdf" in msg

    def test_disguised_elf_as_docx(self):
        with pytest.raises(ValidationError):
            detect_and_verify(BytesIO(ELF_BIN), "evil.docx")

    def test_disguised_zip_as_pdf(self):
        """ZIP bytes uploaded with a .pdf filename — ZIP is not in
        PDF's allowed-MIME set so this must reject."""
        with pytest.raises(ValidationError) as exc:
            detect_and_verify(BytesIO(ZIP_BYTES), "evil.pdf")
        assert "application/zip" in str(exc.value)

    def test_empty_file(self):
        with pytest.raises(ValidationError) as exc:
            detect_and_verify(BytesIO(b""), "empty.pdf")
        assert "empty" in str(exc.value).lower()

    def test_unknown_signature(self):
        """Bytes that don't match any known signature → reject.
        (Random ASCII that doesn't look like a known binary type.)"""
        with pytest.raises(ValidationError) as exc:
            detect_and_verify(BytesIO(b"random gibberish bytes"), "x.pdf")
        msg = str(exc.value).lower()
        assert "could not be recognised" in msg or "does not match" in msg

    def test_text_with_null_bytes_rejected(self):
        """Disguise: rename a binary to ``.txt``. Null bytes in the
        head → reject as not-real-text."""
        with pytest.raises(ValidationError) as exc:
            detect_and_verify(BytesIO(b"hello\x00world"), "evil.txt")
        assert "null" in str(exc.value).lower()

    def test_text_with_invalid_utf8(self):
        """Bytes that aren't valid UTF-8 + don't contain null bytes
        early. ``\xc3\x28`` is an invalid UTF-8 sequence (a multi-byte
        leader followed by an invalid continuation byte)."""
        with pytest.raises(ValidationError) as exc:
            detect_and_verify(BytesIO(b"hi \xc3\x28 there"), "evil.csv")
        assert "utf-8" in str(exc.value).lower()


# ===========================================================================
# Integration: HTTP path through standalone-attachment endpoint
# ===========================================================================

class TestUploadHTTPPath:
    def test_valid_pdf_upload_succeeds(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        r = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("doc.pdf", PDF_HEADER, "application/pdf")},
        )
        assert r.status_code == 201, r.text
        att = r.json()["data"]["attachments"][0]
        # Sniffed MIME is what's persisted — same value either way here
        # because the client also declared application/pdf, but the
        # important guarantee is that the server uses its detection,
        # not the client header.
        assert att["mimeType"] == "application/pdf"

    def test_disguised_exe_as_pdf_rejected(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        r = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("evil.pdf", PE_EXE, "application/pdf")},
        )
        assert r.status_code == 422, r.text
        body = r.json()
        assert "content does not match" in body["error"]["message"].lower()

    def test_disguised_exe_in_inline_multipart_rejected(
        self, client, admin_user, admin_headers, sample_project, temp_storage,
    ):
        """Path #2 wiring: the inline-multipart milestone-create flow
        (pre_validate_files) must also reject a disguised file."""
        r = client.post(
            f"/api/v3/projects/{sample_project.id}/milestones/create",
            headers=admin_headers,
            data={
                "name": "M with bad file",
                "startDate": "2026-07-01T00:00:00+05:30",
                "endDate": "2026-08-30T00:00:00+05:30",
                "priority": "P1",
            },
            files={"files": ("evil.pdf", PE_EXE, "application/pdf")},
        )
        assert r.status_code == 422, r.text
        assert "content does not match" in r.text.lower()

    def test_text_with_null_bytes_via_http_rejected(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        r = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            files={"file": ("evil.txt", b"hi\x00there", "text/plain")},
        )
        assert r.status_code == 422, r.text
        assert "null" in r.text.lower()

    def test_persisted_mime_is_sniffed_not_client_declared(
        self, client, admin_user, admin_headers, sample_milestone, temp_storage,
    ):
        """Send a PNG with a spoofed ``content-type: image/jpeg`` header.
        Server must persist ``image/png`` (the sniffed value)."""
        r = client.post(
            f"/api/v3/milestones/{sample_milestone.id}/attachments",
            headers=admin_headers,
            # Client declares JPEG but the bytes are PNG, and filename
            # is .png so the extension check + sniff both say PNG.
            files={"file": ("photo.png", PNG_HEADER, "image/jpeg")},
        )
        assert r.status_code == 201, r.text
        att = r.json()["data"]["attachments"][0]
        assert att["mimeType"] == "image/png"
