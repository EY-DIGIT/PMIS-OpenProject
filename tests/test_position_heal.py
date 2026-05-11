"""Tests for ``app/shared/position_heal.py``.

The heal helper is what unblocks deployments whose data already had
duplicate ``(parent_id, position) WHERE deleted_at IS NULL`` rows when
the doc 22 migration tries to add the partial unique index.

We test it against in-memory SQLite tables built WITHOUT the unique
index (simulating pre-migration state) so we can deliberately seed
duplicates that violate the soon-to-be-added invariant.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import (
    Column, DateTime, Integer, MetaData, String, Table, create_engine, text,
)
from sqlalchemy.orm import Session

from app.shared.position_heal import (
    heal_all_position_duplicates,
    heal_duplicate_positions,
)


# ---------------------------------------------------------------------------
# Pre-migration shape: same column set the M/A/T/S tables have, but WITHOUT
# the partial unique index. Lets us seed duplicates the heal then fixes.
# ---------------------------------------------------------------------------

@pytest.fixture()
def heal_engine():
    """A standalone in-memory SQLite engine + the four tables the heal cares
    about, with NO unique index on ``(parent_id, position)``. Each test gets
    a fresh DB.
    """
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()

    # Trimmed copies of the real M/A/T/S schemas. We only need the columns
    # the heal touches: id (PK), the parent FK column, position, deleted_at.
    Table(
        "milestones", metadata,
        Column("id", String(36), primary_key=True),
        Column("project_id", String(36), nullable=False),
        Column("position", Integer, nullable=False, default=0),
        Column("deleted_at", DateTime, nullable=True),
    )
    Table(
        "activities", metadata,
        Column("id", String(36), primary_key=True),
        Column("milestone_id", String(36), nullable=False),
        Column("position", Integer, nullable=False, default=0),
        Column("deleted_at", DateTime, nullable=True),
    )
    Table(
        "tasks", metadata,
        Column("id", String(36), primary_key=True),
        Column("activity_id", String(36), nullable=False),
        Column("position", Integer, nullable=False, default=0),
        Column("deleted_at", DateTime, nullable=True),
    )
    Table(
        "subtasks", metadata,
        Column("id", String(36), primary_key=True),
        Column("task_id", String(36), nullable=False),
        Column("position", Integer, nullable=False, default=0),
        Column("deleted_at", DateTime, nullable=True),
    )

    metadata.create_all(engine)
    yield engine
    engine.dispose()


def _seed(engine, table: str, parent_col: str, rows):
    """Insert raw rows. ``rows`` is a list of dicts.

    Bypasses any ORM and any uniqueness check (there is none — see
    ``heal_engine``). Each row should supply ``id``, ``<parent_col>``,
    ``position`` and ``deleted_at`` keys.
    """
    with engine.begin() as conn:
        for row in rows:
            cols = ", ".join(row.keys())
            params = ", ".join(f":{k}" for k in row.keys())
            conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({params})"), row)


def _fetch_all(engine, table: str, parent_col: str):
    with engine.begin() as conn:
        return [
            dict(r._mapping)
            for r in conn.execute(text(
                f"SELECT id, {parent_col}, position, deleted_at "
                f"FROM {table} ORDER BY id"
            )).fetchall()
        ]


# ===========================================================================
# Pure heal behaviour
# ===========================================================================

class TestHealDuplicatePositions:

    def test_no_duplicates_no_op(self, heal_engine):
        """Clean data → 0 rows touched, no churn."""
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 1, "deleted_at": None},
            {"id": "a3", "milestone_id": "m1", "position": 2, "deleted_at": None},
        ])
        with heal_engine.begin() as conn:
            n = heal_duplicate_positions(conn, "activities", "milestone_id")
        assert n == 0
        # Positions are unchanged.
        rows = _fetch_all(heal_engine, "activities", "milestone_id")
        positions = sorted([r["position"] for r in rows])
        assert positions == [0, 1, 2]

    def test_two_at_position_zero_renumbers_loser(self, heal_engine):
        """The smallest id at the dup position keeps it; the other gets max+1."""
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": None},  # dup loser
            {"id": "a3", "milestone_id": "m1", "position": 5, "deleted_at": None},
        ])
        with heal_engine.begin() as conn:
            n = heal_duplicate_positions(conn, "activities", "milestone_id")
        assert n == 1

        rows = {r["id"]: r["position"] for r in _fetch_all(heal_engine, "activities", "milestone_id")}
        assert rows["a1"] == 0  # winner kept its position (smallest id)
        assert rows["a2"] == 6  # loser renumbered to max+1 (max was 5)
        assert rows["a3"] == 5  # untouched

    def test_three_at_same_position_renumbers_two_losers(self, heal_engine):
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a3", "milestone_id": "m1", "position": 0, "deleted_at": None},
        ])
        with heal_engine.begin() as conn:
            n = heal_duplicate_positions(conn, "activities", "milestone_id")
        assert n == 2

        rows = {r["id"]: r["position"] for r in _fetch_all(heal_engine, "activities", "milestone_id")}
        assert rows["a1"] == 0  # winner
        # The other two get 1, 2 (max was 0; renumber to 1, 2)
        assert sorted([rows["a2"], rows["a3"]]) == [1, 2]
        # No two rows share a position now.
        assert len({rows["a1"], rows["a2"], rows["a3"]}) == 3

    def test_soft_deleted_duplicates_ignored(self, heal_engine):
        """Soft-deleted rows do not participate in the live invariant; they
        can share positions with live rows freely."""
        now = datetime.now(timezone.utc)
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": now},  # dead
            {"id": "a3", "milestone_id": "m1", "position": 1, "deleted_at": now},  # dead
        ])
        with heal_engine.begin() as conn:
            n = heal_duplicate_positions(conn, "activities", "milestone_id")
        assert n == 0  # No live duplicates.
        rows = {r["id"]: r["position"] for r in _fetch_all(heal_engine, "activities", "milestone_id")}
        # Nothing changed.
        assert rows["a1"] == 0
        assert rows["a2"] == 0
        assert rows["a3"] == 1

    def test_dups_in_different_parents_isolated(self, heal_engine):
        """Two parents each with their own dup — heal handles them
        independently."""
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "b1", "milestone_id": "m2", "position": 3, "deleted_at": None},
            {"id": "b2", "milestone_id": "m2", "position": 3, "deleted_at": None},
        ])
        with heal_engine.begin() as conn:
            n = heal_duplicate_positions(conn, "activities", "milestone_id")
        assert n == 2

        rows = {r["id"]: r["position"] for r in _fetch_all(heal_engine, "activities", "milestone_id")}
        # m1: a1 keeps 0, a2 gets 1
        assert rows["a1"] == 0
        assert rows["a2"] == 1
        # m2: b1 keeps 3, b2 gets 4
        assert rows["b1"] == 3
        assert rows["b2"] == 4

    def test_multiple_dup_groups_same_parent(self, heal_engine):
        """One parent with TWO different dup positions (e.g. 0 and 5)."""
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a3", "milestone_id": "m1", "position": 5, "deleted_at": None},
            {"id": "a4", "milestone_id": "m1", "position": 5, "deleted_at": None},
        ])
        with heal_engine.begin() as conn:
            n = heal_duplicate_positions(conn, "activities", "milestone_id")
        assert n == 2

        rows = {r["id"]: r["position"] for r in _fetch_all(heal_engine, "activities", "milestone_id")}
        # All four positions are now distinct.
        assert len({rows["a1"], rows["a2"], rows["a3"], rows["a4"]}) == 4
        # Winners kept their positions.
        assert rows["a1"] == 0
        assert rows["a3"] == 5
        # Losers got max+1 each — max recomputed per group, so a2 lands
        # at 6 (max=5+1), a4 at 7 (max=6+1 after a2 was renumbered).
        assert sorted([rows["a2"], rows["a4"]]) == [6, 7]

    def test_idempotent_runs_zero_on_second_call(self, heal_engine):
        """A second call right after a successful heal does nothing."""
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": None},
        ])
        with heal_engine.begin() as conn:
            first = heal_duplicate_positions(conn, "activities", "milestone_id")
            second = heal_duplicate_positions(conn, "activities", "milestone_id")
        assert first == 1
        assert second == 0


# ===========================================================================
# After heal, the partial-unique index can actually be created
# ===========================================================================

class TestHealEnablesUniqueIndex:

    def test_index_creation_succeeds_after_heal(self, heal_engine):
        """End-to-end: seed dups → heal → CREATE UNIQUE INDEX succeeds."""
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a3", "milestone_id": "m1", "position": 0, "deleted_at": None},
        ])
        with heal_engine.begin() as conn:
            heal_duplicate_positions(conn, "activities", "milestone_id")
            # Without the heal, this would fail with UNIQUE constraint
            # violation. Recreate the same partial-unique index the
            # migration adds.
            conn.execute(text(
                "CREATE UNIQUE INDEX uq_activities_milestone_position_live "
                "ON activities (milestone_id, position) "
                "WHERE deleted_at IS NULL"
            ))
        # If we get here without raising, the index was successfully created
        # on the post-heal data.

    def test_index_creation_would_fail_without_heal(self, heal_engine):
        """Sanity check: confirm the duplicate-position scenario actually
        breaks the unique-index creation BEFORE we heal. Locks in the
        contract that the heal is what makes the migration succeed."""
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": None},
        ])
        with pytest.raises(Exception):
            with heal_engine.begin() as conn:
                conn.execute(text(
                    "CREATE UNIQUE INDEX uq_activities_milestone_position_live "
                    "ON activities (milestone_id, position) "
                    "WHERE deleted_at IS NULL"
                ))


# ===========================================================================
# heal_all_position_duplicates — the convenience wrapper
# ===========================================================================

class TestHealAll:

    def test_runs_for_every_table(self, heal_engine):
        """Returns a {table: count} map covering all four M/A/T/S tables."""
        # Seed dups in two of the four tables.
        _seed(heal_engine, "activities", "milestone_id", [
            {"id": "a1", "milestone_id": "m1", "position": 0, "deleted_at": None},
            {"id": "a2", "milestone_id": "m1", "position": 0, "deleted_at": None},
        ])
        _seed(heal_engine, "tasks", "activity_id", [
            {"id": "t1", "activity_id": "a1", "position": 7, "deleted_at": None},
            {"id": "t2", "activity_id": "a1", "position": 7, "deleted_at": None},
        ])
        with heal_engine.begin() as conn:
            results = heal_all_position_duplicates(conn)
        # Exactly four keys, M/A/T/S; the two with dups have count > 0.
        assert set(results.keys()) == {"milestones", "activities", "tasks", "subtasks"}
        assert results["activities"] == 1
        assert results["tasks"] == 1
        assert results["milestones"] == 0
        assert results["subtasks"] == 0
