"""add vendor soft-delete columns

Revision ID: 7c4a91d8e3f0
Revises: 4825a33f9ed3
Create Date: 2026-04-28 00:00:00.000000

Adds ``vendors.deleted_at`` + ``vendors.deleted_by`` so DELETE /vendors/{id}
can soft-delete a vendor without losing the project_vendors / milestone_vendors
mapping rows. Also adds an index on ``vendors.created_at`` to back the
newest-first list ordering used by the Search Vendor view.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c4a91d8e3f0"
down_revision: Union[str, Sequence[str], None] = "4825a33f9ed3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "vendors",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "vendors",
        sa.Column("deleted_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_vendors_deleted_by_users",
        "vendors", "users",
        ["deleted_by"], ["id"],
    )
    op.create_index("idx_vendors_deleted_at", "vendors", ["deleted_at"])
    op.create_index("idx_vendors_created_at", "vendors", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_vendors_created_at", table_name="vendors")
    op.drop_index("idx_vendors_deleted_at", table_name="vendors")
    op.drop_constraint("fk_vendors_deleted_by_users", "vendors", type_="foreignkey")
    op.drop_column("vendors", "deleted_by")
    op.drop_column("vendors", "deleted_at")
