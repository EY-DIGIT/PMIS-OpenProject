"""Merge: refresh-token grace window + rename resource_type ccm -> ccn.

Two migrations independently revised ``c262a1b3e895`` in parallel:

* ``e7d2b3a4f981`` — adds the refresh-token grace-window columns to ``users``
  (this branch).
* ``e7f4a8b9c1d2`` — renames the ``resource_types`` row code from ``ccm`` to
  ``ccn`` (kamal21).

Both apply cleanly on the same database; this merge revision exists only
to give Alembic a single head so ``alembic upgrade head`` resolves
unambiguously on boot. No DDL or data changes are emitted by the merge
itself — each parent does its own work.

Revision ID: eea66b52f947
Revises: e7d2b3a4f981, e7f4a8b9c1d2
Create Date: 2026-04-30
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'eea66b52f947'
down_revision: Union[str, Sequence[str], None] = ('e7d2b3a4f981', 'e7f4a8b9c1d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op merge: each parent revision applies its own DDL."""
    pass


def downgrade() -> None:
    """No-op: downgrade past this revision splits the chain back into the
    two parent heads. Each parent's downgrade still works individually."""
    pass
