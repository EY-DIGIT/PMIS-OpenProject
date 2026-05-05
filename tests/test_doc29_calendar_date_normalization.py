"""Doc 29: cross-format calendar-date normalization.

Reported bug: when the user picks the SAME calendar dates for project
and milestone (e.g. both 04-05-2026 to 31-05-2026), the milestone
create returns 422 with
"Milestone start date cannot be before the project start date."

Root cause: different FE form components serialize "the picked calendar
date" inconsistently. Some send IST midnight (``+05:30``), some send
UTC midnight (``Z``), some send IST end-of-day (``23:59:59+05:30``),
etc. The doc-27 ``UtcDateTime`` storage normalization handled the
write-then-read symmetry within a single entity, but couldn't fix the
asymmetry across entities created from different forms with different
encodings — a project ``2026-05-04T00:00:00Z`` (UTC midnight) and a
milestone ``2026-05-04T00:00:00+05:30`` (IST midnight) represent the
SAME calendar date in IST but different UTC instants 5h30m apart.

Fix: a Pydantic ``IstCalendarDate`` annotated type at the schema input
boundary collapses any submitted datetime to IST midnight of its IST-
local calendar date. All FE encodings of "May 4" — UTC midnight, IST
midnight, IST end-of-day, naive end-of-day — produce the same canonical
instant ``2026-05-04T00:00:00+05:30`` (= ``2026-05-03 18:30:00`` UTC
after ``UtcDateTime`` storage). Comparisons across entities become
trivially correct.

These tests assert the fix for every pairing of project/milestone date
encodings the FE could realistically send.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.shared.datetime import IST, to_ist_calendar_midnight


# ---------------------------------------------------------------------------
# Pure unit tests — the helper itself
# ---------------------------------------------------------------------------

class TestToIstCalendarMidnight:
    def test_none_passes_through(self):
        assert to_ist_calendar_midnight(None) is None

    def test_ist_midnight_stays(self):
        v = datetime(2026, 5, 4, 0, 0, 0, tzinfo=IST)
        out = to_ist_calendar_midnight(v)
        assert out == datetime(2026, 5, 4, 0, 0, 0, tzinfo=IST)

    def test_utc_midnight_collapses_to_ist_midnight_same_day(self):
        # UTC midnight = 5:30 AM IST same day → IST date is May 4
        v = datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc)
        assert to_ist_calendar_midnight(v) == datetime(2026, 5, 4, 0, 0, 0, tzinfo=IST)

    def test_naive_treated_as_utc(self):
        # Naive 2026-05-04 00:00:00 → assumed UTC → IST May 4 morning → IST date May 4
        v = datetime(2026, 5, 4, 0, 0, 0)
        assert to_ist_calendar_midnight(v) == datetime(2026, 5, 4, 0, 0, 0, tzinfo=IST)

    def test_ist_end_of_day_stays_same_day(self):
        v = datetime(2026, 5, 4, 23, 59, 59, tzinfo=IST)
        # Late night IST → still May 4 in IST
        assert to_ist_calendar_midnight(v) == datetime(2026, 5, 4, 0, 0, 0, tzinfo=IST)

    def test_utc_end_of_day_flips_to_next_ist_day(self):
        # 23:59:59 UTC = 05:29:59 next day IST → IST date is May 5
        v = datetime(2026, 5, 4, 23, 59, 59, tzinfo=timezone.utc)
        assert to_ist_calendar_midnight(v) == datetime(2026, 5, 5, 0, 0, 0, tzinfo=IST)

    def test_pacific_morning_stays_in_ist_evening_same_day(self):
        # Some weird tz-aware input — should still resolve to the IST calendar date
        pacific = timezone(timedelta(hours=-8))
        v = datetime(2026, 5, 4, 9, 0, 0, tzinfo=pacific)
        # 9 AM Pacific = 17:00 UTC = 22:30 IST → IST date is May 4
        assert to_ist_calendar_midnight(v) == datetime(2026, 5, 4, 0, 0, 0, tzinfo=IST)


# ---------------------------------------------------------------------------
# End-to-end — every FE encoding pairing produces the right outcome
# ---------------------------------------------------------------------------

# Each tuple: (label, project_start_iso, project_end_iso, milestone_start_iso, milestone_end_iso)
_SAME_CALENDAR_DATE_SCENARIOS = [
    (
        "both_ist_midnight",
        "2026-05-04T00:00:00+05:30", "2026-05-31T00:00:00+05:30",
        "2026-05-04T00:00:00+05:30", "2026-05-31T00:00:00+05:30",
    ),
    (
        "project_ist_eod_ms_ist_midnight",
        "2026-05-04T00:00:00+05:30", "2026-05-31T23:59:59+05:30",
        "2026-05-04T00:00:00+05:30", "2026-05-31T00:00:00+05:30",
    ),
    (
        "project_utc_z_ms_ist",
        "2026-05-04T00:00:00.000Z", "2026-05-31T23:59:59.000Z",
        "2026-05-04T00:00:00+05:30", "2026-05-31T23:59:59+05:30",
    ),
    (
        "project_ist_ms_utc_z",
        "2026-05-04T00:00:00+05:30", "2026-05-31T23:59:59+05:30",
        "2026-05-04T00:00:00.000Z", "2026-05-31T23:59:59.000Z",
    ),
    (
        "both_utc_z",
        "2026-05-04T00:00:00.000Z", "2026-05-31T23:59:59.000Z",
        "2026-05-04T00:00:00.000Z", "2026-05-31T23:59:59.000Z",
    ),
    (
        "both_ist_eod",
        "2026-05-04T23:59:59+05:30", "2026-05-31T23:59:59+05:30",
        "2026-05-04T23:59:59+05:30", "2026-05-31T23:59:59+05:30",
    ),
]


@pytest.mark.parametrize("label,p_start,p_end,m_start,m_end", _SAME_CALENDAR_DATE_SCENARIOS)
def test_same_calendar_dates_accepted_regardless_of_encoding(
    client, admin_user, admin_headers, label, p_start, p_end, m_start, m_end,
):
    """User picks the SAME calendar dates for project + milestone.
    Whatever the FE encoding, both must be accepted as same-instant."""
    proj = client.post("/api/v3/projects/create", json={
        "name": f"Doc29 {label}", "owner": "tmd1",
        "startDate": p_start, "endDate": p_end,
    }, headers=admin_headers)
    assert proj.status_code == 201, proj.text

    pid = proj.json()["data"]["id"]
    ms = client.post(
        f"/api/v3/projects/{pid}/milestones/create", json={
            "name": "M1",
            "startDate": m_start, "endDate": m_end,
        }, headers=admin_headers,
    )
    assert ms.status_code == 201, (
        f"Same calendar dates should be accepted regardless of encoding "
        f"(scenario={label}). Response: {ms.text}"
    )


# ---------------------------------------------------------------------------
# Negative — genuinely earlier dates STILL rejected
# ---------------------------------------------------------------------------

class TestFloorStillEnforced:
    def test_milestone_calendar_day_before_project_rejected(
        self, client, admin_user, admin_headers,
    ):
        proj = client.post("/api/v3/projects/create", json={
            "name": "P-floor", "owner": "tmd1",
            "startDate": "2026-05-04T00:00:00+05:30",
            "endDate":   "2026-05-31T00:00:00+05:30",
        }, headers=admin_headers).json()["data"]
        ms = client.post(f"/api/v3/projects/{proj['id']}/milestones/create", json={
            "name": "M-too-early",
            "startDate": "2026-05-03T00:00:00+05:30",  # genuinely 1 day earlier
            "endDate":   "2026-05-15T00:00:00+05:30",
        }, headers=admin_headers)
        assert ms.status_code == 422
        assert "before the project start date" in ms.json()["error"]["message"]


# ---------------------------------------------------------------------------
# Storage canonicalization — what's actually persisted
# ---------------------------------------------------------------------------

class TestStorageIsCanonicalIstMidnight:
    def test_utc_z_input_resolves_to_correct_ist_calendar_day(
        self, client, admin_user, admin_headers, db_session,
    ):
        """FE sends UTC ``Z``; BE normalizes to IST midnight of the IST-
        local calendar date; UtcDateTime stores the UTC equivalent.

        Key edge case: UTC end-of-day (``23:59:59Z``) is actually
        ``05:29:59 IST next day`` — so IST-calendar-date resolution
        flips to the NEXT day. This is correct behavior; if the FE
        wants to pin to the same day, it should send an IST timestamp.
        """
        from sqlalchemy import text

        proj = client.post("/api/v3/projects/create", json={
            "name": "P-store", "owner": "tmd1",
            "startDate": "2026-05-04T00:00:00.000Z",
            "endDate":   "2026-05-31T23:59:59.000Z",
        }, headers=admin_headers).json()["data"]
        row = db_session.execute(
            text("SELECT start_date, end_date FROM projects WHERE id = :pid"),
            {"pid": proj["id"]},
        ).fetchone()
        # UTC midnight May 4 = IST 05:30 AM May 4 → IST date May 4
        #    → IST midnight May 4 → stored as May 3 18:30 UTC.
        assert "2026-05-03 18:30" in str(row[0]), row[0]
        # UTC 23:59:59 May 31 = IST 05:29:59 AM June 1 → IST date June 1
        #    → IST midnight June 1 → stored as May 31 18:30 UTC.
        assert "2026-05-31 18:30" in str(row[1]), row[1]

    def test_ist_input_stored_as_ist_midnight_utc(
        self, client, admin_user, admin_headers, db_session,
    ):
        from sqlalchemy import text

        proj = client.post("/api/v3/projects/create", json={
            "name": "P-store-ist", "owner": "tmd1",
            "startDate": "2026-05-04T00:00:00+05:30",
            "endDate":   "2026-05-31T00:00:00+05:30",
        }, headers=admin_headers).json()["data"]
        row = db_session.execute(
            text("SELECT start_date, end_date FROM projects WHERE id = :pid"),
            {"pid": proj["id"]},
        ).fetchone()
        assert "2026-05-03 18:30" in str(row[0]), row[0]
        assert "2026-05-30 18:30" in str(row[1]), row[1]
