"""Add refresh-token grace-window columns to users.

Adds two nullable columns to ``users`` so the auth services can hold the
just-rotated-out refresh-token jti for a configurable window
(``REFRESH_TOKEN_GRACE_SECONDS``) after every rotation event:

* ``previous_refresh_token_jti``                     VARCHAR(64) NULL
* ``previous_refresh_token_jti_valid_until``         DATETIME    NULL

Both columns default to NULL on existing rows — no data backfill needed.

Revision ID: e7d2b3a4f981
Revises: c262a1b3e895
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa


revision = "e7d2b3a4f981"
down_revision = "c262a1b3e895"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("previous_refresh_token_jti", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("previous_refresh_token_jti_valid_until", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "previous_refresh_token_jti_valid_until")
    op.drop_column("users", "previous_refresh_token_jti")
