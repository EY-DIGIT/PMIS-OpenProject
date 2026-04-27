"""add actual_start_date column to projects

Revision ID: eb3b19c7487c
Revises: f9b8dd81f7dd
Create Date: 2026-04-27 14:06:16.376060

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb3b19c7487c'
down_revision: Union[str, Sequence[str], None] = 'f9b8dd81f7dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also wanted to drop ``alembic_version_user_svc``,
    # but that table belongs to the SEPARATE pmis-user-service Alembic
    # chain that shares this database. Removing it would break the
    # user-service's migration tracking. Intentionally NOT dropped.
    op.add_column(
        'projects',
        sa.Column('actual_start_date', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'actual_start_date')
