"""Doc 31 — milestone-specific dependency rules.

For milestones (and ONLY milestones — activities/tasks/subtasks keep
the doc 30 rule), the dep-date rule is split into a start-floor and a
strict-end requirement:

    source.start_date >= target.start_date    (equality allowed)
    source.end_date   >  target.end_date      (strict — equality REJECTED)

Plus a status-completion gate that mirrors what activities have:

    A milestone cannot be marked 'completed' while any of its
    dependency targets is not 'completed'.

The dep-date helpers live in ``app/shared/dep_date_rules.py``
(milestone-specific functions: ``collect_milestone_*_violations`` and
``raise_milestone_*_if_violations``). The status gate sits in
``milestones/services/update.py`` as ``_gate_milestone_status_against_deps``.
"""
from datetime import datetime, timedelta, timezone


def _iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _make_project(client, headers, *, name="Doc31 Demo"):
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


def _make_milestone(client, headers, pid, *, name, start, end, deps=None):
    body = {
        "name": name, "startDate": _iso(start), "endDate": _iso(end),
    }
    if deps is not None:
        body["dependsOn"] = deps
    return client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json=body, headers=headers,
    )


def _patch_milestone(client, headers, mid, **body):
    return client.patch(f"/api/v3/milestones/{mid}", json=body, headers=headers)


# ===========================================================================
# Forward direction — start floor (rule 2a)
# ===========================================================================

class TestStartFloor:
    def test_source_start_before_target_start_rejected(
        self, client, admin_user, admin_headers,
    ):
        # M1 starts day+10. M2 (depends on M1) tries to start day+5 — earlier
        # than the target's start. Rule 2a rejects.
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=5, end=30, deps=[m1],
        )
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "must start on or after" in msg, msg
        assert "M1" in msg

    def test_source_start_equal_to_target_start_allowed(
        self, client, admin_user, admin_headers,
    ):
        # Equality is allowed — M2.start == M1.start.
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=10, end=30, deps=[m1],
        )
        assert resp.status_code == 201, resp.text

    def test_source_start_after_target_start_allowed(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=15, end=30, deps=[m1],
        )
        assert resp.status_code == 201, resp.text

    def test_overlap_in_time_allowed(
        self, client, admin_user, admin_headers,
    ):
        # Doc 31 is meant to allow milestones to overlap. M2 starts before
        # M1 ends but starts after M1 starts — should pass.
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=50,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=20, end=60, deps=[m1],
        )
        assert resp.status_code == 201, resp.text


# ===========================================================================
# Forward direction — strict end (rule 2b)
# ===========================================================================

class TestStrictEnd:
    def test_source_end_equal_to_target_end_rejected(
        self, client, admin_user, admin_headers,
    ):
        # Equality on end_date is REJECTED (strict rule).
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=10, end=20, deps=[m1],
        )
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "must end strictly after" in msg, msg
        assert "M1" in msg

    def test_source_end_before_target_end_rejected(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=50,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=10, end=30, deps=[m1],
        )
        assert resp.status_code == 422
        assert "must end strictly after" in resp.json()["error"]["message"]

    def test_source_end_strictly_after_target_end_allowed(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=10, end=21, deps=[m1],
        )
        assert resp.status_code == 201, resp.text


# ===========================================================================
# Both rules combined — error message lists every offender
# ===========================================================================

class TestCombinedErrors:
    def test_both_rules_violated_listed_in_one_message(
        self, client, admin_user, admin_headers,
    ):
        # M2 violates BOTH the start floor AND the strict end. The error
        # should mention both rules in a single response.
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=5, end=15, deps=[m1],
        )
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "must start on or after" in msg
        assert "must end strictly after" in msg

    def test_multiple_targets_listed(
        self, client, admin_user, admin_headers,
    ):
        # M3 depends on M1 + M2; both violate the start floor. Both names
        # appear in the message.
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        m2 = _make_milestone(
            client, admin_headers, pid, name="M2", start=10, end=20,
        ).json()["data"]["id"]
        resp = _make_milestone(
            client, admin_headers, pid, name="M3",
            start=5, end=30, deps=[m1, m2],
        )
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "M1" in msg
        assert "M2" in msg


# ===========================================================================
# Update path — date moves trigger forward + reverse re-validation
# ===========================================================================

class TestUpdateRevalidation:
    def test_patch_source_start_back_breaks_existing_dep(
        self, client, admin_user, admin_headers,
    ):
        # M2 depends on M1 validly. Pull M2.start back before M1.start —
        # forward re-check fires.
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        m2 = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=15, end=30, deps=[m1],
        ).json()["data"]["id"]
        resp = _patch_milestone(
            client, admin_headers, m2, startDate=_iso(5),
        )
        assert resp.status_code == 422
        assert "must start on or after" in resp.json()["error"]["message"]

    def test_patch_source_end_to_equal_target_end_rejected(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        m2 = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=10, end=30, deps=[m1],
        ).json()["data"]["id"]
        # Pull M2.end back to equal M1.end — strict-end rule fires.
        resp = _patch_milestone(
            client, admin_headers, m2, endDate=_iso(20),
        )
        assert resp.status_code == 422
        assert "must end strictly after" in resp.json()["error"]["message"]

    def test_patch_target_start_forward_breaks_existing_source(
        self, client, admin_user, admin_headers,
    ):
        # M2 depends on M1. Push M1.start forward past M2.start — reverse
        # check fires (M2 would no longer satisfy start floor).
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        _make_milestone(
            client, admin_headers, pid, name="M2",
            start=15, end=30, deps=[m1],
        )
        resp = _patch_milestone(
            client, admin_headers, m1, startDate=_iso(20),
        )
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "would then start before" in msg

    def test_patch_target_end_to_equal_source_end_rejected(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        _make_milestone(
            client, admin_headers, pid, name="M2",
            start=10, end=30, deps=[m1],
        )
        # Push M1.end up to day+30 — equals M2.end. Strict rule fires
        # via the reverse direction.
        resp = _patch_milestone(
            client, admin_headers, m1, endDate=_iso(30),
        )
        assert resp.status_code == 422
        assert "would no longer end strictly after" in resp.json()["error"]["message"]


# ===========================================================================
# Status-completion gate (rule 2c)
# ===========================================================================

class TestStatusGate:
    def test_mark_completed_blocked_when_dep_not_completed(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        m2 = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=10, end=30, deps=[m1],
        ).json()["data"]["id"]
        # M1 still 'not_completed' (default). Try to flip M2 to completed.
        resp = _patch_milestone(client, admin_headers, m2, status="completed")
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "Cannot mark this milestone as completed" in msg
        assert "M1" in msg

    def test_mark_completed_allowed_when_all_deps_completed(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        m2 = _make_milestone(
            client, admin_headers, pid, name="M2",
            start=10, end=30, deps=[m1],
        ).json()["data"]["id"]
        # Mark M1 completed first (no deps → allowed).
        r = _patch_milestone(client, admin_headers, m1, status="completed")
        assert r.status_code == 200, r.text
        # Now M2 can be marked completed.
        resp = _patch_milestone(client, admin_headers, m2, status="completed")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "completed"

    def test_mark_completed_with_no_deps_allowed(
        self, client, admin_user, admin_headers,
    ):
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        resp = _patch_milestone(client, admin_headers, m1, status="completed")
        assert resp.status_code == 200, resp.text

    def test_lists_multiple_blockers(
        self, client, admin_user, admin_headers,
    ):
        # M3 depends on M1 + M2; neither is completed. Both should appear.
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        m2 = _make_milestone(
            client, admin_headers, pid, name="M2", start=10, end=20,
        ).json()["data"]["id"]
        m3 = _make_milestone(
            client, admin_headers, pid, name="M3",
            start=10, end=30, deps=[m1, m2],
        ).json()["data"]["id"]
        resp = _patch_milestone(client, admin_headers, m3, status="completed")
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"]
        assert "M1" in msg
        assert "M2" in msg

    def test_revert_to_not_completed_always_allowed(
        self, client, admin_user, admin_headers,
    ):
        # Marking a milestone NOT completed isn't gated — only the
        # forward direction (-> completed) carries the dep check.
        pid = _make_project(client, admin_headers)
        m1 = _make_milestone(
            client, admin_headers, pid, name="M1", start=10, end=20,
        ).json()["data"]["id"]
        # Mark completed first.
        _patch_milestone(client, admin_headers, m1, status="completed")
        # Then revert. Should pass even if a dependent is currently completed.
        resp = _patch_milestone(client, admin_headers, m1, status="not_completed")
        assert resp.status_code == 200, resp.text
