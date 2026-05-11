"""Uppercase priority codes (P1/P2/P3) — UI alignment.

Revision ID: d2c4f1a9b8e7
Revises: e9f1c3a5b704
Create Date: 2026-05-11

The ``priorities`` catalog seeded ``p1`` / ``p2`` / ``p3`` lowercase
codes (see e3f5b7a8c1d4_add_priorities_catalog.py). The FE shows
these as labels and wants them uppercase ("P1") without a per-render
translation, so the canonical persisted form flips to uppercase here.

This migration:

  1. Updates the four M/A/T/S tables' ``priority`` column rows from
     lowercase → uppercase. Soft-deleted rows included so a restore
     doesn't bring back a stale lowercase value that the validator
     would now reject.

  2. Updates the ``priorities`` catalog rows so ``code`` is the
     canonical uppercase form. The ``name`` column is left unchanged
     where it was something other than the lowercase code (e.g. the
     monolith seed used ``name='p1'`` — those are also uppercased so
     the API response is consistent).

The downgrade reverses both.

Notes:
  * The Pydantic ``_normalize_priority`` validators on every M/A/T/S
    schema uppercase incoming values, so legacy callers still sending
    ``"p1"`` keep working through the transition. Server stores ``P1``.
  * If an admin has added custom priority codes outside ``p1/p2/p3``
    (the schema does not constrain to that triple — codes are catalog-
    driven), those custom rows are NOT touched. Only the three seed
    codes flip.
"""
from typing import List, Tuple
from alembic import op
import sqlalchemy as sa


revision = "d2c4f1a9b8e7"
down_revision = "e9f1c3a5b704"
branch_labels = None
depends_on = None


# Mapping: (old, new). Catalog seed codes only.
_SEED_PAIRS: List[Tuple[str, str]] = [
    ("p1", "P1"),
    ("p2", "P2"),
    ("p3", "P3"),
]


# Tables that hold a ``priority`` string column referring to a
# ``priorities.code`` (doc 41 / its follow-ups).
_DEPENDENT_TABLES = ("milestones", "activities", "tasks", "subtasks")


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Flip dependent rows first. Doing this before the catalog
    #    update means the catalog-side update never breaks any FK
    #    semantic (we don't have a real FK here — priority is stored
    #    as a string — but order keeps the data internally consistent
    #    at every step of the migration).
    for table in _DEPENDENT_TABLES:
        for old, new in _SEED_PAIRS:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET priority = :new WHERE priority = :old"
                ),
                {"old": old, "new": new},
            )

    # 2) Flip catalog rows. Update both ``code`` and ``name`` so the
    #    catalog endpoint shows uppercase consistently. The unique
    #    constraint on ``code`` is preserved across the rename (no
    #    intermediate collision because old and new sets are disjoint).
    for old, new in _SEED_PAIRS:
        bind.execute(
            sa.text(
                "UPDATE priorities SET code = :new "
                "WHERE code = :old"
            ),
            {"old": old, "new": new},
        )
        # ``name`` originally seeded as the lowercase code itself; flip
        # to uppercase only when it matches the old code (don't touch
        # admin-customised names).
        bind.execute(
            sa.text(
                "UPDATE priorities SET name = :new "
                "WHERE code = :new AND name = :old"
            ),
            {"old": old, "new": new},
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Reverse catalog update first so the dependent-row update below
    # always finds the lowercase target it expects.
    for old, new in _SEED_PAIRS:
        bind.execute(
            sa.text(
                "UPDATE priorities SET name = :old "
                "WHERE code = :new AND name = :new"
            ),
            {"old": old, "new": new},
        )
        bind.execute(
            sa.text(
                "UPDATE priorities SET code = :old "
                "WHERE code = :new"
            ),
            {"old": old, "new": new},
        )

    for table in _DEPENDENT_TABLES:
        for old, new in _SEED_PAIRS:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET priority = :old WHERE priority = :new"
                ),
                {"old": old, "new": new},
            )
