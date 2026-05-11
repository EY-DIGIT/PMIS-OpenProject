"""Shorten resource_type display names to short codes.

Revision ID: b3c5d7e9f1a2
Revises: f8a9c2d1e3b4
Create Date: 2026-04-30

The FE Resource Type dropdown renders ``name`` as the visible label.
Per product spec the dropdown should show the short uppercase form
("RFP", "ASG", "CCN") rather than the long-form descriptions
("Request for Proposal", "Assignment", "Change Control Notice").

This migration updates the seeded rows in-place. The row UUIDs
remain unchanged so any ``activity_resources.type_of_resource_id``
references stay valid — the rows just now have shorter names.

The seed in ``init_db`` is updated to match, so fresh installs go
straight to the short names.

Idempotent: each ``UPDATE`` filters by code, so a re-run on a DB
that already has the short names is effectively a no-op (Postgres
will still write the same value back).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3c5d7e9f1a2"
down_revision: Union[str, Sequence[str], None] = "f8a9c2d1e3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set name = uppercase code for the three seeded built-ins."""
    op.execute("UPDATE resource_types SET name = 'RFP' WHERE code = 'rfp';")
    op.execute("UPDATE resource_types SET name = 'ASG' WHERE code = 'asg';")
    op.execute("UPDATE resource_types SET name = 'CCN' WHERE code = 'ccn';")


def downgrade() -> None:
    """Restore the long-form display names."""
    op.execute(
        "UPDATE resource_types SET name = 'Request for Proposal' "
        "WHERE code = 'rfp';"
    )
    op.execute(
        "UPDATE resource_types SET name = 'Assignment' WHERE code = 'asg';"
    )
    op.execute(
        "UPDATE resource_types SET name = 'Change Control Notice' "
        "WHERE code = 'ccn';"
    )
