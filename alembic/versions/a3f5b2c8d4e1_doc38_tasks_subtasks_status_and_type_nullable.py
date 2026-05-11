"""doc 38 follow-up — tasks/subtasks: drop NOT NULL on type, add status column

Revision ID: a3f5b2c8d4e1
Revises: f1e8d6a4b9c2
Create Date: 2026-05-07

Doc 38 spec:
- Task/subtask CREATE is trimmed to name + description + dates only.
  ``type`` is no longer required (parent inheritance falls back to NULL
  when the parent activity itself was created without a type).
- Task/subtask EDIT (PATCH) accepts status in addition to actualStartDate,
  actualEndDate, dependsOn, and comments/attachments.

This migration:
- Drops the NOT NULL constraint on tasks.type + subtasks.type (matches
  the activities.type fix in f1e8d6a4b9c2).
- Adds a nullable ``status`` column to both tables, with an index.
- Relaxes ``ck_tasks_type`` / ``ck_subtasks_type`` to allow NULL.

Idempotent — checks current state before altering.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f5b2c8d4e1"
down_revision: Union[str, Sequence[str], None] = "f1e8d6a4b9c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(inspector, table_name: str):
    if table_name not in set(inspector.get_table_names()):
        return {}
    return {c["name"]: c for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    for table in ("tasks", "subtasks"):
        cols = _existing_columns(inspector, table)
        if not cols:
            continue

        # 1. Drop NOT NULL on type.
        if "type" in cols and not cols["type"].get("nullable"):
            if dialect == "postgresql":
                op.execute(f"ALTER TABLE {table} ALTER COLUMN type DROP NOT NULL")
            else:
                try:
                    with op.batch_alter_table(table) as batch:
                        batch.alter_column("type", nullable=True)
                except Exception:
                    pass

        # 2. Add status column if missing.
        if "status" not in cols:
            op.add_column(
                table,
                sa.Column("status", sa.String(length=32), nullable=True),
            )
            try:
                op.create_index(
                    f"idx_{table}_status", table, ["status"], unique=False,
                )
            except Exception:
                pass

        # 3. Relax the type CHECK so NULL is allowed.
        if dialect == "postgresql":
            op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS ck_{table}_type")
            op.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_type "
                f"CHECK (type IS NULL OR type IN ('standard', 'resource', 'transactional'))"
            )


def downgrade() -> None:
    """Intentional no-op (additive migration; matches project convention)."""
    pass
