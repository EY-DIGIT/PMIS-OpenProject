"""add divisions table

Revision ID: c3a8d5e1b962
Revises: b9e2f7c4a8d5
Create Date: 2026-04-29 00:30:00.000000

Adds the ``divisions`` table that backs the project-owner picker.
Three built-in rows (`tmd1` / `tmd2` / `others`) are seeded by
``init_db`` on first boot — the migration only creates the empty
table. User-added rows appear when projects are created with
``owner='others'`` + a free-text ``ownerOther`` label.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3a8d5e1b962"
down_revision: Union[str, Sequence[str], None] = "b9e2f7c4a8d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "divisions",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_other", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_divisions_code"),
    )
    op.create_index("ix_divisions_code", "divisions", ["code"])
    op.create_index("ix_divisions_active", "divisions", ["active"])
    op.create_index("idx_divisions_code_active", "divisions", ["code", "active"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_divisions_code_active", table_name="divisions")
    op.drop_index("ix_divisions_active", table_name="divisions")
    op.drop_index("ix_divisions_code", table_name="divisions")
    op.drop_table("divisions")
