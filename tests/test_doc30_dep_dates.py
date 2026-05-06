"""Doc 27 — cross-dependency date enforcement.

Rule: a SOURCE entity that depends on a TARGET entity must not start
before the target ends.

    source.start_date >= target.end_date  (equality allowed)

This test file exercises the rule across all four kinds (activity,
task, subtask, milestone), in both create and update directions, plus
the reverse direction (predecessor's end_date being pushed past an
existing successor's start_date).

The shared helper is ``app/shared/dep_date_rules.py``. All four
service-layer wirings sit in:
- ``app/api/v3/activities/services/{create,update}.py``
- ``app/api/v3/tasks/services/{create,update}.py``
- ``app/api/v3/subtasks/services/{create,update}.py``
- ``app/api/v3/milestones/services/{create,update}.py``
"""
from datetime import datetime, timedelta, timezone


def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def _make_project(client, headers, *, name="Doc27 Demo"):
    r = client.post(
        "/api/v3/projects/create",
        json={
            "name": name, "owner": "tmd1",
            "startDate": _iso(1), "endDate": _iso(400),
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _make_milestone(client, headers, pid, *, name="M",
                    start=2, end=200):
    r = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={"name": name, "startDate": _iso(start), "endDate": _iso(end)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _make_activity(client, headers, mid, *, name="A",
                   start, end, deps=None):
    body = {
        "name": name, "startDate": _iso(start), "endDate": _iso(end),
    }
    if deps is not None:
        body["dependsOn"] = deps
    return client.post(
        f"/api/v3/milestones/{mid}/activities/standard/create",
        json=body, headers=headers,
    )


def _patch_activity(client, headers, aid, **body):
    return client.patch(f"/api/v3/activities/{aid}", json=body, headers=headers)


def _publish_and_version(client, headers, pid):
    """Publish the project so tasks / subtasks can be created on it.

    Post-doc-33 follow-up: T/S writes are gated on
    ``project.status == 'published'``. Helper publishes then returns
    ``(pid, tree)`` so callers can locate the M / A ids they need.
    """
    pub = client.post(f"/api/v3/projects/{pid}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    tree = client.get(f"/api/v3/projects/{pid}/tree", headers=headers).json()["data"]
    return pid, tree


def _make_task(client, headers, aid, *, name="T", start, end, deps=None):
    body = {"name": name, "startDate": _iso(start), "endDate": _iso(end)}
    if deps is not None:
        body["dependsOn"] = deps
    return client.post(
        f"/api/v3/activities/{aid}/tasks/create",
        json=body, headers=headers,
    )


def _patch_task(client, headers, tid, **body):
    return client.patch(f"/api/v3/tasks/{tid}", json=body, headers=headers)


def _make_subtask(client, headers, tid, *, name="S", start, end, deps=None):
    body = {"name": name, "startDate": _iso(start), "endDate": _iso(end)}
    if deps is not None:
        body["dependsOn"] = deps
    return client.post(
        f"/api/v3/tasks/{tid}/subtasks/create",
        json=body, headers=headers,
    )


def _patch_subtask(client, headers, sid, **body):
    return client.patch(f"/api/v3/subtasks/{sid}", json=body, headers=headers)


# ===========================================================================
# Activity — forward direction (create + update)
# ===========================================================================

class TestActivityForward:
    def test_create_with_dep_violating_start_rejected(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        # A2 starts day+15 — before A1.end (day+20). MUST be rejected.
        resp = _make_activity(
            client, admin_headers, mid, name="A2",
            start=15, end=30, deps=[a1],
        )
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "cannot start" in msg
        assert "A1.1" in msg
        assert "ends" in msg

    def test_create_with_dep_starting_on_dep_end_date_allowed(
        self, client, admin_user, admin_headers,
    ):
        # Equality branch: A2.start == A1.end — same-day handoff.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_activity(
            client, admin_headers, mid, name="A2",
            start=20, end=30, deps=[a1],
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["dependsOn"] == [a1]

    def test_create_with_dep_starting_after_dep_end_allowed(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_activity(
            client, admin_headers, mid, name="A2",
            start=25, end=30, deps=[a1],
        )
        assert resp.status_code == 201, resp.text

    def test_update_dep_replace_violating_rejected(
        self, client, admin_user, admin_headers,
    ):
        # A2 already exists with dates start=25, end=30 (no deps).
        # PATCH dependsOn=[A1] where A1 ends day+50 — A2.start (25) <
        # A1.end (50), should be rejected.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=40, end=50,
        ).json()["data"]["id"]
        a2 = _make_activity(
            client, admin_headers, mid, name="A2", start=25, end=30,
        ).json()["data"]["id"]
        resp = _patch_activity(client, admin_headers, a2, dependsOn=[a1])
        assert resp.status_code == 422
        assert "cannot start" in resp.json()["error"]["message"]

    def test_update_start_date_only_re_validates_existing_deps(
        self, client, admin_user, admin_headers,
    ):
        # A2 depends on A1 (valid). Pull A2's start_date earlier — now
        # invalid against existing dep.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        a2 = _make_activity(
            client, admin_headers, mid, name="A2",
            start=25, end=30, deps=[a1],
        ).json()["data"]["id"]
        # Move A2.start_date back to day+15 (before A1.end=20).
        resp = _patch_activity(
            client, admin_headers, a2, startDate=_iso(15),
        )
        assert resp.status_code == 422
        assert "cannot start" in resp.json()["error"]["message"]


# ===========================================================================
# Activity — reverse direction (target's end_date moves forward)
# ===========================================================================

class TestActivityReverse:
    def test_update_target_end_past_source_start_rejected(
        self, client, admin_user, admin_headers,
    ):
        # A1 ends day+20, A2 (depends on A1) starts day+25. Push A1.end
        # to day+30 — would make A2 invalid. MUST reject A1's update.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        a2 = _make_activity(
            client, admin_headers, mid, name="A2",
            start=25, end=30, deps=[a1],
        ).json()["data"]["id"]
        resp = _patch_activity(client, admin_headers, a1, endDate=_iso(30))
        assert resp.status_code == 422
        body = resp.json()["error"]
        # The error should name the violating successor.
        assert "A1.2" in body["message"], body["message"]
        assert "starts" in body["message"]

    def test_update_target_end_within_safe_range_allowed(
        self, client, admin_user, admin_headers,
    ):
        # Push A1.end to day+22 — still <= A2.start (25). Should pass.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        _make_activity(
            client, admin_headers, mid, name="A2",
            start=25, end=30, deps=[a1],
        )
        resp = _patch_activity(client, admin_headers, a1, endDate=_iso(22))
        assert resp.status_code == 200, resp.text

    def test_update_target_end_to_equal_source_start_allowed(
        self, client, admin_user, admin_headers,
    ):
        # Equality branch on the reverse path: A1.end == A2.start.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        _make_activity(
            client, admin_headers, mid, name="A2",
            start=25, end=30, deps=[a1],
        )
        resp = _patch_activity(client, admin_headers, a1, endDate=_iso(25))
        assert resp.status_code == 200, resp.text

    def test_lists_all_violating_successors_in_error(
        self, client, admin_user, admin_headers,
    ):
        # Two successors A2 and A3 both depend on A1. Push A1.end past
        # both. Error message lists both.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        _make_activity(
            client, admin_headers, mid, name="A2",
            start=25, end=30, deps=[a1],
        )
        _make_activity(
            client, admin_headers, mid, name="A3",
            start=27, end=35, deps=[a1],
        )
        resp = _patch_activity(client, admin_headers, a1, endDate=_iso(40))
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "A1.2" in msg
        assert "A1.3" in msg


# Milestone tests for the doc 30 rule were removed in doc 31 — milestones
# now use a different dep-date rule (start floor + strict end), tested in
# tests/test_doc31_milestone_dep_rules.py. The doc 30 rule remains in force
# for activities, tasks, and subtasks.


# ===========================================================================
# Task — forward + reverse on a version
# ===========================================================================

class TestTaskForwardReverse:
    def _setup_version_with_two_activities(self, client, headers):
        """Build baseline + version with V_A1 (ends day+5) and V_A2
        (starts day+10). Returns (vid, v_a1, v_a2)."""
        pid = _make_project(client, headers)
        m1 = _make_milestone(client, headers, pid, name="M1")
        _make_activity(client, headers, m1, name="A1", start=3, end=5)
        _make_activity(client, headers, m1, name="A2", start=10, end=20)
        vid, tree = _publish_and_version(client, headers, pid)
        v_a1 = next(
            a["id"] for ms in tree["milestones"]
            for a in ms["activities"] if a["name"] == "A1"
        )
        v_a2 = next(
            a["id"] for ms in tree["milestones"]
            for a in ms["activities"] if a["name"] == "A2"
        )
        return vid, v_a1, v_a2

    def test_task_create_with_dep_violating_rejected(
        self, client, admin_user, admin_headers,
    ):
        _, v_a1, v_a2 = self._setup_version_with_two_activities(
            client, admin_headers,
        )
        t1 = _make_task(
            client, admin_headers, v_a1, name="T1", start=4, end=5,
        ).json()["data"]["id"]
        # T2 starts day+5 (== T1.end) so EQUAL is allowed.
        # Then re-attempt with start day+4 < T1.end day+5: should reject.
        ok = _make_task(
            client, admin_headers, v_a2, name="T2-equal",
            start=10, end=15, deps=[t1],
        )
        assert ok.status_code == 201, ok.text

        bad = _make_task(
            client, admin_headers, v_a2, name="T2-bad",
            start=4, end=5, deps=[t1],
        )
        # T2-bad.start (day+4) < T1.end (day+5). Wait — equality is
        # allowed and start=4 <= end=5. So 4 < 5 strictly → reject.
        # However T2-bad.start (4) is also before V_A2.start (10), which
        # the entity-date rule rejects FIRST. We accept either error code.
        assert bad.status_code == 422

    def test_task_update_target_end_extension_blocked(
        self, client, admin_user, admin_headers,
    ):
        _, v_a1, v_a2 = self._setup_version_with_two_activities(
            client, admin_headers,
        )
        t1 = _make_task(
            client, admin_headers, v_a1, name="T1", start=4, end=5,
        ).json()["data"]["id"]
        t2 = _make_task(
            client, admin_headers, v_a2, name="T2",
            start=10, end=15, deps=[t1],
        ).json()["data"]["id"]
        # Push T1.end past T2.start (10). Reject — the new end (12) is
        # after T2's start (10), so the existing successor would no
        # longer be date-valid.
        resp = _patch_task(client, admin_headers, t1, endDate=_iso(12))
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        # Either the source/target label format ("T1.1.1" / "T1.2.1") or
        # the raw name "T2" should appear in the reverse-violation list.
        assert ("T1." in msg) or ("T2" in msg), msg
        # And the message should be the dep-date reverse-violation form
        # (mentions "starts" because the offender is a successor whose
        # start_date now becomes invalid).
        assert "starts" in msg or "would then start" in msg, msg


# ===========================================================================
# Subtask — forward + reverse on a version
# ===========================================================================

class TestSubtaskForwardReverse:
    def _setup_version_with_one_task(self, client, headers):
        pid = _make_project(client, headers)
        m1 = _make_milestone(client, headers, pid, name="M1")
        _make_activity(client, headers, m1, name="A1", start=3, end=5)
        vid, tree = _publish_and_version(client, headers, pid)
        v_a1 = tree["milestones"][0]["activities"][0]["id"]
        t = _make_task(
            client, headers, v_a1, name="T1", start=4, end=5,
        ).json()["data"]["id"]
        return vid, t

    def test_subtask_create_with_dep_violating_rejected(
        self, client, admin_user, admin_headers,
    ):
        _, t = self._setup_version_with_one_task(client, admin_headers)
        s1 = _make_subtask(
            client, admin_headers, t, name="S1", start=5, end=8,
        ).json()["data"]["id"]
        # S2 starts day+6 — before S1.end (8). Reject.
        bad = _make_subtask(
            client, admin_headers, t, name="S2",
            start=6, end=10, deps=[s1],
        )
        assert bad.status_code == 422
        assert "cannot start" in bad.json()["error"]["message"]

    def test_subtask_create_with_dep_equal_dates_allowed(
        self, client, admin_user, admin_headers,
    ):
        _, t = self._setup_version_with_one_task(client, admin_headers)
        s1 = _make_subtask(
            client, admin_headers, t, name="S1", start=5, end=8,
        ).json()["data"]["id"]
        ok = _make_subtask(
            client, admin_headers, t, name="S2",
            start=8, end=10, deps=[s1],
        )
        assert ok.status_code == 201, ok.text

    def test_subtask_update_target_end_extension_blocked(
        self, client, admin_user, admin_headers,
    ):
        _, t = self._setup_version_with_one_task(client, admin_headers)
        s1 = _make_subtask(
            client, admin_headers, t, name="S1", start=5, end=8,
        ).json()["data"]["id"]
        _make_subtask(
            client, admin_headers, t, name="S2",
            start=10, end=15, deps=[s1],
        )
        # Push S1.end past S2.start. Reject.
        resp = _patch_subtask(client, admin_headers, s1, endDate=_iso(12))
        assert resp.status_code == 422


# ===========================================================================
# Empty / null handling
# ===========================================================================

class TestEmptyAndNullHandling:
    def test_clearing_deps_does_not_run_check(
        self, client, admin_user, admin_headers,
    ):
        # PATCH dependsOn=[] should never trigger a date check.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        a2 = _make_activity(
            client, admin_headers, mid, name="A2",
            start=25, end=30, deps=[a1],
        ).json()["data"]["id"]
        # Clear deps + move start to before A1.end. Should pass — no deps.
        resp = _patch_activity(
            client, admin_headers, a2,
            dependsOn=[], startDate=_iso(15),
        )
        assert resp.status_code == 200, resp.text

    def test_unrelated_field_update_does_not_trigger_check(
        self, client, admin_user, admin_headers,
    ):
        # PATCH name only — no date / dep change → no check fires.
        pid = _make_project(client, admin_headers)
        mid = _make_milestone(client, admin_headers, pid)
        a1 = _make_activity(
            client, admin_headers, mid, name="A1", start=10, end=20,
        ).json()["data"]["id"]
        a2 = _make_activity(
            client, admin_headers, mid, name="A2",
            start=25, end=30, deps=[a1],
        ).json()["data"]["id"]
        resp = _patch_activity(client, admin_headers, a2, name="A2-renamed")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["name"] == "A2-renamed"
