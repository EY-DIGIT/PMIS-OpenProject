"""add user soft-delete vendor and division columns

Revision ID: c262a1b3e895
Revises: d4f1a8c5b6e7
Create Date: 2026-04-28

Adds:
- ``users.vendor_id`` (FK to vendors, nullable so the bootstrap admin
  remains valid; API enforces "required at create" via Pydantic)
- ``users.division`` + ``users.division_other`` (enum 'tmd1'/'tmd2'/'others'
  with free-text override)
- ``users.deleted_at`` + ``users.deleted_by`` (soft-delete)
- ``users.created_at`` index (already nullable=False; new index backs the
  newest-first sort on Search User)
- duplicate-friendly indexes on vendors.created_at / deleted_at (the
  ones added in 7c4a91d8e3f0 were "idx_..." prefixed; this run also
  surfaces SQLAlchemy's auto-generated "ix_..." names, harmless)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c262a1b3e895'
down_revision: Union[str, Sequence[str], None] = 'd4f1a8c5b6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also wanted to drop ``alembic_version_user_svc``,
    # but that belongs to the SEPARATE pmis-user-service Alembic chain
    # sharing this database. Intentionally NOT dropped.

    op.add_column('users', sa.Column('vendor_id', sa.String(length=36), nullable=True))
    op.add_column('users', sa.Column('division', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('division_other', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('deleted_by', sa.Integer(), nullable=True))

    op.create_index('idx_users_created_at', 'users', ['created_at'], unique=False)
    op.create_index('idx_users_deleted_at', 'users', ['deleted_at'], unique=False)
    op.create_index('idx_users_vendor_id', 'users', ['vendor_id'], unique=False)

    op.create_foreign_key(
        'fk_users_deleted_by_users',
        'users', 'users', ['deleted_by'], ['id'],
    )
    # Constraint name matches the model's ``use_alter=True`` declaration so
    # SQLAlchemy reflection in tests / dev sees the same name as Alembic
    # creates in production. The name is what breaks the users↔vendors FK
    # cycle for create_all/drop_all in unit tests.
    op.create_foreign_key(
        'fk_users_vendor_id',
        'users', 'vendors', ['vendor_id'], ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_users_vendor_id', 'users', type_='foreignkey')
    op.drop_constraint('fk_users_deleted_by_users', 'users', type_='foreignkey')
    op.drop_index('idx_users_vendor_id', table_name='users')
    op.drop_index('idx_users_deleted_at', table_name='users')
    op.drop_index('idx_users_created_at', table_name='users')
    op.drop_column('users', 'deleted_by')
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'division_other')
    op.drop_column('users', 'division')
    op.drop_column('users', 'vendor_id')
