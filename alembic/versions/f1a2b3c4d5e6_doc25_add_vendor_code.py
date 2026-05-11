"""doc 25: add vendors.vendor_code + backfill existing rows

Revision ID: f1a2b3c4d5e6
Revises: e9f1a2b3c4d5
Create Date: 2026-05-04

Adds the human-readable identifier column ``vendor_code`` to ``vendors``
(see ``app/shared/code_generators.py`` for format spec). Backfills every
existing row deterministically using ``(name, created_at)``.

Three steps in one transaction
------------------------------
1. ``ALTER TABLE vendors ADD COLUMN vendor_code VARCHAR(50)``  (nullable)
2. For each existing vendor: compute ``VN-{slug}-{ist_ts}`` from
   ``name`` + ``created_at``, append ``-N`` suffix on collision, write it.
3. ``CREATE UNIQUE INDEX uq_vendors_vendor_code`` (the DB-level guard).

If anything in step 2 raises (e.g. the helper is missing on this
deployment for some reason), the whole migration rolls back — alembic's
transactional DDL ensures the column add is reverted too. So we never
end up with a column added but unbackfilled.

IDEMPOTENT — every step is wrapped in an inspector check, so re-running
on an already-migrated DB is a no-op (matches the pattern of every other
migration in this chain).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.shared.code_generators import build_code, generate_unique_code


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e9f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in set(inspector.get_table_names()):
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_index(inspector, table: str, index_name: str) -> bool:
    if table not in set(inspector.get_table_names()):
        return False
    return index_name in {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "vendors" not in set(inspector.get_table_names()):
        # Fresh DB without the vendors table — nothing to do. Real
        # bootstrap migrations create the table separately.
        return

    # ---- 1. Add column (nullable for now — backfill needs to write to it).
    if not _has_column(inspector, "vendors", "vendor_code"):
        op.add_column(
            "vendors",
            sa.Column("vendor_code", sa.String(length=50), nullable=True),
        )

    # ---- 2. Backfill — only rows where vendor_code IS NULL. Idempotent
    # if the migration is re-run after a previous partial completion.
    rows = bind.execute(sa.text(
        "SELECT id, name, created_at FROM vendors "
        "WHERE vendor_code IS NULL"
    )).fetchall()
    backfilled = 0
    for row in rows:
        # Row could be a tuple or a Row mapping depending on dialect/version.
        vid = row[0] if not hasattr(row, "id") else row.id
        vname = row[1] if not hasattr(row, "name") else row.name
        vcreated = row[2] if not hasattr(row, "created_at") else row.created_at
        base = build_code("VN", vname or "", vcreated)
        code = generate_unique_code(
            bind, table="vendors", code_column="vendor_code",
            base_code=base, exclude_id=vid,
        )
        bind.execute(
            sa.text("UPDATE vendors SET vendor_code = :c WHERE id = :i"),
            {"c": code, "i": vid},
        )
        backfilled += 1
    if backfilled:
        print(f"  doc 25 migration: backfilled vendor_code for {backfilled} vendor(s).")

    # ---- 3. UNIQUE index — guarantees future inserts can't collide.
    if not _has_index(inspector, "vendors", "uq_vendors_vendor_code"):
        op.create_index(
            "uq_vendors_vendor_code", "vendors", ["vendor_code"],
            unique=True,
        )


def downgrade() -> None:
    """Remove the unique index + column. Backfilled data is lost.

    Safe because ``vendor_code`` doesn't appear in any FK or join — the
    UUID ``id`` remains the canonical identifier downstream of the
    domain layer.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_index(inspector, "vendors", "uq_vendors_vendor_code"):
        op.drop_index("uq_vendors_vendor_code", table_name="vendors")
    if _has_column(inspector, "vendors", "vendor_code"):
        with op.batch_alter_table("vendors") as batch:
            batch.drop_column("vendor_code")
