"""doc 41 follow-up — priority column on milestones / tasks / subtasks

Revision ID: b5e7f2a8c9d3
Revises: d0c41a55145d
Create Date: 2026-05-08

Activity already has ``priority`` (doc 41 — see e3f5b7a8c1d4). This
migration extends the same idiom to milestones, tasks, and subtasks so
each level carries its own independent priority. No parent-child
constraint — milestone priority does NOT derive from / constrain
activity priority, etc. They are fully decoupled per level (matching
the FE picker UX).

For each table the migration:
  1. Adds a nullable ``priority`` String(16) column (no DB-side default;
     wire validation enforces required-on-create).
  2. Creates a single-column index ``idx_<table>_priority`` to keep the
     pattern consistent with ``idx_activities_priority``.
  3. Backfills every existing row to ``'p3'`` (the low / default code).

The priorities catalog itself was already created by e3f5b7a8c1d4 with
the seed rows ``p1`` / ``p2`` / ``p3`` — no catalog changes here.

Idempotent — checks current state before each step so re-running on a
partially-applied DB is safe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5e7f2a8c9d3"
down_revision: Union[str, Sequence[str], None] = "d0c41a55145d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(inspector, table_name: str):
    if table_name not in set(inspector.get_table_names()):
        return {}
    return {c["name"]: c for c in inspector.get_columns(table_name)}


def _existing_indexes(inspector, table_name: str):
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {i["name"] for i in inspector.get_indexes(table_name)}


def _add_priority(inspector, bind, table: str) -> None:
    """Add ``priority`` to ``table``, index it, and backfill to 'p3'.

    Each step is guarded so re-running on a partially-applied DB is a
    no-op for the already-applied bits.
    """
    cols = _existing_columns(inspector, table)
    if not cols:
        return  # table missing entirely — nothing to do
    if "priority" not in cols:
        op.add_column(
            table,
            sa.Column("priority", sa.String(length=16), nullable=True),
        )

    idxs = _existing_indexes(inspector, table)
    idx_name = f"idx_{table}_priority"
    if idx_name not in idxs:
        op.create_index(idx_name, table, ["priority"])

    # Backfill: every existing row gets the default 'p3'.
    bind.execute(
        sa.text(
            f"UPDATE {table} SET priority = 'p3' WHERE priority IS NULL"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in ("milestones", "tasks", "subtasks"):
        _add_priority(inspector, bind, table)


def downgrade() -> None:
    """Intentional no-op — keep the new columns for safety, mirroring
    the activity-priority migration's downgrade choice."""
    pass
