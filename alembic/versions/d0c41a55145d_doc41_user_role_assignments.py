"""Doc 41 — scoped role assignments table.

Revision ID: d0c41a55145d
Revises: e3f5b7a8c1d4
Create Date: 2026-05-08

Adds ``user_role_assignments`` (canonical owner: PMIS-user-management;
mirrored in monolith for joins from auth middleware + scoped checks).

A row carries (user_id, role_id, organization_id?, project_id?). The
check constraint ``ck_ura_single_scope`` rejects rows with both scope
columns set — every row is either global, org-scoped, or
project-scoped.

Backfill steps (idempotent):
  1. Copy every row from ``user_roles`` into ``user_role_assignments``
     as a global-scope row (org_id = NULL, project_id = NULL).
  2. For each ``project_members`` row whose ``roles`` JSON contains
     a recognised role name (project_admin / project_member / member /
     viewer), insert a project-scoped assignment row pointing at that
     project.

Both backfill steps look at existing rows and skip duplicates so this
migration can be re-run safely.

Downgrade drops the table (data lost). The new permission rows /
seeded role rows that user-mgmt's ``sync_builtin_permissions`` adds
on boot are NOT touched — they're additive and harmless to leave.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d0c41a55145d"
down_revision: Union[str, Sequence[str], None] = "e3f5b7a8c1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Idempotent: skip if the table already exists.
    if "user_role_assignments" not in inspector.get_table_names():
        op.create_table(
            "user_role_assignments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("project_id", sa.String(length=36), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
            ),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
            sa.ForeignKeyConstraint(["organization_id"], ["vendors.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.CheckConstraint(
                "(organization_id IS NULL) OR (project_id IS NULL)",
                name="ck_ura_single_scope",
            ),
            sa.UniqueConstraint(
                "user_id", "role_id", "organization_id", "project_id",
                name="uq_user_role_assignment_scope",
            ),
        )
        op.create_index(
            "idx_ura_user", "user_role_assignments", ["user_id"]
        )
        op.create_index(
            "idx_ura_project", "user_role_assignments", ["project_id"]
        )
        op.create_index(
            "idx_ura_org", "user_role_assignments", ["organization_id"]
        )
        op.create_index(
            "idx_ura_role", "user_role_assignments", ["role_id"]
        )

    # ------------------------------------------------------------------
    # Backfill 1 — copy user_roles → user_role_assignments (global).
    # ------------------------------------------------------------------
    # Only insert rows that don't already exist (idempotent).
    bind.execute(sa.text("""
        INSERT INTO user_role_assignments (user_id, role_id, organization_id, project_id, created_at)
        SELECT ur.user_id, ur.role_id, NULL, NULL, ur.created_at
        FROM user_roles ur
        WHERE NOT EXISTS (
            SELECT 1 FROM user_role_assignments ura
            WHERE ura.user_id = ur.user_id
              AND ura.role_id = ur.role_id
              AND ura.organization_id IS NULL
              AND ura.project_id IS NULL
        )
    """))

    # ------------------------------------------------------------------
    # Backfill 2 — project_members.roles[] → project-scoped assignments.
    # ------------------------------------------------------------------
    # ``roles`` is a JSON array of role *names*. We map each known name
    # to its role_id and insert a project-scoped row. Unknown names are
    # ignored (fail-soft — admin can re-grant manually).
    #
    # The Postgres path uses jsonb_array_elements_text. SQLite (test path)
    # stores JSON as TEXT and doesn't have that function — we skip the
    # backfill on SQLite (tests don't depend on it; production runs PG).
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("""
            INSERT INTO user_role_assignments (user_id, role_id, organization_id, project_id, created_at)
            SELECT pm.user_id, r.id, NULL, pm.project_id, pm.created_at
            FROM project_members pm
            CROSS JOIN LATERAL jsonb_array_elements_text(
                CASE WHEN jsonb_typeof(pm.roles::jsonb) = 'array'
                     THEN pm.roles::jsonb
                     ELSE '[]'::jsonb
                END
            ) AS role_name
            JOIN roles r ON r.name = role_name
            WHERE NOT EXISTS (
                SELECT 1 FROM user_role_assignments ura
                WHERE ura.user_id = pm.user_id
                  AND ura.role_id = r.id
                  AND ura.organization_id IS NULL
                  AND ura.project_id = pm.project_id
            )
        """))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_role_assignments" in inspector.get_table_names():
        op.drop_index("idx_ura_role", table_name="user_role_assignments")
        op.drop_index("idx_ura_org", table_name="user_role_assignments")
        op.drop_index("idx_ura_project", table_name="user_role_assignments")
        op.drop_index("idx_ura_user", table_name="user_role_assignments")
        op.drop_table("user_role_assignments")
