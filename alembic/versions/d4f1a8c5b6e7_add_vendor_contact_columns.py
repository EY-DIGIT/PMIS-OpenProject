"""add vendor contact columns

Revision ID: d4f1a8c5b6e7
Revises: c3a8d5e1b962
Create Date: 2026-04-29 01:00:00.000000

Adds ``vendors.email`` (VARCHAR(255), nullable), ``vendors.contact_person``
(VARCHAR(255), nullable), and ``vendors.phone_number`` (VARCHAR(50),
nullable). Backs the contact-detail fields on the Vendor Management
screens and the new GET /api/v3/vendors/{id} detail endpoint. Pre-
existing vendors stay NULL until edited.

Includes an index on ``email`` so future "find vendor by email" lookups
stay sub-linear.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4f1a8c5b6e7"
down_revision: Union[str, Sequence[str], None] = "c3a8d5e1b962"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "vendors",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "vendors",
        sa.Column("contact_person", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "vendors",
        sa.Column("phone_number", sa.String(length=50), nullable=True),
    )
    op.create_index("idx_vendors_email", "vendors", ["email"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_vendors_email", table_name="vendors")
    op.drop_column("vendors", "phone_number")
    op.drop_column("vendors", "contact_person")
    op.drop_column("vendors", "email")
