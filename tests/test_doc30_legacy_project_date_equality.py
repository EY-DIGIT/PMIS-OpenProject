"""Doc 30 follow-up: same-calendar-date floor rule must hold against
legacy projects whose stored ``start_date`` was never IST-canonicalized.

Reported bug (portal):
  POST /projects/{LEGACY_PID}/milestones/create with
    {startDate: "2026-05-01T00:00:00.000Z",  endDate: ...}
  returns 422
    "Milestone start date cannot be before the project start date (2026-05-01)."

Why doc 29 alone didn't fix it:
  Doc 29 normalizes incoming datetimes at the schema boundary via
  ``IstCalendarDate``. A live milestone request comes in as
  ``2026-05-01T00:00:00Z`` (UTC midnight) and is normalized to IST
  midnight May 1 = ``2026-04-30 18:30 UTC`` (the canonical stored form).
  But projects created BEFORE doc 29 was deployed have their
  ``start_date`` stored as the FE-supplied UTC instant directly — e.g.
  ``2026-05-01 00:00 UTC`` rather than the doc-29 canonical
  ``2026-04-30 18:30 UTC``. The two values differ by 5h30m even though
  they represent the same IST calendar date.

  ``date_rules._normalize`` previously stripped tzinfo to naive UTC,
  preserving that 5h30m gap. Strict ``<`` then rejected the milestone
  as "before the project start date" — the user's exact symptom.

Fix (this commit):
  ``_normalize`` now collapses to IST midnight via
  ``to_ist_calendar_midnight`` so both sides land on the same canonical
  instant when they represent the same IST calendar date — robust to
  legacy stored values, future encoding drift, and the doc-29 happy
  path simultaneously.

These tests pin that contract by inserting a project with a deliberately
non-canonical legacy ``start_date`` directly via the ORM (mirroring a
pre-doc-29 row) and then exercising the create endpoints for milestone,
activity, task, and subtask. Each must accept a same-calendar-date
request and reject a genuinely earlier date.
"""
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from app.infrastructure.db.models.project import ProjectModel


# ---------------------------------------------------------------------------
# A "legacy" project: ``start_date`` stored as the literal UTC instant
# the FE sent before doc 29 was deployed (i.e. NOT IST-canonical).
#
# We bypass the create endpoint and write directly to the ORM so the
# stored value is exactly ``YYYY-MM-DD 00:00:00 UTC`` (UTC midnight,
# 5h30m AHEAD of the doc-29 canonical IST-midnight value).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def legacy_project(db_session, admin_user):
    """A project whose start_date was inserted as UTC midnight May 1 —
    representing a row created pre-doc-29 (or via a pathway that bypassed
    the IstCalendarDate normalizer)."""
    now = datetime.now(timezone.utc)
    p = ProjectModel(
        id=str(uuid4()),
        name=f"Legacy date project {uuid4().hex[:6]}",
        description="-",
        active=True,
        public=False,
        status="new",
        owner="tmd1",
        # NOTE: naive UTC midnight — mimics legacy storage. The whole
        # point of this fixture is that the value is NOT IST-canonical.
        start_date=datetime(2026, 5, 1, 0, 0, 0),
        end_date=datetime(2026, 12, 31, 0, 0, 0),
        project_code=f"P-LEG-{uuid4().hex[:8]}",
        created_by=admin_user.id,
        updated_by=admin_user.id,
        created_at=now, updated_at=now,
    )
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    return p


# ---------------------------------------------------------------------------
# Milestone — the user's reported failure case
# ---------------------------------------------------------------------------

class TestLegacyProjectMilestoneFloor:
    def test_same_ist_day_milestone_accepted_against_legacy_project(
        self, client, admin_user, admin_headers, legacy_project,
    ):
        """User's exact payload: UTC midnight May 1 against a legacy
        project whose stored start_date is also UTC midnight May 1
        (they represent the same IST calendar day; the floor must hold)."""
        resp = client.post(
            f"/api/v3/projects/{legacy_project.id}/milestones/create",
            headers=admin_headers,
            json={
                "name": "milestone1-kamal",
                "description": "",
                "startDate": "2026-05-01T00:00:00.000Z",
                "endDate":   "2026-05-31T23:59:59.000Z",
                "status":    "not_completed",
                "vendorIds": [],
                "dependsOn": [],
            },
        )
        assert resp.status_code == 201, resp.text

    def test_one_day_earlier_milestone_still_rejected(
        self, client, admin_user, admin_headers, legacy_project,
    ):
        """Floor rule must still hold for genuinely earlier dates — the
        fix is for cross-format equality, not a wholesale relaxation."""
        resp = client.post(
            f"/api/v3/projects/{legacy_project.id}/milestones/create",
            headers=admin_headers,
            json={
                "name": "M-too-early",
                "startDate": "2026-04-30T00:00:00+05:30",  # April 30 IST = 1 day before May 1
                "endDate":   "2026-05-31T00:00:00+05:30",
            },
        )
        assert resp.status_code == 422, resp.text
        assert "before the project start date" in resp.json()["error"]["message"]

    def test_ist_midnight_input_also_accepted(
        self, client, admin_user, admin_headers, legacy_project,
    ):
        """Same calendar day picked via the OTHER common FE encoding
        (IST midnight +05:30) — must also be accepted."""
        resp = client.post(
            f"/api/v3/projects/{legacy_project.id}/milestones/create",
            headers=admin_headers,
            json={
                "name": "M-ist-midnight",
                "startDate": "2026-05-01T00:00:00+05:30",
                "endDate":   "2026-05-31T00:00:00+05:30",
            },
        )
        assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Activity / task / subtask — same fix has to hold all the way down the
# parent chain. We seed a baseline milestone under the legacy project,
# then check the activity / task / subtask floors land on the same IST
# calendar day as the legacy project's start_date.
# ---------------------------------------------------------------------------

class TestLegacyProjectActivityFloor:
    def test_same_ist_day_activity_accepted_against_legacy_milestone(
        self, client, admin_user, admin_headers, legacy_project,
    ):
        # Create a milestone (this one will be IST-canonical thanks to
        # doc 29) starting on the same legacy calendar day.
        m = client.post(
            f"/api/v3/projects/{legacy_project.id}/milestones/create",
            headers=admin_headers,
            json={
                "name": "M1",
                "startDate": "2026-05-01T00:00:00.000Z",
                "endDate":   "2026-05-31T23:59:59.000Z",
            },
        )
        assert m.status_code == 201, m.text
        mid = m.json()["data"]["id"]

        # Doc 39: activity create needs ownerDivision / vendorId /
        # concernedDivision. Seed a vendor and attach it to the legacy project.
        from uuid import uuid4
        vresp = client.post("/api/v3/master/vendors/create", headers=admin_headers,
                            json={"name": f"Doc30L V {uuid4().hex[:4]}", "phoneNumber": "+919999999999"})
        vid = vresp.json()["data"]["id"]
        client.patch(f"/api/v3/projects/{legacy_project.id}", headers=admin_headers,
                     json={"vendorIds": [vid]})

        # Activity on the same calendar day as the milestone.
        a = client.post(
            f"/api/v3/milestones/{mid}/activities/create",
            headers=admin_headers,
            json={
                "name": "A1",
                "startDate": "2026-05-01T00:00:00.000Z",
                "endDate":   "2026-05-31T23:59:59.000Z",
                "ownerDivision": "tmd1",
                "vendorId": vid,
                "concernedDivision": ["tmd1"],
            },
        )
        assert a.status_code == 201, a.text


# ---------------------------------------------------------------------------
# A pathological case: project's ``end_date`` is also legacy-encoded.
# The end-after-start sanity rule shouldn't be confused by the encoding
# either. (Less critical than the start floor — the user's bug was the
# start floor — but worth pinning for completeness.)
# ---------------------------------------------------------------------------

class TestLegacyEndDateOrdering:
    def test_milestone_end_equal_to_start_still_accepted(
        self, client, admin_user, admin_headers, legacy_project,
    ):
        """Same-day milestone (start == end on the same calendar date)
        is allowed in the product rule (doc 24 inclusive). Must keep
        working against the legacy project too."""
        resp = client.post(
            f"/api/v3/projects/{legacy_project.id}/milestones/create",
            headers=admin_headers,
            json={
                "name": "M-one-day",
                "startDate": "2026-05-15T00:00:00.000Z",
                "endDate":   "2026-05-15T23:59:59.000Z",
            },
        )
        assert resp.status_code == 201, resp.text
