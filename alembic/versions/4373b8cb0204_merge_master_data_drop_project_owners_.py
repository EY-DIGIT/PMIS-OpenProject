"""Merge: master-data router/project_owners drop + resource_type cleanup/rename.

Two doc-20-era migration chains independently revised ``eea66b52f947``
in parallel:

* ``f3c8a7b2d491`` — drops the ``project_owners`` table (this branch's
  Part 3 of doc 20).
* ``b3c5d7e9f1a2`` — chained from ``f8a9c2d1e3b4``: kamal21's catalog
  cleanup (purges leftover ``test_*`` rows from ``resource_types`` and
  any rogue divisions) followed by a display-name normalisation
  (``ASG`` -> ``Assignment`` style was wrong; this restores short
  codes).

Both chains apply cleanly on the same database; this merge revision
exists only to give Alembic a single head so ``alembic upgrade head``
resolves unambiguously on boot. No DDL or data changes are emitted by
the merge itself — each parent does its own work.

Revision ID: 4373b8cb0204
Revises: f3c8a7b2d491, b3c5d7e9f1a2
Create Date: 2026-04-30
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '4373b8cb0204'
down_revision: Union[str, Sequence[str], None] = (
    'f3c8a7b2d491', 'b3c5d7e9f1a2',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op merge: each parent revision applies its own DDL/data."""
    pass


def downgrade() -> None:
    """No-op: downgrade past this revision splits the chain back into
    the two parent heads. Each parent's downgrade still works
    individually."""
    pass
