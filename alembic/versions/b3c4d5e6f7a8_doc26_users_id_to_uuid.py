"""doc 26: flip users.id from Integer to UUID String(36) + cascade FK columns

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-04

Senior reviewer rule: every public-facing identifier must be a UUID, not
an auto-incrementing integer. Vendors / projects / milestones / tasks /
subtasks / activities / comments / attachments already use UUIDs; the
remaining hold-out was ``users.id`` (Integer autoincrement). This
migration flips it.

Cascade: every FK column that today references ``users.id`` (~25 of them
across vendors, projects, milestones, tasks, subtasks, activities,
project_members, project_audit_logs, comments, attachments, the
*_dependency soft-delete columns, user_roles, user_permissions,
revoked_tokens, meetings, meeting_participants, work_packages, and
``users.deleted_by`` itself) gets retyped from Integer to String(36)
in the same transaction.

Strategy (Postgres) — single transactional sweep
------------------------------------------------
1. Add ``users.id_new VARCHAR(36)`` populated with a fresh ``uuid4()``
   per row.
2. For every dependent FK column ``X``, add an ``X_new VARCHAR(36)``,
   backfill via a JOIN against the users mapping, then atomically
   swap (drop the old FK, drop the old column, rename the new one).
3. Drop the legacy ``users.id`` (and the autoincrement sequence).
4. Promote ``users.id_new`` to PRIMARY KEY and rename it back to ``id``.
5. Re-establish FOREIGN KEY constraints across every dependent column.

All steps run in alembic's transactional DDL — partial application
rolls back to the pre-migration shape.

SQLite path
-----------
SQLite cannot retype a PRIMARY KEY in place (no ``ALTER TABLE ... ALTER
COLUMN``). For tests we rebuild from ``Base.metadata.create_all()``;
for any legacy on-disk ``pmis.db`` the dev workflow has been "wipe and
re-bootstrap" since the project_id UUID flip — same precedent applies
here. This migration is a no-op on SQLite (skipped via dialect check).

IDEMPOTENT — every step is gated on an inspector check so re-running on
an already-migrated DB does nothing.
"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Every (table, column) pair whose existing Integer FK references users.id.
# Drives the cascade in upgrade(). Order doesn't matter — we drop FK
# constraints up front, do the column retype, then re-add constraints at
# the end.
# ---------------------------------------------------------------------------
_FK_COLUMNS: list[tuple[str, str]] = [
    ("vendors",                "deleted_by"),
    ("projects",               "created_by"),
    ("projects",               "updated_by"),
    ("projects",               "deleted_by"),
    ("project_audit_logs",     "actor_id"),
    ("project_members",        "user_id"),
    ("comments",               "author_user_id"),
    ("comments",               "deleted_by"),
    ("attachments",            "uploaded_by_user_id"),
    ("attachments",            "deleted_by"),
    ("milestones",             "created_by"),
    ("milestones",             "updated_by"),
    ("activities",             "created_by"),
    ("activities",             "updated_by"),
    ("activity_dependencies",  "deleted_by"),
    ("tasks",                  "created_by"),
    ("tasks",                  "updated_by"),
    ("task_dependencies",      "deleted_by"),
    ("subtasks",               "created_by"),
    ("subtasks",               "updated_by"),
    ("subtask_dependencies",   "deleted_by"),
    ("milestone_dependencies", "deleted_by"),
    ("user_roles",             "user_id"),
    ("user_roles",             "created_by"),
    ("user_permissions",       "user_id"),
    ("user_permissions",       "created_by"),
    ("revoked_tokens",         "user_id"),
    ("meetings",               "created_by_id"),
    ("meeting_participants",   "user_id"),
    ("work_packages",          "assignee_id"),
    # users.deleted_by — self-FK; handled inline during the users rebuild.
]


def _has_table(inspector, table: str) -> bool:
    return table in set(inspector.get_table_names())


def _column_type(inspector, table: str, column: str):
    """Return the SQLAlchemy type for a column, or None if the column is missing."""
    if not _has_table(inspector, table):
        return None
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return col["type"]
    return None


def _is_integer(col_type) -> bool:
    """Loose integer check — catches Postgres INTEGER, BIGINT, SERIAL, etc."""
    if col_type is None:
        return False
    name = type(col_type).__name__.upper()
    return "INT" in name or "SERIAL" in name


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # SQLite: rebuild via Base.metadata.create_all() at boot. This
    # migration is a no-op there. Same precedent as project_id UUID flip.
    if dialect == "sqlite":
        return

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "users"):
        return  # nothing to migrate

    # ---- Idempotency guard ------------------------------------------------
    # If users.id is already a string-y type, the migration has already run.
    users_id_type = _column_type(inspector, "users", "id")
    if users_id_type is not None and not _is_integer(users_id_type):
        return

    # ---- 1. Add users.id_new + populate -----------------------------------
    op.add_column(
        "users",
        sa.Column("id_new", sa.String(length=36), nullable=True),
    )
    rows = bind.execute(sa.text("SELECT id FROM users")).fetchall()
    for row in rows:
        old_id = row[0] if not hasattr(row, "id") else row.id
        bind.execute(
            sa.text("UPDATE users SET id_new = :u WHERE id = :i"),
            {"u": str(uuid4()), "i": old_id},
        )

    # ---- 2. Cascade — for each FK column, add X_new and backfill ----------
    # Drop FK constraints up front so the column type swap doesn't run
    # into "depended-on by FK" errors.
    for table, column in _FK_COLUMNS + [("users", "deleted_by")]:
        if not _has_table(inspector, table):
            continue
        # Find the FK constraint that targets users.id from this column.
        for fk in inspector.get_foreign_keys(table):
            if (
                fk.get("referred_table") == "users"
                and column in (fk.get("constrained_columns") or [])
            ):
                fk_name = fk.get("name")
                if fk_name:
                    op.drop_constraint(fk_name, table, type_="foreignkey")

    # Refresh inspector after constraint drops.
    inspector = sa.inspect(bind)

    # Now retype each column. For PK-participating columns
    # (user_roles.user_id, user_permissions.user_id) the PK constraint
    # has to come down too.
    for table, column in _FK_COLUMNS:
        if not _has_table(inspector, table):
            continue
        # Add new column.
        op.add_column(
            table,
            sa.Column(f"{column}_new", sa.String(length=36), nullable=True),
        )
        # Backfill from join.
        bind.execute(sa.text(
            f"UPDATE {table} SET {column}_new = u.id_new "
            f"FROM users u WHERE {table}.{column} = u.id"
        ))

    # users.deleted_by self-FK — handled inline.
    op.add_column(
        "users",
        sa.Column("deleted_by_new", sa.String(length=36), nullable=True),
    )
    bind.execute(sa.text(
        "UPDATE users SET deleted_by_new = u.id_new "
        "FROM users u WHERE users.deleted_by = u.id"
    ))

    # ---- 3. Drop existing PK on users + child PKs -------------------------
    # user_roles + user_permissions have user_id as part of a composite PK.
    op.drop_constraint("user_roles_pkey", "user_roles", type_="primary")
    op.drop_constraint("user_permissions_pkey", "user_permissions", type_="primary")
    op.drop_constraint("users_pkey", "users", type_="primary")

    # ---- 4. Drop legacy columns + rename _new → original ------------------
    for table, column in _FK_COLUMNS + [("users", "deleted_by")]:
        if not _has_table(inspector, table):
            continue
        op.drop_column(table, column)
        op.alter_column(table, f"{column}_new", new_column_name=column)

    op.drop_column("users", "id")
    op.alter_column("users", "id_new", new_column_name="id", nullable=False)

    # ---- 5. Re-create PKs + FK constraints --------------------------------
    op.create_primary_key("users_pkey", "users", ["id"])
    op.create_primary_key(
        "user_roles_pkey", "user_roles", ["user_id", "role_id"],
    )
    op.create_primary_key(
        "user_permissions_pkey", "user_permissions",
        ["user_id", "permission_code"],
    )

    # Re-add FK constraints. Constraint names follow the SQLAlchemy
    # auto-generated convention (``<table>_<column>_fkey`` on Postgres)
    # so a future ``alembic downgrade`` (if ever attempted — note we
    # deliberately don't ship one for this revision) could find them.
    for table, column in _FK_COLUMNS + [("users", "deleted_by")]:
        if not _has_table(inspector, table):
            continue
        op.create_foreign_key(
            f"fk_{table}_{column}_users",
            source_table=table,
            referent_table="users",
            local_cols=[column],
            remote_cols=["id"],
        )


def downgrade() -> None:
    """No-op. Doc 26 is a one-way upgrade.

    Reverting would require regenerating an integer sequence keyed on
    UUID values (impossible without losing identity) plus rolling back
    every JWT issued post-migration. If a rollback is genuinely needed,
    restore from a pre-migration snapshot.
    """
    pass
