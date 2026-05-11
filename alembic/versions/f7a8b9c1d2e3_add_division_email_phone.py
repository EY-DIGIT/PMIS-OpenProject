"""Add divisions.email + divisions.phone_number.

Revision ID: f7a8b9c1d2e3
Revises: e6f7a8b9c1d2
Create Date: 2026-05-06 14:00:00

Adds optional contact details to the ``divisions`` table — a shared
mailbox / hotline per division. Both columns are nullable: the seeded
``tmd1`` / ``tmd2`` / ``others`` rows leave them NULL and admins can
populate per-division as needed via PATCH /api/v3/master/divisions/{code}.

Mirrors the same column shapes used for vendors (doc 18):
  - ``email``        : VARCHAR(255), nullable, indexed
  - ``phone_number`` : VARCHAR(50),  nullable, free-form
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c1d2e3"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("divisions") as b:
        b.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("phone_number", sa.String(length=50), nullable=True))
    op.create_index("ix_divisions_email", "divisions", ["email"])


def downgrade() -> None:
    op.drop_index("ix_divisions_email", table_name="divisions")
    with op.batch_alter_table("divisions") as b:
        b.drop_column("phone_number")
        b.drop_column("email")
