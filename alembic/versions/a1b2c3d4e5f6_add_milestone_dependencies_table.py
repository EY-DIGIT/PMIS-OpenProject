"""Add milestone_dependencies table (doc 21 part A).

Mirrors the activity/task/subtask dependency tables: surrogate UUID PK,
soft-delete via ``deleted_at``, partial unique on the (source, target)
pair WHERE ``deleted_at IS NULL`` so historical rows can coexist with a
fresh live edge.

The legacy ``milestones.depends`` JSON column is left in place for
forward/back compatibility on the column ALTER, but services no longer
read or write it once the new edge table ships.

Revision ID: a1b2c3d4e5f6
Revises: 4373b8cb0204
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "4373b8cb0204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "milestone_dependencies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_milestone_id",
            sa.String(length=36),
            sa.ForeignKey("milestones.id"),
            nullable=False,
        ),
        sa.Column(
            "target_milestone_id",
            sa.String(length=36),
            sa.ForeignKey("milestones.id"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "idx_milestone_deps_source_live",
        "milestone_dependencies",
        ["source_milestone_id", "deleted_at"],
    )
    op.create_index(
        "idx_milestone_deps_target_live",
        "milestone_dependencies",
        ["target_milestone_id", "deleted_at"],
    )
    op.create_index(
        "idx_milestone_deps_project_live",
        "milestone_dependencies",
        ["project_id", "deleted_at"],
    )
    op.create_index(
        "uq_milestone_deps_pair_live",
        "milestone_dependencies",
        ["source_milestone_id", "target_milestone_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_milestone_deps_pair_live", table_name="milestone_dependencies"
    )
    op.drop_index(
        "idx_milestone_deps_project_live", table_name="milestone_dependencies"
    )
    op.drop_index(
        "idx_milestone_deps_target_live", table_name="milestone_dependencies"
    )
    op.drop_index(
        "idx_milestone_deps_source_live", table_name="milestone_dependencies"
    )
    op.drop_table("milestone_dependencies")
