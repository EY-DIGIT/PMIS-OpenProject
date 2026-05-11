"""Cleanup test data in resource_types and divisions catalogs.

Revision ID: f8a9c2d1e3b4
Revises: eea66b52f947
Create Date: 2026-04-30

Both catalogs accumulated dummy / admin-created rows during testing
that pollute the dropdowns the FE renders:
  - ``resource_types`` had auto-generated "Test Resource Type
    <timestamp>" rows from the admin "create resource type" flow.
  - ``divisions`` had user-added rows ("admin", "test", "come") that
    appeared when projects were saved with ``owner='others'`` plus
    those free-text labels (kamal's slugify-on-others-label flow).

This migration purges them, leaving only the canonical seeded values:
  - resource_types: rfp / asg / ccn
  - divisions: tmd1 / tmd2 / others

resource_types cleanup is FK-aware. ``activity_resources.type_of_
resource_id`` is a hard FK to ``resource_types.id``. Rows that no
activity references are deleted outright. Rows that *are* referenced
are kept (FK preserved) but flipped to ``active = false`` so the
``GET /api/v3/resource_types`` listing (which filters active=true)
no longer surfaces them.

divisions cleanup is unconditional delete. There are no incoming
FKs (kamal's design uses codes as wire values, not FKs from other
tables), so non-built-in rows can be removed directly.

Idempotent — re-running on an already-clean DB is a no-op.
Downgrade is intentionally a no-op: the dummy rows had unrecoverable
codes / labels and no audit trail; restoring them is impossible.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f8a9c2d1e3b4"
down_revision: Union[str, Sequence[str], None] = "eea66b52f947"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Purge non-canonical rows from the two catalog tables."""
    # 1. resource_types — delete any non-canonical row that is NOT
    # referenced by activity_resources.type_of_resource_id.
    op.execute(
        """
        DELETE FROM resource_types
        WHERE code NOT IN ('rfp', 'asg', 'ccn')
          AND id NOT IN (
              SELECT DISTINCT type_of_resource_id
              FROM activity_resources
              WHERE type_of_resource_id IS NOT NULL
          );
        """
    )

    # 2. resource_types — anything still around (i.e. referenced by an
    # activity_resource row) gets deactivated so the catalog endpoint
    # filters it out. The FK relationship stays valid.
    op.execute(
        """
        UPDATE resource_types
        SET active = false
        WHERE code NOT IN ('rfp', 'asg', 'ccn');
        """
    )

    # 3. divisions — wipe non-built-in rows. No incoming FKs means a
    # straight DELETE is safe; codes-as-wire-values mean any
    # ``projects.owner`` referencing a deleted code becomes "unknown
    # division" in the picker but the project row itself is unaffected.
    op.execute(
        """
        DELETE FROM divisions
        WHERE is_builtin = false;
        """
    )


def downgrade() -> None:
    """Intentionally a no-op.

    The dummy rows had auto-generated names / unknown codes; we have
    no record of what to restore. If a downgrade is ever needed, an
    operator can re-add specific rows manually via the admin endpoints
    (POST /api/v3/resource_types/create or by saving a project with
    owner='others' + ownerOther='<label>').
    """
    pass
