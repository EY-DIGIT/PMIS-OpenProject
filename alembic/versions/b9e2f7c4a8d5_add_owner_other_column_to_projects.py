"""add owner_other column to projects

Revision ID: b9e2f7c4a8d5
Revises: 7c4a91d8e3f0
Create Date: 2026-04-29 00:00:00.000000

Adds ``projects.owner_other`` (VARCHAR(255), nullable). Captures the
free-text label when ``owner == 'others'`` — symmetric with the
existing ``category_other`` column. Required at the service layer
when owner is 'others'; MUST be NULL otherwise.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9e2f7c4a8d5"
down_revision: Union[str, Sequence[str], None] = "7c4a91d8e3f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "projects",
        sa.Column("owner_other", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projects", "owner_other")
