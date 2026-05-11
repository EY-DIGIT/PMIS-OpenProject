"""Rename resource_type CCM to CCN.

Revision ID: e7f4a8b9c1d2
Revises: c262a1b3e895
Create Date: 2026-04-30

Renames the ``ccm`` row in the ``resource_types`` catalog to ``ccn``
("Change Control Notice"). The seed in ``init_db`` is updated to match,
so fresh installs go straight to ``ccn`` and existing installs get
the in-place rename via this migration.

The row's ``id`` (UUID) is preserved, so any existing
``activity_resources.type_of_resource_id`` references stay valid —
they continue to point at the same row, which now has the new code
and display name.

Idempotent: the WHERE filter on ``code='ccm'`` makes a re-run a no-op
on a DB that's already been migrated (or that never had the old row).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e7f4a8b9c1d2"
down_revision: Union[str, Sequence[str], None] = "c262a1b3e895"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename ccm -> ccn (and update display name)."""
    op.execute(
        "UPDATE resource_types "
        "SET code = 'ccn', name = 'Change Control Notice' "
        "WHERE code = 'ccm';"
    )


def downgrade() -> None:
    """Reverse: rename ccn -> ccm (restore old display name)."""
    op.execute(
        "UPDATE resource_types "
        "SET code = 'ccm', name = 'Change Control Memo' "
        "WHERE code = 'ccn';"
    )
