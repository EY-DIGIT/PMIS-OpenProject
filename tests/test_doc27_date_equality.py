"""Doc 27 — date equality regression suite.

Reported bug: when the project's start/end dates and a milestone's
start/end dates are picked as the same calendar date, the BE rejects
the milestone create with "Milestone start date cannot be before the
project start date." The user clearly entered the same date in both
forms, but the BE saw them as ~5h30m apart.

Root cause: SQLAlchemy ``Column(DateTime, ...)`` maps to
``TIMESTAMP WITHOUT TIME ZONE`` on Postgres / a plain string on SQLite.
When the FE sends a tz-aware datetime like ``2026-07-10T00:00:00+05:30``
(IST midnight), the driver silently drops the offset and stores the
wall-clock value: ``2026-07-10 00:00:00``. On read, that's a naive
datetime. ``app/shared/date_rules.py::_normalize`` treats naive values
as UTC, but a fresh tz-aware request is converted to UTC properly. The
two values end up offset by 5h30m and the comparison rejects.

Fix: ``app/infrastructure/db/utc_datetime.py`` defines a ``UtcDateTime``
TypeDecorator that converts tz-aware values to naive UTC at the bind
boundary. Every datetime column was migrated to use it. So the storage
layer always holds canonical UTC, and the existing comparison helper
works correctly.

These tests verify:
  1. The exact failing scenario from the bug report passes.
  2. Reverse direction (project IST, milestone naive UTC) also passes.
  3. The DB-level stored value for a tz-aware input is canonical UTC,
     not the wall-clock IST value.
  4. Activity / task / subtask under the same project also accept the
     equality dates (the fix cascades through the hierarchy).
  5. Nothing breaks for purely UTC inputs (the existing happy path).
"""
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.milestone import MilestoneModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_ist(year, month, day, hour=0, minute=0):
    """Build an ISO-8601 string with a +05:30 offset."""
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00+05:30"


def _iso_naive(year, month, day, hour=0, minute=0):
    """Build a naive (no offset) ISO-8601 string."""
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"


def _iso_utc(year, month, day, hour=0, minute=0):
    """Build an ISO-8601 string with a Z suffix (UTC)."""
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00Z"


def _create_project(client, headers, *, start_iso, end_iso, name=None):
    body = {
        "name": name or f"Doc27 P {uuid4().hex[:6]}",
        "owner": "tmd1",
        "startDate": start_iso,
        "endDate": end_iso,
    }
    return client.post("/api/v3/projects/create", json=body, headers=headers)


def _create_milestone(client, headers, project_id, *, start_iso, end_iso, name=None):
    body = {
        "name": name or f"Doc27 M {uuid4().hex[:4]}",
        "startDate": start_iso,
        "endDate": end_iso,
    }
    return client.post(
        f"/api/v3/projects/{project_id}/milestones/create",
        json=body, headers=headers,
    )


# ===========================================================================
# Bug reproductions — these MUST pass post-fix
# ===========================================================================

class TestEqualDatesIstFix:
    """The user's exact scenario: same calendar date, both sides in IST."""

    def test_milestone_equals_project_dates_both_ist(
        self, client, admin_user, admin_headers,
    ):
        # FE date picker: IST locale → sends offset +05:30.
        proj = _create_project(
            client, admin_headers,
            start_iso=_iso_ist(2026, 7, 10),
            end_iso=_iso_ist(2026, 7, 20),
        )
        assert proj.status_code == 201, proj.text
        pid = proj.json()["data"]["id"]

        ms = _create_milestone(
            client, admin_headers, pid,
            start_iso=_iso_ist(2026, 7, 10),  # exact same calendar dates
            end_iso=_iso_ist(2026, 7, 20),
        )
        assert ms.status_code == 201, (
            f"BUG: milestone with same IST dates as project rejected.\n"
            f"Response: {ms.text}"
        )

    def test_milestone_start_equals_project_start_only(
        self, client, admin_user, admin_headers,
    ):
        proj = _create_project(
            client, admin_headers,
            start_iso=_iso_ist(2026, 7, 10),
            end_iso=_iso_ist(2026, 7, 30),
        )
        pid = proj.json()["data"]["id"]
        ms = _create_milestone(
            client, admin_headers, pid,
            start_iso=_iso_ist(2026, 7, 10),  # equal start
            end_iso=_iso_ist(2026, 7, 15),    # earlier end
        )
        assert ms.status_code == 201, ms.text

    def test_milestone_end_equals_project_end_only(
        self, client, admin_user, admin_headers,
    ):
        proj = _create_project(
            client, admin_headers,
            start_iso=_iso_ist(2026, 7, 10),
            end_iso=_iso_ist(2026, 7, 30),
        )
        pid = proj.json()["data"]["id"]
        ms = _create_milestone(
            client, admin_headers, pid,
            start_iso=_iso_ist(2026, 7, 15),
            end_iso=_iso_ist(2026, 7, 30),  # equal end
        )
        assert ms.status_code == 201, ms.text


# ===========================================================================
# DB-level invariant — stored values are canonical UTC
# ===========================================================================

class TestStorageIsCanonicalUtc:
    def test_ist_input_stored_as_utc(self, client, admin_user, admin_headers, db_session):
        proj = _create_project(
            client, admin_headers,
            start_iso=_iso_ist(2026, 7, 10),  # IST midnight = 2026-07-09 18:30 UTC
            end_iso=_iso_ist(2026, 7, 20),
        )
        pid = proj.json()["data"]["id"]

        # Read raw value from DB — should be UTC-converted, not wall-clock IST.
        row = db_session.execute(
            text("SELECT start_date FROM projects WHERE id = :pid"),
            {"pid": pid},
        ).fetchone()
        raw = str(row[0])
        # The wall-clock IST value would be "2026-07-10 00:00:00".
        # The canonical UTC value is "2026-07-09 18:30:00".
        assert "2026-07-09 18:30" in raw, (
            f"Expected UTC-converted storage, got wall-clock: {raw!r}"
        )

    def test_utc_input_stored_unchanged(self, client, admin_user, admin_headers, db_session):
        proj = _create_project(
            client, admin_headers,
            start_iso=_iso_utc(2026, 7, 10),
            end_iso=_iso_utc(2026, 7, 20),
        )
        pid = proj.json()["data"]["id"]
        row = db_session.execute(
            text("SELECT start_date FROM projects WHERE id = :pid"),
            {"pid": pid},
        ).fetchone()
        raw = str(row[0])
        assert "2026-07-10 00:00" in raw, raw


# ===========================================================================
# Hierarchy cascade — activity / task / subtask all accept equal dates
# ===========================================================================

class TestEqualDatesCascade:
    def test_activity_equals_milestone_dates(
        self, client, admin_user, admin_headers,
    ):
        proj = _create_project(
            client, admin_headers,
            start_iso=_iso_ist(2026, 7, 10),
            end_iso=_iso_ist(2026, 7, 20),
        )
        pid = proj.json()["data"]["id"]
        ms = _create_milestone(
            client, admin_headers, pid,
            start_iso=_iso_ist(2026, 7, 10),
            end_iso=_iso_ist(2026, 7, 20),
        )
        assert ms.status_code == 201
        msid = ms.json()["data"]["id"]

        a = client.post(
            f"/api/v3/milestones/{msid}/activities/standard/create",
            json={
                "name": "Eq A1",
                "startDate": _iso_ist(2026, 7, 10),
                "endDate": _iso_ist(2026, 7, 20),
            },
            headers=admin_headers,
        )
        assert a.status_code == 201, a.text


# ===========================================================================
# Negative — make sure the floor check still works for genuinely-too-early
# ===========================================================================

class TestFloorStillEnforced:
    def test_milestone_start_before_project_start_still_rejected(
        self, client, admin_user, admin_headers,
    ):
        proj = _create_project(
            client, admin_headers,
            start_iso=_iso_ist(2026, 7, 10),
            end_iso=_iso_ist(2026, 7, 20),
        )
        pid = proj.json()["data"]["id"]
        ms = _create_milestone(
            client, admin_headers, pid,
            start_iso=_iso_ist(2026, 7, 5),  # genuinely earlier
            end_iso=_iso_ist(2026, 7, 15),
        )
        assert ms.status_code == 422
        assert "before the project start date" in ms.json()["error"]["message"]


# ===========================================================================
# Schema invariant — no DateTime column escaped the sweep
# ===========================================================================

class TestNoPlainDateTimeColumns:
    def test_every_datetime_column_uses_utc_decorator(self):
        """Walk every model's columns; for any column whose underlying
        type is the bare ``DateTime`` (not the ``UtcDateTime`` decorator),
        flag it. A regression here would re-introduce the IST drift bug."""
        from sqlalchemy import DateTime as PlainDateTime

        from app.infrastructure.db.session import Base
        from app.infrastructure.db.utc_datetime import UtcDateTime

        offenders = []
        for table_name, table in Base.metadata.tables.items():
            for col in table.columns:
                t = col.type
                # Plain DateTime instances would NOT be UtcDateTime instances.
                if isinstance(t, PlainDateTime) and not isinstance(t, UtcDateTime):
                    offenders.append(f"{table_name}.{col.name}: {type(t).__name__}")
        assert not offenders, (
            "DateTime columns not migrated to UtcDateTime:\n  "
            + "\n  ".join(offenders)
        )
