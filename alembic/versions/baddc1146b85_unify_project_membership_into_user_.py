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
Revises: d4f9b2e8a317
Create Date: 2026-05-13 09:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "baddc1146b85"
# Re-parented from f9b8dd81f7dd to d4f9b2e8a317 to collapse a parallel
# branch I'd accidentally created — f9b8dd81f7dd was a branch point
# (eb3b19c7487c was already chained off it as the actual main-line
# head's ancestor). Chaining off d4f9b2e8a317 (the real head) makes
# this migration the single new head and lets ``alembic upgrade head``
# succeed without a "Multiple head revisions" error.
down_revision: Union[str, Sequence[str], None] = "d4f9b2e8a317"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill URA rows from project_members, then drop project_members.

    Pre-flight guards run before any destructive operation:

      1. The ``project_member`` role row must exist. If it doesn't, we
         abort — without that row the backfill silently writes zero
         rows and the DROP would destroy the legacy data.

      2. Every project_members row's ``user_id`` / ``project_id`` must
         reference a live row. Stale FKs (orphaned rows pointing at
         hard-deleted users/projects) would fail URA's FK constraints
         mid-insert, leaving the migration half-applied. We report a
         summary and skip them at SELECT time so the rest of the data
         migrates cleanly.
    """
    bind = op.get_bind()

    # Guard 1: project_member role must exist.
    role_id_row = bind.execute(sa.text(
        "SELECT id FROM roles WHERE name = 'project_member'"
    )).fetchone()
    if role_id_row is None:
        raise RuntimeError(
            "Migration aborted: the 'project_member' role is not seeded. "
            "Apply this migration AFTER the app has booted at least once "
            "(or after running RbacRepository.sync_builtin_permissions). "
            "Without that role row the legacy project_members data would "
            "be silently destroyed by the DROP TABLE step."
        )

    # Guard 2: surface stale FKs before we touch anything. These rows
    # have user_id / project_id pointing at hard-deleted (no row at all)
    # users or projects and would violate URA's FKs on insert.
    stale = bind.execute(sa.text(
        """
        SELECT COUNT(*) FROM project_members pm
        WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = pm.user_id)
           OR NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = pm.project_id)
        """
    )).scalar()
    if stale and stale > 0:
        # Print to stdout — alembic surfaces this in the deploy log. Skip
        # them in the backfill below (via the EXISTS filter); they would
        # otherwise crash mid-insert.
        print(
            f"[doc-54b migration] WARNING: {stale} project_members row(s) "
            f"reference hard-deleted users or projects; these will not be "
            f"backfilled into user_role_assignments and will be lost when "
            f"project_members is dropped."
        )

    # Backfill: only rows whose FK targets exist on both sides. The
    # NOT EXISTS guard on URA prevents duplicates if a URA row already
    # covers the same (user, project_member, project) tuple.
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
        AND EXISTS (SELECT 1 FROM users u WHERE u.id = pm.user_id)
        AND EXISTS (SELECT 1 FROM projects p WHERE p.id = pm.project_id)
        AND NOT EXISTS (
            SELECT 1 FROM user_role_assignments ura
            WHERE ura.user_id = pm.user_id
            AND ura.role_id  = r.id
            AND ura.organization_id IS NULL
            AND ura.project_id = pm.project_id
        )
        """
    )

    # DROP TABLE cascades to attached indexes on both Postgres and
    # SQLite, so no explicit DROP INDEX is needed.
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
