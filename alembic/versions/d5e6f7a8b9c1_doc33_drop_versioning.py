"""Doc 33: drop versioning columns + suspended status + add audit actor_role.

Revision ID: d5e6f7a8b9c1
Revises: b3c4d5e6f7a8
Create Date: 2026-05-05 20:00:00

Doc 33 dropped the entire versioning feature plus the ``suspended``
status. This migration:

  - DELETEs every version row (``projects.is_version=true``) and any
    project still in status ``suspended``. Per the doc 33 decision
    (Q1.1), version data is not preserved.
  - Drops the partial unique index ``ux_projects_active_version_per_baseline``.
  - Drops the columns ``projects.is_version``, ``projects.version_of``,
    ``projects.baseline_id``, ``projects.version_no``,
    ``milestones.cloned_from_id``, ``activities.cloned_from_id``,
    ``project_status_transitions.version_only``.
  - Drops index ``idx_projects_is_version``, ``idx_projects_version_of``,
    ``idx_projects_baseline_id``, ``ix_milestones_cloned_from_id``,
    ``ix_activities_cloned_from_id``.
  - Removes any ``project_status_transitions`` row mentioning
    ``suspended``.
  - Adds ``project_audit_logs.actor_role`` (nullable) for the audit
    expansion (records the role bucket the actor occupied at the time
    of the change).
  - Adds index ``idx_project_audit_logs_action`` on
    ``project_audit_logs.action`` for the expanded audit query path.

Down-revision is purely structural — the deleted version rows cannot
be recreated.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c1"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Wipe version rows + suspended rows BEFORE dropping the columns
    #    that filter for them.
    op.execute("DELETE FROM projects WHERE is_version = true OR status = 'suspended'")
    op.execute("DELETE FROM project_status_transitions WHERE from_status = 'suspended' OR to_status = 'suspended'")

    # 2. Drop indexes that reference soon-to-be-dropped columns.
    for ix in (
        "ux_projects_active_version_per_baseline",
        "idx_projects_is_version",
        "idx_projects_version_of",
        "idx_projects_baseline_id",
        "ix_milestones_cloned_from_id",
        "ix_activities_cloned_from_id",
    ):
        try:
            op.drop_index(ix, table_name=None)
        except Exception:
            # Index may not exist on legacy schemas. Best-effort drop.
            pass

    # 3. Drop the columns themselves.
    with op.batch_alter_table("projects") as b:
        for col in ("is_version", "version_of", "baseline_id", "version_no"):
            try:
                b.drop_column(col)
            except Exception:
                pass

    with op.batch_alter_table("milestones") as b:
        try:
            b.drop_column("cloned_from_id")
        except Exception:
            pass

    with op.batch_alter_table("activities") as b:
        try:
            b.drop_column("cloned_from_id")
        except Exception:
            pass

    with op.batch_alter_table("project_status_transitions") as b:
        try:
            b.drop_column("version_only")
        except Exception:
            pass

    # 4. Audit-expansion column + index.
    with op.batch_alter_table("project_audit_logs") as b:
        b.add_column(sa.Column("actor_role", sa.String(length=50), nullable=True))
    op.create_index(
        "idx_project_audit_logs_action", "project_audit_logs", ["action"],
    )
    op.create_index(
        "idx_project_audit_logs_actor_role", "project_audit_logs", ["actor_role"],
    )


def downgrade() -> None:
    """Re-add the dropped columns + index. Note: deleted version rows are
    NOT restored (intentional per doc 33 Q1.1)."""
    op.drop_index("idx_project_audit_logs_actor_role", table_name="project_audit_logs")
    op.drop_index("idx_project_audit_logs_action", table_name="project_audit_logs")
    with op.batch_alter_table("project_audit_logs") as b:
        b.drop_column("actor_role")

    with op.batch_alter_table("project_status_transitions") as b:
        b.add_column(
            sa.Column("version_only", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("activities") as b:
        b.add_column(sa.Column("cloned_from_id", sa.String(length=36), nullable=True))

    with op.batch_alter_table("milestones") as b:
        b.add_column(sa.Column("cloned_from_id", sa.String(length=36), nullable=True))

    with op.batch_alter_table("projects") as b:
        b.add_column(sa.Column("is_version", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("version_of", sa.String(length=36), nullable=True))
        b.add_column(sa.Column("baseline_id", sa.String(length=36), nullable=True))
        b.add_column(sa.Column("version_no", sa.Integer(), nullable=True))
