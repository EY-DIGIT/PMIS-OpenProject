"""doc 25: add users.user_code + backfill existing rows

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-04

Adds the human-readable identifier column ``user_code`` to ``users``
(see ``app/shared/code_generators.py`` for format spec). Backfills every
existing row deterministically using ``(login, created_at)``.

Three steps in one transaction
------------------------------
1. ``ALTER TABLE users ADD COLUMN user_code VARCHAR(50)``  (nullable)
2. For each existing user: compute ``US-{slug}-{ist_ts}`` from
   ``login`` + ``created_at``, append ``-N`` suffix on collision, write it.
3. ``CREATE UNIQUE INDEX uq_users_user_code`` (the DB-level guard).

If anything in step 2 raises (e.g. the helper is missing on this
deployment for some reason), the whole migration rolls back — alembic's
transactional DDL ensures the column add is reverted too. So we never
end up with a column added but unbackfilled.

IDEMPOTENT — every step is wrapped in an inspector check, so re-running
on an already-migrated DB is a no-op (matches the pattern of every other
migration in this chain).

Mirror of ``f1a2b3c4d5e6_doc25_add_vendor_code.py`` (the vendor side of
the same feature). Both code columns share the same generator helper so
the format stays identical across entities.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.shared.code_generators import build_code, generate_unique_code


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
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

    if "users" not in set(inspector.get_table_names()):
        # Fresh DB without the users table — nothing to do. Real
        # bootstrap migrations create the table separately.
        return

    # ---- 1. Add column (nullable for now — backfill needs to write to it).
    if not _has_column(inspector, "users", "user_code"):
        op.add_column(
            "users",
            sa.Column("user_code", sa.String(length=50), nullable=True),
        )

    # ---- 2. Backfill — only rows where user_code IS NULL. Idempotent
    # if the migration is re-run after a previous partial completion.
    #
    # Slug source is the user's full name (first + last) so the 4-char
    # slug is recognisable to humans (US-RAVI-..., US-PRIY-...). Falls
    # back to ``login`` (employee id) when neither name is populated —
    # legacy bootstrap admin rows lack a name.
    rows = bind.execute(sa.text(
        "SELECT id, login, first_name, last_name, created_at FROM users "
        "WHERE user_code IS NULL"
    )).fetchall()
    backfilled = 0
    for row in rows:
        # Row could be a tuple or a Row mapping depending on dialect/version.
        uid = row[0] if not hasattr(row, "id") else row.id
        ulogin = row[1] if not hasattr(row, "login") else row.login
        ufirst = row[2] if not hasattr(row, "first_name") else row.first_name
        ulast = row[3] if not hasattr(row, "last_name") else row.last_name
        ucreated = row[4] if not hasattr(row, "created_at") else row.created_at
        name_source = " ".join(
            part for part in (ufirst, ulast) if part and str(part).strip()
        ).strip()
        slug_source = name_source or (ulogin or "")
        base = build_code("US", slug_source, ucreated)
        code = generate_unique_code(
            bind, table="users", code_column="user_code",
            base_code=base, exclude_id=uid,
        )
        bind.execute(
            sa.text("UPDATE users SET user_code = :c WHERE id = :i"),
            {"c": code, "i": uid},
        )
        backfilled += 1
    if backfilled:
        print(f"  doc 25 migration: backfilled user_code for {backfilled} user(s).")

    # ---- 3. UNIQUE index — guarantees future inserts can't collide.
    if not _has_index(inspector, "users", "uq_users_user_code"):
        op.create_index(
            "uq_users_user_code", "users", ["user_code"],
            unique=True,
        )


def downgrade() -> None:
    """Remove the unique index + column. Backfilled data is lost.

    Safe because ``user_code`` doesn't appear in any FK or join — the
    integer ``id`` remains the canonical identifier downstream of the
    domain layer.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_index(inspector, "users", "uq_users_user_code"):
        op.drop_index("uq_users_user_code", table_name="users")
    if _has_column(inspector, "users", "user_code"):
        with op.batch_alter_table("users") as batch:
            batch.drop_column("user_code")
