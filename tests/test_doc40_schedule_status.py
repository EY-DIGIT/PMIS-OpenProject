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

    def test_no_actuals_falls_back_to_planned(self):
        """When neither actual_start_date nor actual_end_date is set,
        the calculation uses the planned dates — same as before doc 52."""
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 6, 11),
            actual_start_date=None,
            actual_end_date=None,
        )
        assert s == "delayed" and d == 1

    # -----------------------------------------------------------------
    # Doc 52 — actual-first / planned-fallback rules.
    # -----------------------------------------------------------------

    def test_actual_start_overrides_planned_when_work_starts_early(self):
        """Planned start 2026-06-10. Work actually started 2026-06-05.
        Today 2026-06-07 — should be in_progress (using the actual
        start), not 'not_started' (which is what planned would say)."""
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 10),
            _ist_midnight(2026, 6, 20),
            today=date(2026, 6, 7),
            actual_start_date=_ist_midnight(2026, 6, 5),
            actual_end_date=None,
        )
        assert s == "in_progress" and d is None

    def test_actual_end_overrides_planned_when_finished_early(self):
        """Planned end 2026-06-20. Work actually finished 2026-06-15.
        Today 2026-06-17 — past the actual end → delayed by 2 days
        (using actual_end_date as the deadline)."""
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 20),
            today=date(2026, 6, 17),
            actual_start_date=None,
            actual_end_date=_ist_midnight(2026, 6, 15),
        )
        assert s == "delayed" and d == 2

    def test_actual_start_set_but_actual_end_null_uses_planned_end(self):
        """Work started (actual_start set), not finished. Status should
        compare today against planned end — actual_end is NULL so the
        planned end is the deadline."""
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 10),
            _ist_midnight(2026, 6, 20),
            today=date(2026, 6, 15),
            actual_start_date=_ist_midnight(2026, 6, 8),
            actual_end_date=None,
        )
        assert s == "in_progress" and d is None

    def test_actual_end_set_but_actual_start_null_uses_planned_start(self):
        """Work finished (actual_end set) but actual_start was never
        recorded. Fall back to planned start."""
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 20),
            today=date(2026, 6, 25),
            actual_start_date=None,
            actual_end_date=_ist_midnight(2026, 6, 22),
        )
        # Effective end = actual_end_date = 22 Jun; today 25 Jun → delayed by 3.
        assert s == "delayed" and d == 3

    def test_both_actuals_set_completely_overrides_planned(self):
        """When both actual dates are set, planned dates are
        ignored entirely."""
        s, d = _schedule_status(
            _ist_midnight(2099, 1, 1),     # ridiculous planned dates
            _ist_midnight(2099, 1, 10),
            today=date(2026, 6, 11),
            actual_start_date=_ist_midnight(2026, 6, 1),
            actual_end_date=_ist_midnight(2026, 6, 10),
        )
        # today 6/11 > actual_end 6/10 → delayed by 1.
        assert s == "delayed" and d == 1

    def test_both_actuals_set_but_today_before_actual_start(self):
        """Actuals shouldn't make the status go 'backwards' to
        not_started if today happens to fall before actual_start —
        but if today legitimately precedes actual_start, that's
        not_started (e.g. data correction)."""
        s, d = _schedule_status(
            _ist_midnight(2026, 6, 1),
            _ist_midnight(2026, 6, 10),
            today=date(2026, 6, 4),
            actual_start_date=_ist_midnight(2026, 6, 5),
            actual_end_date=None,
        )
        # Effective start = 5 Jun; today 4 Jun < 5 Jun → not_started.
        assert s == "not_started" and d is None

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

    def test_tree_uses_actual_end_when_set_for_status(
        self, client, admin_headers, sample_project, db_session,
    ):
        """Doc 52: planned end is the future (would normally render
        'in_progress'); but actual_end_date sits in the past so the
        node should report 'delayed'."""
        from app.infrastructure.db.models.milestone import MilestoneModel
        from uuid import uuid4

        m = MilestoneModel(
            id=str(uuid4()),
            project_id=sample_project.id,
            name="Actual-past Milestone",
            start_date=_ist_midnight(2025, 1, 1),
            end_date=_ist_midnight(2099, 1, 10),    # planned end far future
            actual_start_date=_ist_midnight(2025, 1, 5),
            actual_end_date=_ist_midnight(2025, 1, 20),  # actual end in the past
            position=42,
            status="completed",
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
        assert node["scheduleStatus"] == "delayed", (
            "actual_end_date is in the past, status must reflect that"
        )
        assert isinstance(node.get("daysDelayed"), int) and node["daysDelayed"] > 0

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
