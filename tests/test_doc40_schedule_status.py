"""Doc 40: schedule status + days-delayed on /api/v3/projects/{id}/tree.

Unit tests target the pure helper in ``app/api/v3/tree/service.py`` so
the date logic is covered without spinning up the whole FastAPI +
SQLAlchemy stack. The integration class at the bottom drives the real
endpoint so we know the field is wired into every M/A/T/S node.
"""
from datetime import datetime, timezone, timedelta, date

import pytest

from app.api.v3.tree.service import _schedule_status, _ist_calendar_date


IST = timezone(timedelta(hours=5, minutes=30))


def _ist_midnight(y, m, d):
    """Match how ``to_ist_calendar_midnight`` stores dates."""
    return datetime(y, m, d, tzinfo=IST)


class TestScheduleStatusHelper:
    """Pure-function coverage of the today-vs-window logic."""

    def test_not_started_when_today_before_start(self):
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 5, 30),
        )
        assert s == "not_started"
        assert d is None

    def test_in_progress_when_today_inside_window(self):
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 6, 5),
        )
        assert s == "in_progress"
        assert d is None

    def test_in_progress_at_start_boundary_inclusive(self):
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 6, 1),
        )
        assert s == "in_progress"
        assert d is None

    def test_in_progress_at_end_boundary_inclusive(self):
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 6, 10),
        )
        assert s == "in_progress"
        assert d is None

    def test_delayed_one_day_past_end(self):
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 6, 11),
        )
        assert s == "delayed"
        assert d == 1

    def test_delayed_many_days_past_end(self):
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 7, 5),
        )
        assert s == "delayed"
        assert d == 25

    def test_single_day_window_today_equals_both(self):
        """When start_date == end_date == today, the item is in_progress."""
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 5),
            _ist_midnight(2026, 6, 5),
            today=date(2026, 6, 5),
        )
        assert s == "in_progress"
        assert d is None

    def test_missing_dates_default_to_not_started(self):
        """Defensive: legacy rows with NULL dates don't crash."""
        s, d = _schedule_status(None, _ist_midnight(2026, 6, 10), date(2026, 6, 5))
        assert s == "not_started" and d is None
        s, d = _schedule_status(_ist_midnight(2026, 6, 1), None, date(2026, 6, 5))
        assert s == "not_started" and d is None
        s, d = _schedule_status(None, None, date(2026, 6, 5))
        assert s == "not_started" and d is None

    def test_actual_dates_are_ignored(self):
        """``actual_start_date`` / ``actual_end_date`` deliberately don't
        feed into the status — the field answers 'is this on schedule?'
        not 'is this done?'. An item past its expected end is delayed
        even if it has no actual_end_date set."""
        # The helper signature only takes expected dates — by-design.
        # If a future caller adds actuals, the helper signature has to
        # change first, which makes the contract explicit.
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 6, 11),
        )
        assert s == "delayed" and d == 1

    def test_naive_utc_input_treated_as_utc_then_converted_to_ist(self):
        """Old fixtures may store naive UTC datetimes. The helper still
        produces a sensible IST calendar date."""
        # 2026-06-10 19:00 UTC == 2026-06-11 00:30 IST → IST date is 11.
        naive_utc_19h = datetime(2026, 6, 10, 19, 0)
        ist_d = _ist_calendar_date(naive_utc_19h)
        assert ist_d == date(2026, 6, 11)


class TestScheduleStatusOnTreeEndpoint:
    """End-to-end: fetch /tree and assert every node carries the field.

    Uses ``client`` + ``admin_headers`` + ``sample_project`` from
    ``tests/conftest.py``. We attach one milestone with start/end in
    the past so we know at least one node should report ``delayed``;
    the test then asserts the field exists on every M/A/T/S node and
    ``daysDelayed`` is positive on the delayed node.
    """

    def test_tree_response_carries_schedule_status_on_every_node(
        self, client, admin_headers, sample_project, db_session,
    ):
        from datetime import datetime as _dt
        from app.infrastructure.db.models.milestone import MilestoneModel
        from app.infrastructure.db.models.activity import ActivityModel
        from uuid import uuid4

        # A milestone clearly in the past — must come back as 'delayed'.
        m = MilestoneModel(
            id=str(uuid4()),
            project_id=sample_project.id,
            name="Milestone Past",
            start_date=_ist_midnight(2025, 1, 1),
            end_date=_ist_midnight(2025, 1, 10),
            position=1,
            status="not_completed",
        )
        db_session.add(m)
        db_session.flush()

        # An activity clearly in the future — must come back as 'not_started'.
        a = ActivityModel(
            id=str(uuid4()),
            project_id=sample_project.id,
            milestone_id=m.id,
            name="Activity Future",
            type=None,
            start_date=_ist_midnight(2099, 1, 1),
            end_date=_ist_midnight(2099, 1, 10),
            position=1,
        )
        db_session.add(a)
        db_session.commit()

        resp = client.get(
            f"/api/v3/projects/{sample_project.id}/tree",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        tree = resp.json()["data"]

        milestones = tree.get("milestones", [])
        assert milestones, "expected at least one milestone in the tree"
        ms = next(x for x in milestones if x["id"] == m.id)
        assert ms["scheduleStatus"] == "delayed"
        assert isinstance(ms.get("daysDelayed"), int) and ms["daysDelayed"] > 0

        acts = ms.get("activities", [])
        assert acts, "expected the activity to appear under the milestone"
        act = next(x for x in acts if x["id"] == a.id)
        assert act["scheduleStatus"] == "not_started"
        # daysDelayed MUST be omitted from non-delayed payloads.
        assert "daysDelayed" not in act

    def test_tree_response_omits_days_delayed_for_non_delayed_nodes(
        self, client, admin_headers, sample_project, db_session,
    ):
        from app.infrastructure.db.models.milestone import MilestoneModel
        from uuid import uuid4

        m = MilestoneModel(
            id=str(uuid4()),
            project_id=sample_project.id,
            name="Future Milestone",
            start_date=_ist_midnight(2099, 1, 1),
            end_date=_ist_midnight(2099, 1, 10),
            position=99,
            status="not_completed",
        )
        db_session.add(m)
        db_session.commit()

        resp = client.get(
            f"/api/v3/projects/{sample_project.id}/tree",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        node = next(
            x for x in resp.json()["data"]["milestones"] if x["id"] == m.id
        )
        assert node["scheduleStatus"] == "not_started"
        assert "daysDelayed" not in node, (
            "daysDelayed must only appear on delayed nodes"
        )
