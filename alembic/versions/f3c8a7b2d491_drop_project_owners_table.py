"""Drop project_owners table (doc 20).

The per-user project-owner whitelist became dead code in doc 18 when
``project.owner`` switched from a user-login reference to a strict
division code (``tmd1`` / ``tmd2`` / ``others``). The catalog endpoints
(GET / POST /create / DELETE) were never consulted by the project create
or update flows after that change. Doc 20 removes the table along with
the model, repository, and routes.

The downgrade re-creates an empty table with the original schema so a
rollback puts the file structure back, but the row data is gone — there
was nothing to back up because the rows had no functional consumers.

Revision ID: f3c8a7b2d491
Revises: eea66b52f947
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa


revision = "f3c8a7b2d491"
down_revision = "eea66b52f947"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("project_owners")


def downgrade() -> None:
    """Re-create an empty project_owners table matching the original
    schema. Row data from before the upgrade is not restored — the
    catalog had no functional consumers (the project create / update
    flows stopped reading it in doc 18) so there was nothing operational
    to back up. If a re-introduction is ever needed, repopulate via the
    POST /project_owners/create endpoint that the upgrade also removed.
    """
    op.create_table(
        "project_owners",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_project_owners_user_id"),
    )
    op.create_index(
        "idx_project_owners_active_user",
        "project_owners",
        ["active", "user_id"],
    )
