"""Doc 24 part 2: subtask_id parent for nested subtasks.

Adds ``subtasks.parent_subtask_id`` (nullable self-FK) so subtasks can
nest under other subtasks. ``subtasks.task_id`` keeps pointing at the
root task — the column is **not** renamed; nested subtasks share the
root task id with their top-level ancestors so "all subtasks under task
X" stays a one-column-filter query.

Position uniqueness reshape:
  - Drops the existing ``uq_subtasks_task_position_live`` (which was
    ``(task_id, position) WHERE deleted_at IS NULL``). After this
    migration nested subtasks under different parents share the same
    root task and could legitimately collide on position, so the index
    has to be split.
  - Adds ``uq_subtasks_task_position_top_live`` —
    ``(task_id, position) WHERE deleted_at IS NULL AND
    parent_subtask_id IS NULL``. Top-level siblings only.
  - Adds ``uq_subtasks_subtask_position_live`` —
    ``(parent_subtask_id, position) WHERE deleted_at IS NULL AND
    parent_subtask_id IS NOT NULL``. Children of one subtask only.

No data migration: every existing row stays top-level
(``parent_subtask_id = NULL``). Labels resolve identically to before.

Revision ID: e9f1a2b3c4d5
Revises: d8e1f3a4b502
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa


revision = "e9f1a2b3c4d5"
down_revision = "d8e1f3a4b502"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("subtasks") as batch:
        batch.add_column(
            sa.Column(
                "parent_subtask_id",
                sa.String(length=36),
                sa.ForeignKey(
                    "subtasks.id",
                    name="fk_subtasks_parent_subtask_id",
                    use_alter=True,
                ),
                nullable=True,
            )
        )
    op.create_index(
        "ix_subtasks_parent_subtask_id",
        "subtasks",
        ["parent_subtask_id"],
    )
    # Drop the old single position-uniqueness index; replaced by the two
    # partial-unique indexes below.
    try:
        op.drop_index("uq_subtasks_task_position_live", table_name="subtasks")
    except Exception:
        # Index may not exist on environments where it was never created
        # (fresh dev DB). Safe to ignore — the new indexes are added below.
        pass
    op.create_index(
        "uq_subtasks_task_position_top_live",
        "subtasks",
        ["task_id", "position"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND parent_subtask_id IS NULL"
        ),
        sqlite_where=sa.text(
            "deleted_at IS NULL AND parent_subtask_id IS NULL"
        ),
    )
    op.create_index(
        "uq_subtasks_subtask_position_live",
        "subtasks",
        ["parent_subtask_id", "position"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND parent_subtask_id IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "deleted_at IS NULL AND parent_subtask_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_subtasks_subtask_position_live", table_name="subtasks"
    )
    op.drop_index(
        "uq_subtasks_task_position_top_live", table_name="subtasks"
    )
    op.create_index(
        "uq_subtasks_task_position_live",
        "subtasks",
        ["task_id", "position"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(
        "ix_subtasks_parent_subtask_id", table_name="subtasks"
    )
    with op.batch_alter_table("subtasks") as batch:
        batch.drop_column("parent_subtask_id")
