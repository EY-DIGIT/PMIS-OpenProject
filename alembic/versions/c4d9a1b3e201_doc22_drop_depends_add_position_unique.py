"""doc 22: drop milestones.depends + add per-parent live-position unique indexes

Revision ID: c4d9a1b3e201
Revises: b2c3d4e5f6a7
Create Date: 2026-05-02

Drops the legacy ``milestones.depends`` JSON column (replaced by the
``milestone_dependencies`` edge table in doc 21A), and locks down the
display-label rank source by adding a partial-unique index on
``(parent_id, position) WHERE deleted_at IS NULL`` for milestones,
activities, tasks, and subtasks.

Why the unique indexes
----------------------
Display labels (M1, A1.2, T1.2.3, S1.2.3.4) are computed from each
entity's rank in ``ORDER BY position ASC, id ASC`` among its live
siblings. If two siblings shared the same position the rank would be
ambiguous (two activities could both resolve to ``A1.2``). The
``next_position`` allocation in services already prevents duplicates in
practice; the index makes that invariant a constraint.

Self-healing data step
----------------------
Some deployments arrived at this migration with pre-existing duplicate
``(parent_id, position)`` live rows — legacy bug, manual import, or a
race in older position-allocation code. Adding the unique index would
fail on such data with ``UniqueViolation``. Before each index is
created, this migration runs ``heal_duplicate_positions`` (in
``app.shared.position_heal``), which keeps the row with the smallest
``id`` at its current position and renumbers every additional row to
the next free slot for that parent. The heal is idempotent — runs
zero updates on clean data, so dev / test DBs see no churn.

The heal happens BEFORE the index is created, inside the same
transaction, so a failure anywhere rolls back the heal too.

IDEMPOTENT — every drop/index step is wrapped in an inspector check so
re-running against an already-migrated DB is a no-op.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.shared.position_heal import heal_duplicate_positions


revision: str = "c4d9a1b3e201"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
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
    dialect = bind.dialect.name

    # ---- 1. Drop milestones.depends -----------------------------------
    if _has_column(inspector, "milestones", "depends"):
        with op.batch_alter_table("milestones") as batch_op:
            batch_op.drop_column("depends")

    # ---- 2. Partial unique indexes for live position --------------------
    # Index name → (table, parent_col)
    indexes = (
        ("uq_milestones_project_position_live",  "milestones",  "project_id"),
        ("uq_activities_milestone_position_live", "activities", "milestone_id"),
        ("uq_tasks_activity_position_live",      "tasks",       "activity_id"),
        ("uq_subtasks_task_position_live",       "subtasks",    "task_id"),
    )

    for ix_name, table, parent_col in indexes:
        if _has_index(inspector, table, ix_name):
            continue

        # Self-heal pre-existing duplicate (parent, position) live rows
        # before adding the unique index. No-op on clean data; rescues
        # legacy deployments where past races / manual imports left
        # duplicates behind. Same transaction, so any later failure
        # rolls the heal back too.
        healed = heal_duplicate_positions(bind, table, parent_col)
        if healed:
            print(
                f"  doc 22 migration: re-numbered {healed} duplicate-position "
                f"row(s) in `{table}` to satisfy {ix_name}."
            )

        if dialect == "postgresql":
            op.create_index(
                ix_name, table, [parent_col, "position"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
            )
        elif dialect == "sqlite":
            # SQLite supports partial indexes via raw SQL.
            op.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {ix_name} "
                f"ON {table} ({parent_col}, position) "
                f"WHERE deleted_at IS NULL"
            )
        else:
            # Other backends: best-effort plain-unique index. Coordinate with
            # ops if a non-postgres / non-sqlite DB is ever in scope.
            op.create_index(
                ix_name, table, [parent_col, "position"], unique=True,
            )


def downgrade() -> None:
    """Reverse only the additive part (indexes). Re-creating the dropped
    JSON column would risk reintroducing dead-write behavior, so we
    intentionally leave it dropped on downgrade.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for ix_name, table, _ in (
        ("uq_milestones_project_position_live",  "milestones",  None),
        ("uq_activities_milestone_position_live", "activities", None),
        ("uq_tasks_activity_position_live",      "tasks",       None),
        ("uq_subtasks_task_position_live",       "subtasks",    None),
    ):
        if _has_index(inspector, table, ix_name):
            op.drop_index(ix_name, table_name=table)
