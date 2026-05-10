"""doc 45 round 9b: add users.org_role tier column

Revision ID: e9f1c3a5b704
Revises: d6b9c4f8a3e1
Create Date: 2026-05-10

Adds a stored copy of the user's intended orgRole tier label to the
``users`` table. The FE has been getting ``orgRole=null`` after creating
a project-tier user (project_admin / project_member / division_member)
without ``project_ids``, because the create-user service only writes
to ``user_role_assignments`` when there's a scope to attach the role
to (a project_id), and ``derive_org_role`` reads exclusively from
that table.

The new column is the persistent "what tier did the FE ask for"
label. ``derive_org_role`` falls back to it when no role-assignment
row matches. Authorization is unchanged — permissions are still
sourced exclusively from ``user_role_assignments`` / ``user_roles``.

Idempotent. Re-running on an already-migrated DB is a no-op.

Round 10 hotfix: the original revision ID ``a1b2c3d4e5f6`` collided
with ``a1b2c3d4e5f6_add_milestone_dependencies_table`` already in
the chain — ``alembic upgrade head`` crashed with a duplicate
revision error and the deploy script bailed before bringing the
service up. Renamed to ``e9f1c3a5b704`` (kept the same
``down_revision`` since ``d6b9c4f8a3e1`` is the actual live head
post the existing milestone_deps → rbac → ... chain).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e9f1c3a5b704"
down_revision: Union[str, Sequence[str], None] = "d6b9c4f8a3e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in set(inspector.get_table_names()):
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "users", "org_role"):
        op.add_column(
            "users",
            sa.Column("org_role", sa.String(length=50), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "users", "org_role"):
        op.drop_column("users", "org_role")
