"""Unify project membership into user_role_assignments and drop project_members

The legacy ``project_members`` table predates the doc-41 scoped-RBAC
``user_role_assignments`` (URA) table. Both stored "user U is on project
P" but URA does it as part of a unified scoped-RBAC model that also
covers global and org-level role assignments.

``project_members.roles`` was always written as ``[]`` in every call
site (verified via codebase audit) — the JSON column was a placeholder
that never got populated. So each legacy row maps cleanly to ONE URA
row with ``role = project_member``, ``project_id = <pm.project_id>``,
``organization_id = NULL``.

This migration:

  1. Backfills URA rows from any existing ``project_members`` rows
     that don't already have an equivalent URA row. The backfill is
     idempotent — re-running is a no-op.
  2. Drops the ``project_members`` table.

All writers and readers have been switched to URA in the same change
set, so the table is safe to drop. The ``GET /projects/{id}/members``
URL surface is preserved and now reads from URA.

Revision ID: baddc1146b85
Revises: f9b8dd81f7dd
Create Date: 2026-05-13 09:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "baddc1146b85"
down_revision: Union[str, Sequence[str], None] = "f9b8dd81f7dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill URA rows from project_members, then drop project_members."""
    # Backfill: for each project_members row, write a URA row with role
    # = project_member. Skip rows that would conflict with the URA
    # UNIQUE constraint (user_id, role_id, organization_id, project_id).
    #
    # NOTE: organization_id is NULL on every backfilled row; URA's
    # ck_ura_single_scope check constraint requires at most one of
    # (organization_id, project_id) to be non-null, which holds here.
    op.execute(
        """
        INSERT INTO user_role_assignments
            (user_id, role_id, organization_id, project_id, created_at)
        SELECT
            pm.user_id,
            r.id AS role_id,
            NULL AS organization_id,
            pm.project_id,
            pm.created_at
        FROM project_members pm
        CROSS JOIN roles r
        WHERE r.name = 'project_member'
        AND NOT EXISTS (
            SELECT 1 FROM user_role_assignments ura
            WHERE ura.user_id = pm.user_id
            AND ura.role_id  = r.id
            AND ura.organization_id IS NULL
            AND ura.project_id = pm.project_id
        )
        """
    )

    # Drop indexes first to play nicely with strict DBs that don't
    # auto-cascade index drops on table drop.
    with op.batch_alter_table("project_members") as batch:
        for ix in (
            "idx_project_members_project_id",
            "idx_project_members_user_id",
            "idx_project_members_created_at",
        ):
            try:
                batch.drop_index(ix)
            except Exception:  # noqa: BLE001
                pass  # idempotent — index may not exist in some envs

    op.drop_table("project_members")


def downgrade() -> None:
    """Recreate project_members and best-effort restore rows from URA.

    Note: the downgrade restores only the project-scoped URA rows that
    hold the ``project_member`` role. Rows added via the new RBAC paths
    with other roles (project_admin / division_member) are NOT
    represented in the legacy table by design — they were never there
    pre-migration either."""
    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.String(length=36),
                  sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )
    op.create_index(
        "idx_project_members_project_id", "project_members", ["project_id"],
    )
    op.create_index(
        "idx_project_members_user_id", "project_members", ["user_id"],
    )
    op.create_index(
        "idx_project_members_created_at", "project_members", ["created_at"],
    )

    op.execute(
        """
        INSERT INTO project_members
            (project_id, user_id, roles, created_at, updated_at)
        SELECT
            ura.project_id,
            ura.user_id,
            '[]'::jsonb AS roles,
            ura.created_at,
            ura.created_at AS updated_at
        FROM user_role_assignments ura
        JOIN roles r ON r.id = ura.role_id
        WHERE ura.project_id IS NOT NULL
        AND r.name = 'project_member'
        """
    )
