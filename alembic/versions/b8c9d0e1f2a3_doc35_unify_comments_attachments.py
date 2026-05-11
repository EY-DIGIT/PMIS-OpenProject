"""Doc 35: unify comments + attachments into a single comments row.

Revision ID: b8c9d0e1f2a3
Revises: f7a8b9c1d2e3
Create Date: 2026-05-06 18:00:00

(Note: the existing doc 34 series — commits ``8b61f1d`` / ``286dbad`` /
``efa045d`` — covers cascade soft-delete + delete-block + cascade-
restore on M/A/T/S entities. That work runs against the two-table
schema; this revision migrates that schema to the unified single-row
form so the cascade walk only needs to touch ``comments``.)

The senior product owner asked for the comments / attachments storage
model to look like an email send-event:

  * Each "send event" is one row in the comments table.
  * The row has either body text, an attachment, or both. Never edited
    after-the-fact (only soft-delete + new row on top of the trail).
  * The attachment lives on an external file server; the comments row
    stores the file's URL (with metadata) directly, not an FK to a
    separate attachments table.
  * Multiple files in one submission collapse into one row whose
    ``attachments`` JSON column carries the array.

Schema delta (this revision):

  comments table:
    + ``attachments`` JSON column (nullable) — list of objects
      ``{url, filename, mimeType, sizeBytes, uploadedAt}``.
    * ``body`` relaxed from NOT NULL to NULL — a row can now be
      file-only (body NULL) or comment-only (body present).

  attachments table:
    DROPPED entirely after data migration.

Data migration (also in upgrade()):

  For each live attachment row:
    * If ``comment_id`` is set: append its file metadata to the parent
      comment's ``attachments`` JSON array (URL = ``{public_base}/{storage_key}``).
    * If ``comment_id`` is NULL (standalone attachment): create a new
      comment row with ``body=NULL``, ``target_kind`` / ``target_id``
      from the attachment, and an ``attachments`` array of one entry.
  Soft-deleted attachment rows are not migrated — they're effectively
  hidden from the trail under the senior's "deleted is gone" rule.

Public base URL for the migrated rows comes from
``settings.FILE_SERVER_PUBLIC_BASE_URL``; if unset (typical for
existing deployments) it defaults to ``""`` and the URL ends up as a
relative path like ``"attachments/2026/04/abc.pdf"``. The local
fallback ``GET /files/{key}`` route added in this commit can serve
either form.

Downgrade is best-effort: it recreates the attachments table and
re-explodes the JSON array into rows. The original attachment ids are
NOT preserved (they're regenerated). Any callers that rely on the
original ids must restore from backup.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# JSON column type — Postgres uses JSONB, SQLite uses JSON. SQLAlchemy's
# ``sa.JSON`` resolves to the right thing per dialect.
# ---------------------------------------------------------------------------
def _json_col() -> sa.types.TypeEngine:
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ---- 1. comments: add attachments column + relax body NOT NULL --------
    with op.batch_alter_table("comments") as b:
        b.add_column(sa.Column("attachments", _json_col(), nullable=True))
        b.alter_column("body", existing_type=sa.Text(), nullable=True)

    # ---- 2. read existing attachments rows and fold into comments ---------
    # We use a small ad-hoc query (not the ORM) because the ORM models in
    # this revision will already be at the post-migration shape, which
    # would mismatch the live DB schema mid-migration.
    attachments_rows = bind.execute(sa.text(
        "SELECT id, comment_id, target_kind, target_id, original_filename, "
        "       storage_key, mime_type, size_bytes, uploaded_by_user_id, "
        "       uploaded_at, deleted_at "
        "FROM attachments "
        "WHERE deleted_at IS NULL"
    )).fetchall()

    # Pre-compute the public URL for legacy storage_keys. If the deployment
    # hasn't set FILE_SERVER_PUBLIC_BASE_URL yet, use the storage_key as-is —
    # the fallback /files/{key} route will resolve it locally.
    try:
        from app.core.config import settings
        public_base = (settings.FILE_SERVER_PUBLIC_BASE_URL or "").rstrip("/")
    except Exception:
        public_base = ""

    def to_url(storage_key: str) -> str:
        if public_base:
            return f"{public_base}/{storage_key}"
        # Path-only — the fallback route concatenates with its own prefix.
        return storage_key

    # Group attachments by comment_id (NULL → standalone bucket).
    by_comment: dict[str, list[dict]] = {}
    standalone: list[dict] = []
    for r in attachments_rows:
        entry = {
            "url": to_url(r.storage_key),
            "filename": r.original_filename,
            "mimeType": r.mime_type,
            "sizeBytes": r.size_bytes,
            "uploadedAt": r.uploaded_at.isoformat() if r.uploaded_at else None,
        }
        if r.comment_id is not None:
            by_comment.setdefault(r.comment_id, []).append(entry)
        else:
            standalone.append({
                **entry,
                "_target_kind": r.target_kind,
                "_target_id": r.target_id,
                "_uploaded_by_user_id": r.uploaded_by_user_id,
                "_uploaded_at": r.uploaded_at,
            })

    # Update each existing comment with its attachments array.
    for cid, entries in by_comment.items():
        bind.execute(
            sa.text("UPDATE comments SET attachments = :att WHERE id = :id"),
            {"att": json.dumps(entries), "id": cid},
        )

    # Insert one comment row per standalone attachment (body NULL).
    now = datetime.now(timezone.utc)
    for s in standalone:
        bind.execute(
            sa.text(
                "INSERT INTO comments "
                "(id, target_kind, target_id, body, attachments, "
                " author_user_id, created_at, updated_at, deleted_at, deleted_by) "
                "VALUES "
                "(:id, :tk, :ti, NULL, :att, :auid, :now, :now, NULL, NULL)"
            ),
            {
                "id": str(uuid4()),
                "tk": s["_target_kind"],
                "ti": s["_target_id"],
                "att": json.dumps([{
                    k: v for k, v in s.items() if not k.startswith("_")
                }]),
                "auid": s["_uploaded_by_user_id"],
                "now": s["_uploaded_at"] or now,
            },
        )

    # ---- 3. drop attachments table + its indexes -------------------------
    # batch_alter_table for SQLite portability of index drops.
    try:
        op.drop_index("idx_attachments_target", table_name="attachments")
    except Exception:
        pass
    try:
        op.drop_index("idx_attachments_target_active", table_name="attachments")
    except Exception:
        pass
    try:
        op.drop_index("idx_attachments_uploaded_at", table_name="attachments")
    except Exception:
        pass
    op.drop_table("attachments")


def downgrade() -> None:
    """Recreate the attachments table and explode the JSON arrays back
    into rows.

    Best-effort: original attachment IDs are NOT preserved (they're
    regenerated as fresh UUIDs). Callers depending on the original IDs
    should restore from backup instead.
    """
    bind = op.get_bind()

    # ---- 1. recreate attachments table -----------------------------------
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("comment_id", sa.String(length=36),
                  sa.ForeignKey("comments.id"), nullable=True),
        sa.Column("target_kind", sa.String(length=20), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(length=36),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(length=36),
                  sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "idx_attachments_target", "attachments",
        ["target_kind", "target_id"],
    )
    op.create_index(
        "idx_attachments_target_active", "attachments",
        ["target_kind", "target_id", "deleted_at"],
    )
    op.create_index(
        "idx_attachments_uploaded_at", "attachments",
        ["uploaded_at"],
    )

    # ---- 2. fan out each comment's JSON attachments to rows --------------
    # Standalone-only comments (body NULL) become standalone attachment
    # rows. Comments with body keep their row, with attachments table
    # entries linked back via comment_id.
    rows = bind.execute(sa.text(
        "SELECT id, target_kind, target_id, body, attachments, "
        "       author_user_id, created_at, updated_at "
        "FROM comments "
        "WHERE attachments IS NOT NULL"
    )).fetchall()

    for r in rows:
        # SQLite returns JSON as a string; Postgres returns a list / dict.
        att_value = r.attachments
        if isinstance(att_value, str):
            try:
                att_list = json.loads(att_value)
            except Exception:
                continue
        elif isinstance(att_value, list):
            att_list = att_value
        else:
            continue

        body_is_empty = (r.body is None) or (str(r.body).strip() == "")

        for entry in att_list:
            # Reconstruct a storage_key from the URL — strip any leading
            # public prefix so the bare relative path is preserved.
            url = entry.get("url") or ""
            try:
                from app.core.config import settings
                public_base = (settings.FILE_SERVER_PUBLIC_BASE_URL or "").rstrip("/")
            except Exception:
                public_base = ""
            storage_key = url
            if public_base and url.startswith(public_base + "/"):
                storage_key = url[len(public_base) + 1:]

            if body_is_empty:
                # Standalone attachment: comment_id NULL,
                # target_kind/target_id set.
                bind.execute(
                    sa.text(
                        "INSERT INTO attachments "
                        "(id, comment_id, target_kind, target_id, "
                        " original_filename, storage_key, mime_type, "
                        " size_bytes, uploaded_by_user_id, uploaded_at) "
                        "VALUES "
                        "(:id, NULL, :tk, :ti, :fn, :sk, :mt, :sz, :auid, :ua)"
                    ),
                    {
                        "id": str(uuid4()),
                        "tk": r.target_kind,
                        "ti": r.target_id,
                        "fn": entry.get("filename") or "unnamed",
                        "sk": storage_key,
                        "mt": entry.get("mimeType") or "application/octet-stream",
                        "sz": entry.get("sizeBytes") or 0,
                        "auid": r.author_user_id,
                        "ua": entry.get("uploadedAt") or r.created_at,
                    },
                )
            else:
                # Comment-bound attachment.
                bind.execute(
                    sa.text(
                        "INSERT INTO attachments "
                        "(id, comment_id, target_kind, target_id, "
                        " original_filename, storage_key, mime_type, "
                        " size_bytes, uploaded_by_user_id, uploaded_at) "
                        "VALUES "
                        "(:id, :cid, NULL, NULL, :fn, :sk, :mt, :sz, :auid, :ua)"
                    ),
                    {
                        "id": str(uuid4()),
                        "cid": r.id,
                        "fn": entry.get("filename") or "unnamed",
                        "sk": storage_key,
                        "mt": entry.get("mimeType") or "application/octet-stream",
                        "sz": entry.get("sizeBytes") or 0,
                        "auid": r.author_user_id,
                        "ua": entry.get("uploadedAt") or r.created_at,
                    },
                )

    # Body-empty + attachments-empty comments created during migration
    # for standalone rows can stay (they're effectively orphan rows
    # post-downgrade, but not visible in any list). Operators wanting a
    # cleaner rollback can DELETE them by hand.

    # ---- 3. revert comments column changes -------------------------------
    with op.batch_alter_table("comments") as b:
        # NOT NULL again. Existing NULL bodies get coerced to "" so the
        # constraint passes.
        bind.execute(sa.text(
            "UPDATE comments SET body = '' WHERE body IS NULL"
        ))
        b.alter_column("body", existing_type=sa.Text(), nullable=False)
        b.drop_column("attachments")
