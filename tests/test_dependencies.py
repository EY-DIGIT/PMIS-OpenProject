"""Tests for the dependency feature.

Covers:
- Activity ↔ activity deps on a baseline (cross-milestone allowed; self / cycle
  / cross-project / unknown-target / soft-deleted-target rejected; status gate
  for activity 'completed' transitions).
- Task ↔ task deps on a version (hierarchy rule: parent activities must already
  be linked; self / cycle / cross-project / hierarchy violation rejected).
- Subtask ↔ subtask deps on a version (one level deeper, same hierarchy rule).
- Cascade-on-delete: deleting an activity (or task) wipes incoming + outgoing
  edges for it and its subtree.
- Version-clone preserves activity dependencies with id-rewrite.
- Tree response emits ``dependsOn`` on every node, sorted, default [].

The fixtures match the rest of the suite: ``client``, ``admin_headers``,
``db_session`` come from tests/conftest.py.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.infrastructure.db.models.activity_dependency import ActivityDependencyModel
from app.infrastructure.db.models.subtask_dependency import SubtaskDependencyModel
from app.infrastructure.db.models.task_dependency import TaskDependencyModel


def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def _create_project(client, admin_headers, *, name="Dep Demo"):
    resp = client.post(
        "/api/v3/projects/create",
        json={
            "name": name,
            "owner": "tmd1",
            "startDate": _future_iso(1),
            "endDate": _future_iso(400),
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_milestone(
    client, admin_headers, project_id, *,
    name="M", start_offset=2, end_offset=300,
):
    """Default window is intentionally wide so successor activities,
    tasks, and subtasks (which use later offsets per doc 27 dep-date
    enforcement) still fit under it."""
    resp = client.post(
        f"/api/v3/projects/{project_id}/milestones/create",
        json={
            "name": name,
            "startDate": _future_iso(start_offset),
            "endDate": _future_iso(end_offset),
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_activity(
    client, admin_headers, milestone_id, *,
    name="A", depends_on=None, start_offset=30, end_offset=40,
):
    """Default offsets (30/40) sit AFTER the staggered baseline activities
    created by ``_build_baseline_with_two_activities`` (A1 ends day+5,
    A2 ends day+20), so a "third" activity created via this helper can
    safely depend on either baseline activity under the doc 27 rule
    (source.start_date >= target.end_date)."""
    body = {
        "name": name,
        "startDate": _future_iso(start_offset),
        "endDate": _future_iso(end_offset),
    }
    if depends_on is not None:
        body["dependsOn"] = depends_on
    resp = client.post(
        f"/api/v3/milestones/{milestone_id}/activities/standard/create",
        json=body,
        headers=admin_headers,
    )
    return resp


def _publish(client, admin_headers, project_id):
    """Doc 33: tests that used to publish before creating a version no
    longer need to. Publish is now an optional checkpoint. Keep the helper
    callable as a no-op so call sites stay readable."""
    return None


def _create_version(client, admin_headers, baseline_id):
    """Doc 33: versioning was removed. Tests that used to publish + create
    a version now just continue to operate on the original project — T/S
    writes are allowed directly on it. This shim returns the input id."""
    return baseline_id


def _list_activities_in(client, admin_headers, milestone_id):
    resp = client.get(
        f"/api/v3/milestones/{milestone_id}/activities", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["_embedded"]["elements"]


def _build_baseline_with_two_activities(client, admin_headers):
    """Returns (project_id, milestone1_id, milestone2_id, activity1_id, activity2_id).

    Doc 27 staggering: A1 ends day+5 (early); A2 starts day+10 and ends
    day+20. So an A2 → A1 dep is valid (A2.start=10 >= A1.end=5) and a
    third activity created with default offsets (start=30) can depend on
    either."""
    pid = _create_project(client, admin_headers)
    m1 = _create_milestone(client, admin_headers, pid, name="M1")
    m2 = _create_milestone(client, admin_headers, pid, name="M2")
    a1 = _create_activity(
        client, admin_headers, m1, name="A1",
        start_offset=3, end_offset=5,
    )
    assert a1.status_code == 201, a1.text
    a2 = _create_activity(
        client, admin_headers, m2, name="A2",
        start_offset=10, end_offset=20,
    )
    assert a2.status_code == 201, a2.text
    return pid, m1, m2, a1.json()["data"]["id"], a2.json()["data"]["id"]


def _create_task(client, admin_headers, activity_id, *, name="T", depends_on=None,
                 start_offset=50, end_offset=60):
    # ``type`` is no longer accepted on the task create body (doc 15) — the
    # task inherits it from the parent activity. The activities created by
    # _create_activity above are 'standard', so the task is too.
    body = {
        "name": name,
        "startDate": _future_iso(start_offset),
        "endDate": _future_iso(end_offset),
    }
    if depends_on is not None:
        body["dependsOn"] = depends_on
    return client.post(
        f"/api/v3/activities/{activity_id}/tasks/create",
        json=body, headers=admin_headers,
    )


def _create_subtask(client, admin_headers, task_id, *, name="S", depends_on=None,
                    start_offset=70, end_offset=80):
    # ``type`` removed from body (doc 15) — subtask inherits from parent task.
    body = {
        "name": name,
        "startDate": _future_iso(start_offset),
        "endDate": _future_iso(end_offset),
    }
    if depends_on is not None:
        body["dependsOn"] = depends_on
    return client.post(
        f"/api/v3/tasks/{task_id}/subtasks/create",
        json=body, headers=admin_headers,
    )


# ===========================================================================
# Activity-level dependencies
# ===========================================================================

class TestActivityDeps:
    def test_create_activity_with_empty_deps(self, client, admin_user, admin_headers):
        pid, m1, _, _, _ = _build_baseline_with_two_activities(client, admin_headers)
        resp = _create_activity(client, admin_headers, m1, name="X", depends_on=[])
        assert resp.status_code == 201
        assert resp.json()["data"]["dependsOn"] == []

    def test_create_activity_with_valid_dep(self, client, admin_user, admin_headers):
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        # New activity in M2 depends on A1 (cross-milestone).
        resp = _create_activity(client, admin_headers, m2, name="X", depends_on=[a1])
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["dependsOn"] == [a1]

    def test_create_activity_with_unknown_target_rejected(self, client, admin_user, admin_headers):
        _, m1, _, _, _ = _build_baseline_with_two_activities(client, admin_headers)
        bogus = str(uuid4())
        resp = _create_activity(client, admin_headers, m1, name="X", depends_on=[bogus])
        assert resp.status_code == 422
        assert "Unknown" in resp.json()["error"]["message"]

    def test_create_activity_with_target_in_other_project_rejected(
        self, client, admin_user, admin_headers,
    ):
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        # Set up a SECOND project and try to reference A1 from the first.
        pid2 = _create_project(client, admin_headers, name="Other")
        m_other = _create_milestone(client, admin_headers, pid2, name="MO")
        resp = _create_activity(client, admin_headers, m_other, name="Cross", depends_on=[a1])
        assert resp.status_code == 422
        assert a1 in resp.json()["error"]["message"]

    def test_update_activity_self_dep_rejected(self, client, admin_user, admin_headers):
        _, m1, _, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        resp = client.patch(
            f"/api/v3/activities/{a1}",
            json={"dependsOn": [a1]},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "itself" in resp.json()["error"]["message"]

    def test_update_activity_creates_cycle_rejected(
        self, client, admin_user, admin_headers,
    ):
        # For the cycle direction A1 -> A2 to satisfy the doc 27 dep-date
        # rule (A1.start >= A2.end), we need both activities pinned to the
        # SAME date — equality is allowed. Then both directions are
        # date-valid and the cycle rule is what we're actually testing.
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid, name="M1")
        m2 = _create_milestone(client, admin_headers, pid, name="M2")
        a1 = _create_activity(
            client, admin_headers, m1, name="A1",
            start_offset=10, end_offset=10,
        ).json()["data"]["id"]
        a2 = _create_activity(
            client, admin_headers, m2, name="A2",
            start_offset=10, end_offset=10,
        ).json()["data"]["id"]
        # A1 -> A2
        r = client.patch(
            f"/api/v3/activities/{a1}",
            json={"dependsOn": [a2]},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        # A2 -> A1 should be a cycle.
        r2 = client.patch(
            f"/api/v3/activities/{a2}",
            json={"dependsOn": [a1]},
            headers=admin_headers,
        )
        assert r2.status_code == 422
        assert "cycle" in r2.json()["error"]["message"].lower()

    def test_update_activity_replace_clears_then_adds(
        self, client, admin_user, admin_headers,
    ):
        _, _, m2, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        # Create a third activity in M2 with dep on a1, then replace with [a2].
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]
        resp = client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"dependsOn": [a2]},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["dependsOn"] == [a2]
        # Empty list clears.
        resp2 = client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"dependsOn": []},
            headers=admin_headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"]["dependsOn"] == []

    def test_update_omitting_dependsOn_leaves_unchanged(
        self, client, admin_user, admin_headers,
    ):
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]
        # Patch a different field; deps should stay.
        resp = client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"description": "no dep change"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["dependsOn"] == [a1]


# ===========================================================================
# Status-completion gate
# ===========================================================================

class TestActivityStatusGate:
    def test_completing_blocked_when_dep_not_completed(
        self, client, admin_user, admin_headers,
    ):
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]
        # A1 is still 'not_completed' (default). Try to mark AX completed.
        resp = client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"status": "completed"},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "completed" in resp.json()["error"]["message"].lower()

    def test_completing_allowed_when_all_deps_completed(
        self, client, admin_user, admin_headers,
    ):
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        # Mark A1 completed first (it has no deps -> allowed).
        r = client.patch(
            f"/api/v3/activities/{a1}",
            json={"status": "completed"},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        # Now AX (depends on A1) can also be completed.
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]
        resp = client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"status": "completed"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "completed"

    def test_completing_with_no_deps_allowed(self, client, admin_user, admin_headers):
        _, m1, _, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        resp = client.patch(
            f"/api/v3/activities/{a1}",
            json={"status": "completed"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text


# ===========================================================================
# Cascade-on-delete (silent drop incoming + outgoing edges)
# ===========================================================================

class TestActivityDepsCascadeOnDelete:
    def test_deleting_target_with_external_dep_is_blocked(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Doc 34: deleting a target that has an EXTERNAL dependent
        (a source outside the delete subtree) is refused with 422
        + ``dependency_block``. Previously the dep edge was silently
        soft-deleted; that behaviour was deemed too easy to footgun
        users who'd lose their declared dependencies without warning."""
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]

        # Sanity: one LIVE edge before delete.
        live_before = db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.target_activity_id == a1,
            ActivityDependencyModel.deleted_at.is_(None),
        ).count()
        assert live_before == 1

        # Doc 34: delete refused — AX (in M2) is external to A1's
        # subtree but depends on A1.
        resp = client.delete(f"/api/v3/activities/{a1}", headers=admin_headers)
        assert resp.status_code == 422, resp.text
        details = resp.json()["error"]["_embedded"]["details"]
        assert details["errorIdentifier"] == "dependency_block"
        # A1 still alive.
        live_a1 = db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.target_activity_id == a1,
            ActivityDependencyModel.deleted_at.is_(None),
        ).count()
        assert live_a1 == 1, "edge must still be live (delete refused)"

        # Removing the dep first unblocks the delete and the edge gets
        # soft-deleted by the dependsOn=[] PATCH (the existing dep-edge
        # cascade).
        resp = client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"dependsOn": []},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        resp = client.delete(f"/api/v3/activities/{a1}", headers=admin_headers)
        assert resp.status_code in (200, 204), resp.text

    def test_replace_list_soft_deletes_removed_edges(
        self, client, admin_user, admin_headers, db_session,
    ):
        """PATCH dependsOn that removes a target must soft-delete the edge,
        not physically remove it."""
        _, _, m2, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]

        # Replace [a1] with [a2]: a1 edge is removed, a2 edge is added.
        resp = client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"dependsOn": [a2]},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()

        # DB state: old (ax → a1) exists with deleted_at set; new (ax → a2) live.
        old_edge = db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.source_activity_id == ax_id,
            ActivityDependencyModel.target_activity_id == a1,
        ).one()
        assert old_edge.deleted_at is not None, "removed edge must be soft-deleted"

        new_edge = db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.source_activity_id == ax_id,
            ActivityDependencyModel.target_activity_id == a2,
            ActivityDependencyModel.deleted_at.is_(None),
        ).one()
        assert new_edge.deleted_at is None

    def test_re_adding_previously_removed_edge_inserts_fresh_row(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Re-adding a previously removed (source, target) pair creates a
        NEW row (history preserved). The partial unique index allows the
        dead + live rows to coexist."""
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]

        # Remove, then re-add.
        client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"dependsOn": []}, headers=admin_headers,
        )
        client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"dependsOn": [a1]}, headers=admin_headers,
        )
        db_session.expire_all()

        # Two rows for the (ax, a1) pair: one soft-deleted, one live.
        rows = db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.source_activity_id == ax_id,
            ActivityDependencyModel.target_activity_id == a1,
        ).all()
        assert len(rows) == 2
        assert sum(1 for r in rows if r.deleted_at is None) == 1
        assert sum(1 for r in rows if r.deleted_at is not None) == 1


# ===========================================================================
# Task-level dependencies (hierarchy rule)
# ===========================================================================

class TestTaskDeps:
    def _setup_versioned_tree(self, client, admin_headers):
        """Build a baseline with M1.A1 and M2.A2 + an activity dep A2->A1, then
        version it. Returns (version_id, version_a1_id, version_a2_id)."""
        pid, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        # A2 depends on A1 (cross-milestone).
        r = client.patch(
            f"/api/v3/activities/{a2}",
            json={"dependsOn": [a1]},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)

        # Discover the version's cloned activities (by name match — A1 in M1
        # clones to v_a1, etc.).
        tree = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers)
        assert tree.status_code == 200, tree.text
        v_a1 = v_a2 = None
        for ms in tree.json()["data"]["milestones"]:
            for act in ms["activities"]:
                if act["name"] == "A1":
                    v_a1 = act["id"]
                if act["name"] == "A2":
                    v_a2 = act["id"]
        assert v_a1 and v_a2
        return vid, v_a1, v_a2

    def test_version_clone_carries_activity_dep_with_id_rewrite(
        self, client, admin_user, admin_headers,
    ):
        vid, v_a1, v_a2 = self._setup_versioned_tree(client, admin_headers)
        # Read v_a2 — its dependsOn must point at v_a1, NOT the baseline a1.
        resp = client.get(f"/api/v3/activities/{v_a2}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["dependsOn"] == [v_a1]

    def test_create_task_under_dependent_activity(
        self, client, admin_user, admin_headers,
    ):
        vid, v_a1, v_a2 = self._setup_versioned_tree(client, admin_headers)
        # Task under v_a1 first (no deps).
        t1 = _create_task(client, admin_headers, v_a1, name="T1")
        assert t1.status_code == 201, t1.text
        t1_id = t1.json()["data"]["id"]
        # Task under v_a2 depending on T1 — allowed because v_a2 depends on v_a1.
        t2 = _create_task(client, admin_headers, v_a2, name="T2", depends_on=[t1_id], start_offset=65, end_offset=75)
        assert t2.status_code == 201, t2.text
        assert t2.json()["data"]["dependsOn"] == [t1_id]

    def test_task_dep_across_unlinked_activities_now_allowed(
        self, client, admin_user, admin_headers,
    ):
        # Doc 24: the old "parent activities must be linked" rule was
        # dropped. Tasks can depend on any task in the same project.
        pid, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        tree = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers)
        v_a1 = v_a2 = None
        for ms in tree.json()["data"]["milestones"]:
            for act in ms["activities"]:
                if act["name"] == "A1":
                    v_a1 = act["id"]
                if act["name"] == "A2":
                    v_a2 = act["id"]
        t1 = _create_task(client, admin_headers, v_a1, name="T1")
        t1_id = t1.json()["data"]["id"]
        # No activity-level edge between A1 and A2; this used to 422.
        t2 = _create_task(client, admin_headers, v_a2, name="T2", depends_on=[t1_id], start_offset=65, end_offset=75)
        assert t2.status_code == 201, t2.text
        assert t2.json()["data"]["dependsOn"] == [t1_id]

    def test_same_activity_task_dep_always_allowed(
        self, client, admin_user, admin_headers,
    ):
        # No activity-level edge needed when both tasks share a parent activity.
        pid, _, _, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        tree = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers)
        v_a1 = next(
            act["id"]
            for ms in tree.json()["data"]["milestones"]
            for act in ms["activities"]
            if act["name"] == "A1"
        )
        t1 = _create_task(client, admin_headers, v_a1, name="T1")
        t1_id = t1.json()["data"]["id"]
        t2 = _create_task(client, admin_headers, v_a1, name="T2", depends_on=[t1_id], start_offset=65, end_offset=75)
        assert t2.status_code == 201, t2.text


# ===========================================================================
# Subtask-level dependencies
# ===========================================================================

class TestSubtaskDeps:
    def test_subtask_dep_under_dependent_tasks(
        self, client, admin_user, admin_headers,
    ):
        # Build version + activity dep, then task dep, then subtask dep.
        pid, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        client.patch(
            f"/api/v3/activities/{a2}",
            json={"dependsOn": [a1]},
            headers=admin_headers,
        )
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        tree = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers)
        v_a1 = v_a2 = None
        for ms in tree.json()["data"]["milestones"]:
            for act in ms["activities"]:
                if act["name"] == "A1":
                    v_a1 = act["id"]
                if act["name"] == "A2":
                    v_a2 = act["id"]
        t1 = _create_task(client, admin_headers, v_a1, name="T1").json()["data"]["id"]
        t2 = _create_task(
            client, admin_headers, v_a2, name="T2", depends_on=[t1], start_offset=65, end_offset=75
        ).json()["data"]["id"]

        s1 = _create_subtask(client, admin_headers, t1, name="S1").json()["data"]["id"]
        # Subtask under T2 depending on S1: allowed because T2 depends on T1.
        s2 = _create_subtask(client, admin_headers, t2, name="S2", depends_on=[s1], start_offset=85, end_offset=95)
        assert s2.status_code == 201, s2.text
        assert s2.json()["data"]["dependsOn"] == [s1]

    def test_subtask_dep_across_unlinked_tasks_now_allowed(
        self, client, admin_user, admin_headers,
    ):
        # Doc 24: the old "parent tasks must be linked" rule was dropped.
        # Subtasks can depend on any subtask in the same project.
        pid, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        # No activity-level edge needed any more; tasks no longer require it.
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        tree = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers)
        v_a1 = v_a2 = None
        for ms in tree.json()["data"]["milestones"]:
            for act in ms["activities"]:
                if act["name"] == "A1":
                    v_a1 = act["id"]
                if act["name"] == "A2":
                    v_a2 = act["id"]
        t1 = _create_task(client, admin_headers, v_a1, name="T1").json()["data"]["id"]
        # T2 with NO dep on T1 — used to make the subtask dep below 422.
        t2 = _create_task(client, admin_headers, v_a2, name="T2").json()["data"]["id"]
        s1 = _create_subtask(client, admin_headers, t1, name="S1").json()["data"]["id"]
        s2 = _create_subtask(client, admin_headers, t2, name="S2", depends_on=[s1], start_offset=85, end_offset=95)
        assert s2.status_code == 201, s2.text
        assert s2.json()["data"]["dependsOn"] == [s1]


# ===========================================================================
# Tree response shape
# ===========================================================================

class TestTreeEmitsDependsOn:
    def test_tree_emits_dependsOn_default_empty(
        self, client, admin_user, admin_headers,
    ):
        pid, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        # A2 depends on A1.
        client.patch(
            f"/api/v3/activities/{a2}",
            json={"dependsOn": [a1]},
            headers=admin_headers,
        )
        tree = client.get(f"/api/v3/projects/{pid}/tree", headers=admin_headers)
        assert tree.status_code == 200, tree.text
        flat = {
            act["id"]: act["dependsOn"]
            for ms in tree.json()["data"]["milestones"]
            for act in ms["activities"]
        }
        assert flat[a1] == []
        assert flat[a2] == [a1]


# ===========================================================================
# Soft-delete DB-level assertions for TASK dependencies
# ===========================================================================

class TestTaskDepsSoftDelete:
    def _setup_two_linked_tasks(self, client, admin_headers):
        """Build a version with V_A1 deps V_A2 set up + T1 and T2 where T2
        deps T1. Returns (version_id, T1_id, T2_id)."""
        pid, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        client.patch(
            f"/api/v3/activities/{a2}",
            json={"dependsOn": [a1]},
            headers=admin_headers,
        )
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        tr = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers)
        v_a1 = v_a2 = None
        for ms in tr.json()["data"]["milestones"]:
            for a in ms["activities"]:
                if a["name"] == "A1":
                    v_a1 = a["id"]
                if a["name"] == "A2":
                    v_a2 = a["id"]
        t1 = _create_task(client, admin_headers, v_a1, name="T1").json()["data"]["id"]
        t2 = _create_task(
            client, admin_headers, v_a2, name="T2", depends_on=[t1], start_offset=65, end_offset=75
        ).json()["data"]["id"]
        return vid, t1, t2

    def test_task_replace_soft_deletes_removed_edge(
        self, client, admin_user, admin_headers, db_session,
    ):
        """PATCH task dependsOn with the target removed must soft-delete
        the edge row (not DELETE FROM)."""
        _, t1, t2 = self._setup_two_linked_tasks(client, admin_headers)

        # Remove the dep.
        resp = client.patch(
            f"/api/v3/tasks/{t2}",
            json={"dependsOn": []},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()

        rows = db_session.query(TaskDependencyModel).filter(
            TaskDependencyModel.source_task_id == t2,
            TaskDependencyModel.target_task_id == t1,
        ).all()
        assert len(rows) == 1, "edge row must persist (soft-delete)"
        assert rows[0].deleted_at is not None

    def test_task_re_adding_previously_removed_edge_inserts_fresh_row(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Re-adding the same (source, target) pair creates a NEW row; the
        partial unique allows dead + live to coexist."""
        _, t1, t2 = self._setup_two_linked_tasks(client, admin_headers)

        client.patch(f"/api/v3/tasks/{t2}", json={"dependsOn": []}, headers=admin_headers)
        client.patch(f"/api/v3/tasks/{t2}", json={"dependsOn": [t1]}, headers=admin_headers)
        db_session.expire_all()

        rows = db_session.query(TaskDependencyModel).filter(
            TaskDependencyModel.source_task_id == t2,
            TaskDependencyModel.target_task_id == t1,
        ).all()
        assert len(rows) == 2
        assert sum(1 for r in rows if r.deleted_at is None) == 1
        assert sum(1 for r in rows if r.deleted_at is not None) == 1

    def test_task_delete_with_external_dep_is_blocked(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Doc 34: deleting a target task that has an external
        dependent is refused with 422 + ``dependency_block``."""
        _, t1, t2 = self._setup_two_linked_tasks(client, admin_headers)

        # Sanity: one live edge.
        live = db_session.query(TaskDependencyModel).filter(
            TaskDependencyModel.target_task_id == t1,
            TaskDependencyModel.deleted_at.is_(None),
        ).count()
        assert live == 1

        resp = client.delete(f"/api/v3/tasks/{t1}", headers=admin_headers)
        assert resp.status_code == 422, resp.text
        assert (
            resp.json()["error"]["_embedded"]["details"]["errorIdentifier"]
            == "dependency_block"
        )
        # Edge still live (delete refused).
        live = db_session.query(TaskDependencyModel).filter(
            TaskDependencyModel.target_task_id == t1,
            TaskDependencyModel.deleted_at.is_(None),
        ).count()
        assert live == 1


# ===========================================================================
# Soft-delete DB-level assertions for SUBTASK dependencies
# ===========================================================================

class TestSubtaskDepsSoftDelete:
    def _setup_two_linked_subtasks(self, client, admin_headers):
        """Build a version with task-level dep + S1 under T1 and S2 under
        T2 where S2 deps S1. Returns (S1_id, S2_id)."""
        pid, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        client.patch(
            f"/api/v3/activities/{a2}",
            json={"dependsOn": [a1]},
            headers=admin_headers,
        )
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        tr = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers)
        v_a1 = v_a2 = None
        for ms in tr.json()["data"]["milestones"]:
            for a in ms["activities"]:
                if a["name"] == "A1":
                    v_a1 = a["id"]
                if a["name"] == "A2":
                    v_a2 = a["id"]
        t1 = _create_task(client, admin_headers, v_a1, name="T1").json()["data"]["id"]
        t2 = _create_task(client, admin_headers, v_a2, name="T2", depends_on=[t1], start_offset=65, end_offset=75).json()["data"]["id"]
        s1 = _create_subtask(client, admin_headers, t1, name="S1").json()["data"]["id"]
        s2 = _create_subtask(client, admin_headers, t2, name="S2", depends_on=[s1], start_offset=85, end_offset=95).json()["data"]["id"]
        return s1, s2

    def test_subtask_replace_soft_deletes_removed_edge(
        self, client, admin_user, admin_headers, db_session,
    ):
        s1, s2 = self._setup_two_linked_subtasks(client, admin_headers)

        resp = client.patch(
            f"/api/v3/subtasks/{s2}",
            json={"dependsOn": []},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()

        rows = db_session.query(SubtaskDependencyModel).filter(
            SubtaskDependencyModel.source_subtask_id == s2,
            SubtaskDependencyModel.target_subtask_id == s1,
        ).all()
        assert len(rows) == 1
        assert rows[0].deleted_at is not None

    def test_subtask_re_adding_previously_removed_edge_inserts_fresh_row(
        self, client, admin_user, admin_headers, db_session,
    ):
        s1, s2 = self._setup_two_linked_subtasks(client, admin_headers)

        client.patch(f"/api/v3/subtasks/{s2}", json={"dependsOn": []}, headers=admin_headers)
        client.patch(f"/api/v3/subtasks/{s2}", json={"dependsOn": [s1]}, headers=admin_headers)
        db_session.expire_all()

        rows = db_session.query(SubtaskDependencyModel).filter(
            SubtaskDependencyModel.source_subtask_id == s2,
            SubtaskDependencyModel.target_subtask_id == s1,
        ).all()
        assert len(rows) == 2
        assert sum(1 for r in rows if r.deleted_at is None) == 1
        assert sum(1 for r in rows if r.deleted_at is not None) == 1

    def test_subtask_delete_with_external_dep_is_blocked(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Doc 34: deleting a subtask that has an external dependent
        is refused with 422 + ``dependency_block``."""
        s1, s2 = self._setup_two_linked_subtasks(client, admin_headers)

        resp = client.delete(f"/api/v3/subtasks/{s1}", headers=admin_headers)
        assert resp.status_code == 422, resp.text
        assert (
            resp.json()["error"]["_embedded"]["details"]["errorIdentifier"]
            == "dependency_block"
        )
        # Edge still live.
        live = db_session.query(SubtaskDependencyModel).filter(
            SubtaskDependencyModel.target_subtask_id == s1,
            SubtaskDependencyModel.deleted_at.is_(None),
        ).count()
        assert live == 1


# ===========================================================================
# Milestone delete cascades dep edges across the whole A/T/S subtree
# ===========================================================================

class TestMilestoneDeleteCascadesDeps:
    def test_milestone_delete_with_external_activity_dep_is_blocked(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Doc 34: deleting M1 is refused when an activity outside M1
        (here A2 in M2) depends on something inside M1's subtree (A1).
        Dep edges are no longer auto-orphaned by parent deletes — the
        user must clear the dep first."""
        _, m1, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        client.patch(
            f"/api/v3/activities/{a2}",
            json={"dependsOn": [a1]},
            headers=admin_headers,
        )

        resp = client.delete(f"/api/v3/milestones/{m1}", headers=admin_headers)
        assert resp.status_code == 422, resp.text
        assert (
            resp.json()["error"]["_embedded"]["details"]["errorIdentifier"]
            == "dependency_block"
        )
        # M1 still alive.
        live = db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.target_activity_id == a1,
            ActivityDependencyModel.deleted_at.is_(None),
        ).count()
        assert live == 1, "edge still live, delete refused"

    def test_milestone_delete_soft_deletes_task_and_subtask_edges(
        self, client, admin_user, admin_headers, db_session,
    ):
        """When a milestone on the baseline is deleted, the propagation to
        the version's cloned milestone carries through to tasks + subtasks
        under that milestone — all of their dep edges must be soft-deleted."""
        pid, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
        client.patch(f"/api/v3/activities/{a2}", json={"dependsOn": [a1]}, headers=admin_headers)
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        tr = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers)
        v_a1 = v_a2 = v_m1_under_a1 = None
        for ms in tr.json()["data"]["milestones"]:
            for a in ms["activities"]:
                if a["name"] == "A1":
                    v_a1 = a["id"]
                    v_m1_under_a1 = ms["id"]
                if a["name"] == "A2":
                    v_a2 = a["id"]
        # Build tasks + subtasks under the project, with deps.
        t1 = _create_task(client, admin_headers, v_a1, name="T1").json()["data"]["id"]
        t2 = _create_task(client, admin_headers, v_a2, name="T2", depends_on=[t1], start_offset=65, end_offset=75).json()["data"]["id"]
        s1 = _create_subtask(client, admin_headers, t1, name="S1").json()["data"]["id"]
        s2 = _create_subtask(client, admin_headers, t2, name="S2", depends_on=[s1], start_offset=85, end_offset=95).json()["data"]["id"]

        # Doc 34: with t2 (under v_a2 in a different milestone) depending
        # on t1 (under v_a1 in the milestone we want to delete), the
        # delete is refused. Same with s2 → s1. The doc 34 contract is
        # "remove external deps before deleting".
        resp = client.delete(f"/api/v3/milestones/{v_m1_under_a1}", headers=admin_headers)
        assert resp.status_code == 422, resp.text
        details = resp.json()["error"]["_embedded"]["details"]
        assert details["errorIdentifier"] == "dependency_block"
        # At least 2 blockers: the t2→t1 edge and the s2→s1 edge.
        assert len(details["blockers"]) >= 2

        # All edges still live.
        live_t = db_session.query(TaskDependencyModel).filter(
            TaskDependencyModel.target_task_id == t1,
            TaskDependencyModel.deleted_at.is_(None),
        ).count()
        live_s = db_session.query(SubtaskDependencyModel).filter(
            SubtaskDependencyModel.target_subtask_id == s1,
            SubtaskDependencyModel.deleted_at.is_(None),
        ).count()
        assert live_t == 1
        assert live_s == 1


# ===========================================================================
# Actor threading: deleted_by is set on cascade
# ===========================================================================

class TestActorThreadingOnCascade:
    """Doc 34: external-dep cascade was replaced by an upfront block,
    so the only remaining "cascade soft-deletes a dep edge with
    deleted_by stamped" path is when the user clears the dep via PATCH
    or when the source's parent (which contains the source) is
    deleted. Both PATCH-clear and same-subtree cascade still set
    ``deleted_by`` with the acting user."""

    def test_deleted_by_set_on_replace_list(
        self, client, admin_user, admin_headers, db_session,
    ):
        """PATCH-driven replace that removes an edge stamps deleted_by
        with the current actor."""
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]

        client.patch(
            f"/api/v3/activities/{ax_id}",
            json={"dependsOn": []},
            headers=admin_headers,
        )
        db_session.expire_all()

        dead_row = db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.source_activity_id == ax_id,
            ActivityDependencyModel.target_activity_id == a1,
            ActivityDependencyModel.deleted_at.isnot(None),
        ).one()
        assert dead_row.deleted_by == admin_user.id


# ===========================================================================
# Partial unique index enforcement
# ===========================================================================

class TestPartialUniqueIndex:
    def test_partial_unique_allows_dead_plus_live_same_pair(
        self, client, admin_user, admin_headers, db_session,
    ):
        """The partial unique on (source, target) WHERE deleted_at IS NULL
        permits many dead rows + exactly one live row for the same pair."""
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]

        # Toggle a few times: add/remove/add/remove/add.
        for deps in [[], [a1], [], [a1], [], [a1]]:
            client.patch(
                f"/api/v3/activities/{ax_id}",
                json={"dependsOn": deps},
                headers=admin_headers,
            )
        db_session.expire_all()

        rows = db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.source_activity_id == ax_id,
            ActivityDependencyModel.target_activity_id == a1,
        ).all()
        live = [r for r in rows if r.deleted_at is None]
        dead = [r for r in rows if r.deleted_at is not None]
        assert len(live) == 1, "exactly one LIVE row allowed"
        assert len(dead) >= 2, "multiple dead rows coexist as history"


# ===========================================================================
# Legacy-schema migration (schema v1 → v2)
# ===========================================================================

class TestLegacyDepTableMigration:
    def test_heal_drops_legacy_composite_pk_tables(self, tmp_path):
        """The helper ``_heal_legacy_dep_tables`` must detect and drop any
        dep table whose schema still uses composite PK / no ``id`` column."""
        from sqlalchemy import create_engine, text
        from app.infrastructure.db.session import _heal_legacy_dep_tables

        db_file = tmp_path / "legacy.db"
        engine = create_engine(f"sqlite:///{db_file}")

        # 1. Create three tables with the legacy v1 shape.
        with engine.connect() as conn:
            for tbl, (src, tgt) in (
                ("activity_dependencies", ("source_activity_id", "target_activity_id")),
                ("task_dependencies", ("source_task_id", "target_task_id")),
                ("subtask_dependencies", ("source_subtask_id", "target_subtask_id")),
            ):
                conn.execute(text(f"""
                    CREATE TABLE {tbl} (
                        {src} VARCHAR(36) NOT NULL,
                        {tgt} VARCHAR(36) NOT NULL,
                        project_id VARCHAR(36) NOT NULL,
                        created_at DATETIME,
                        PRIMARY KEY ({src}, {tgt})
                    )
                """))
            conn.commit()

        # Confirm pre-state: three legacy tables, none has `id`.
        with engine.connect() as conn:
            for tbl in ("activity_dependencies", "task_dependencies", "subtask_dependencies"):
                cols = {r[1] for r in conn.execute(text(f"PRAGMA table_info('{tbl}')")).fetchall()}
                assert "id" not in cols, f"test setup: {tbl} should be legacy v1"

        # 2. Run the heal helper.
        with engine.connect() as conn:
            dropped = _heal_legacy_dep_tables(conn)
            conn.commit()

        # 3. Helper reports three drops; all three tables should be gone,
        # ready for ``create_all`` to rebuild with v2.
        assert set(dropped) == {
            "activity_dependencies", "task_dependencies", "subtask_dependencies",
        }
        with engine.connect() as conn:
            for tbl in ("activity_dependencies", "task_dependencies", "subtask_dependencies"):
                cols = conn.execute(text(f"PRAGMA table_info('{tbl}')")).fetchall()
                assert cols == [], f"{tbl} should be dropped"

    def test_heal_is_noop_on_v2_tables(self, tmp_path):
        """Running the helper against v2-shaped tables must not touch them."""
        from sqlalchemy import create_engine, text
        from app.infrastructure.db.session import _heal_legacy_dep_tables

        db_file = tmp_path / "v2.db"
        engine = create_engine(f"sqlite:///{db_file}")

        with engine.connect() as conn:
            # v2 shape: has `id` column.
            conn.execute(text("""
                CREATE TABLE activity_dependencies (
                    id VARCHAR(36) PRIMARY KEY,
                    source_activity_id VARCHAR(36) NOT NULL,
                    target_activity_id VARCHAR(36) NOT NULL,
                    project_id VARCHAR(36) NOT NULL,
                    created_at DATETIME,
                    deleted_at DATETIME,
                    deleted_by INTEGER
                )
            """))
            conn.commit()

        with engine.connect() as conn:
            dropped = _heal_legacy_dep_tables(conn)
            conn.commit()

        assert dropped == [], "v2 tables must not be dropped"
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info('activity_dependencies')")).fetchall()}
            assert "id" in cols, "v2 table still intact"

    def test_heal_is_noop_when_tables_missing(self, tmp_path):
        """If none of the dep tables exist yet (fresh DB), heal is a no-op
        that returns []; create_all will build the tables afterwards."""
        from sqlalchemy import create_engine
        from app.infrastructure.db.session import _heal_legacy_dep_tables

        engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
        with engine.connect() as conn:
            dropped = _heal_legacy_dep_tables(conn)
        assert dropped == []


# ===========================================================================
# Doc 21 — cross-milestone explicit lock-in for A/T/S
# ===========================================================================

class TestCrossMilestoneActivityTaskSubtaskDeps:
    """Lock in: A/T/S deps work across different milestones inside a project.

    Cross-project rejection is already covered above; these are belt-and-
    braces tests so a future regression that quietly tightens the filter to
    same-milestone is caught."""

    def test_activity_in_m1_can_depend_on_activity_in_m2(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid, name="M1")
        m2 = _create_milestone(client, admin_headers, pid, name="M2")
        a_in_m1 = _create_activity(
            client, admin_headers, m1, name="A",
            start_offset=3, end_offset=5,
        ).json()["data"]["id"]
        # New activity in M2 depends on A (cross-milestone, same project).
        # Doc 27: B.start must be >= A.end (5).
        resp = _create_activity(
            client, admin_headers, m2, name="B", depends_on=[a_in_m1],
            start_offset=10, end_offset=20,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["dependsOn"] == [a_in_m1]

    def test_task_under_activity_in_m1_can_depend_on_task_under_activity_in_m2(
        self, client, admin_user, admin_headers,
    ):
        # M1.A1 → A1's task. M2.A2 → A2's task. Both activities linked
        # so the task hierarchy rule is satisfied. Then T2 depends on T1.
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid, name="M1")
        m2 = _create_milestone(client, admin_headers, pid, name="M2")
        a1 = _create_activity(
            client, admin_headers, m1, name="A1",
            start_offset=3, end_offset=5,
        ).json()["data"]["id"]
        a2 = _create_activity(
            client, admin_headers, m2, name="A2", depends_on=[a1],
            start_offset=10, end_offset=20,
        ).json()["data"]["id"]
        # publish + create version for T/S writes
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        # locate version twins of A1, A2
        v_acts = []
        for m in client.get(
            f"/api/v3/projects/{vid}/milestones", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"]:
            v_acts.extend(_list_activities_in(client, admin_headers, m["id"]))
        v_a1 = next(a for a in v_acts if a["name"] == "A1")["id"]
        v_a2 = next(a for a in v_acts if a["name"] == "A2")["id"]
        t1 = _create_task(client, admin_headers, v_a1, name="T1").json()["data"]["id"]
        resp = _create_task(
            client, admin_headers, v_a2, name="T2", depends_on=[t1], start_offset=65, end_offset=75
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["dependsOn"] == [t1]

    def test_subtask_under_task_in_m1_can_depend_on_subtask_under_task_in_m2(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid, name="M1")
        m2 = _create_milestone(client, admin_headers, pid, name="M2")
        a1 = _create_activity(
            client, admin_headers, m1, name="A1",
            start_offset=3, end_offset=5,
        ).json()["data"]["id"]
        a2 = _create_activity(
            client, admin_headers, m2, name="A2", depends_on=[a1],
            start_offset=10, end_offset=20,
        ).json()["data"]["id"]
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)
        v_acts = []
        for m in client.get(
            f"/api/v3/projects/{vid}/milestones", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"]:
            v_acts.extend(_list_activities_in(client, admin_headers, m["id"]))
        v_a1 = next(a for a in v_acts if a["name"] == "A1")["id"]
        v_a2 = next(a for a in v_acts if a["name"] == "A2")["id"]
        t1 = _create_task(client, admin_headers, v_a1, name="T1").json()["data"]["id"]
        t2 = _create_task(
            client, admin_headers, v_a2, name="T2", depends_on=[t1], start_offset=65, end_offset=75
        ).json()["data"]["id"]
        s1 = _create_subtask(client, admin_headers, t1, name="S1").json()["data"]["id"]
        resp = _create_subtask(
            client, admin_headers, t2, name="S2", depends_on=[s1], start_offset=85, end_offset=95
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["dependsOn"] == [s1]


# ===========================================================================
# Doc 21 — milestone-to-milestone dependencies
# ===========================================================================

class TestMilestoneDeps:
    """Milestone-level dependency edges: same-project, no self, acyclic,
    cascade-on-delete, propagated to active versions."""

    def _make_three_milestones(self, client, admin_headers):
        # Doc 27 staggering: M1 ends day+10, M2 starts day+15 / ends day+25,
        # M3 starts day+30. So M2->M1, M3->M2, M3->M1 all satisfy
        # source.start >= target.end.
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(
            client, admin_headers, pid, name="M1",
            start_offset=2, end_offset=10,
        )
        m2 = _create_milestone(
            client, admin_headers, pid, name="M2",
            start_offset=15, end_offset=25,
        )
        m3 = _create_milestone(
            client, admin_headers, pid, name="M3",
            start_offset=30, end_offset=40,
        )
        return pid, m1, m2, m3

    def _patch_milestone(self, client, admin_headers, mid, **body):
        return client.patch(
            f"/api/v3/milestones/{mid}", json=body, headers=admin_headers,
        )

    def _get_milestone(self, client, admin_headers, mid):
        return client.get(f"/api/v3/milestones/{mid}", headers=admin_headers)

    def test_create_with_empty_depends_on(self, client, admin_user, admin_headers):
        pid, _, _, _ = self._make_three_milestones(client, admin_headers)
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={
                "name": "M4",
                "startDate": _future_iso(2),
                "endDate": _future_iso(100),
                "dependsOn": [],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["dependsOn"] == []

    def test_create_with_valid_depends_on(self, client, admin_user, admin_headers):
        pid, m1, m2, _ = self._make_three_milestones(client, admin_headers)
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={
                "name": "M4",
                # M4 must start after both m1.end (day+10) and m2.end (day+25).
                "startDate": _future_iso(50),
                "endDate": _future_iso(100),
                "dependsOn": [m1, m2],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert sorted(resp.json()["data"]["dependsOn"]) == sorted([m1, m2])

    def test_unknown_target_rejected(self, client, admin_user, admin_headers):
        pid, _, _, _ = self._make_three_milestones(client, admin_headers)
        bogus = str(uuid4())
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={
                "name": "M4",
                "startDate": _future_iso(2),
                "endDate": _future_iso(100),
                "dependsOn": [bogus],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "out-of-project" in resp.json()["error"]["message"]

    def test_cross_project_target_rejected(self, client, admin_user, admin_headers):
        _, m1, _, _ = self._make_three_milestones(client, admin_headers)
        pid2 = _create_project(client, admin_headers, name="Other")
        resp = client.post(
            f"/api/v3/projects/{pid2}/milestones/create",
            json={
                "name": "Cross",
                "startDate": _future_iso(2),
                "endDate": _future_iso(100),
                "dependsOn": [m1],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert m1 in resp.json()["error"]["message"]

    def test_self_edge_rejected_on_update(self, client, admin_user, admin_headers):
        _, m1, _, _ = self._make_three_milestones(client, admin_headers)
        resp = self._patch_milestone(
            client, admin_headers, m1, dependsOn=[m1],
        )
        assert resp.status_code == 422
        assert "itself" in resp.json()["error"]["message"]

    def test_cycle_rejected_on_update(self, client, admin_user, admin_headers):
        # Doc 31 makes a date-valid milestone cycle structurally
        # impossible: each edge requires source.end > target.end (strict),
        # so a closed loop forces some milestone to outlast itself. The
        # cycle-detection code remains in place (and is exercised by
        # activity / task / subtask tests), but for milestones the date
        # rule will fire first and the cycle rule is unreachable.
        #
        # We assert the date-rule rejection here so a future regression
        # that quietly relaxes the end rule back to >= would be caught.
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(
            client, admin_headers, pid, name="M1",
            start_offset=10, end_offset=10,
        )
        m2 = _create_milestone(
            client, admin_headers, pid, name="M2",
            start_offset=10, end_offset=10,
        )
        # M2 -> M1 with equal end dates: the strict-end rule rejects it.
        resp = self._patch_milestone(
            client, admin_headers, m2, dependsOn=[m1],
        )
        assert resp.status_code == 422
        # The error names the strict-end requirement, not "cycle".
        assert "strictly after" in resp.json()["error"]["message"], (
            resp.json()["error"]["message"]
        )

    def test_update_replace_list_semantics(self, client, admin_user, admin_headers):
        _, m1, m2, m3 = self._make_three_milestones(client, admin_headers)
        # Start: M3 depends on [M1, M2].
        assert self._patch_milestone(
            client, admin_headers, m3, dependsOn=[m1, m2],
        ).status_code == 200
        # Replace with [M1].
        resp = self._patch_milestone(
            client, admin_headers, m3, dependsOn=[m1],
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["dependsOn"] == [m1]
        # GET reflects.
        assert self._get_milestone(
            client, admin_headers, m3,
        ).json()["data"]["dependsOn"] == [m1]

    def test_get_returns_depends_on(self, client, admin_user, admin_headers):
        _, m1, m2, _ = self._make_three_milestones(client, admin_headers)
        self._patch_milestone(
            client, admin_headers, m2, dependsOn=[m1],
        )
        body = self._get_milestone(client, admin_headers, m2).json()["data"]
        assert body["dependsOn"] == [m1]

    def test_delete_milestone_with_external_dependent_is_blocked(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Doc 34: deleting M2 is refused while M3 still depends on it.
        Outgoing edges (M2->M1) wouldn't block by themselves — only
        incoming edges from outside the subtree do."""
        from app.infrastructure.db.models.milestone_dependency import (
            MilestoneDependencyModel,
        )
        _, m1, m2, m3 = self._make_three_milestones(client, admin_headers)
        # M2 -> M1, M3 -> M2, M3 -> M1.
        self._patch_milestone(client, admin_headers, m2, dependsOn=[m1])
        self._patch_milestone(client, admin_headers, m3, dependsOn=[m2, m1])
        live_before = (
            db_session.query(MilestoneDependencyModel)
            .filter(MilestoneDependencyModel.deleted_at.is_(None))
            .count()
        )
        assert live_before == 3

        resp = client.delete(f"/api/v3/milestones/{m2}", headers=admin_headers)
        assert resp.status_code == 422, resp.text
        assert (
            resp.json()["error"]["_embedded"]["details"]["errorIdentifier"]
            == "dependency_block"
        )
        # All 3 edges still live.
        live_after = (
            db_session.query(MilestoneDependencyModel)
            .filter(MilestoneDependencyModel.deleted_at.is_(None))
            .count()
        )
        assert live_after == 3

        # Removing the M3 -> M2 edge unblocks the delete; the M2 -> M1
        # outgoing edge then cascades soft-delete with M2 (no source
        # outside the subtree of M2).
        self._patch_milestone(client, admin_headers, m3, dependsOn=[m1])
        resp = client.delete(f"/api/v3/milestones/{m2}", headers=admin_headers)
        assert resp.status_code == 204
        live_final = (
            db_session.query(MilestoneDependencyModel)
            .filter(MilestoneDependencyModel.deleted_at.is_(None))
            .count()
        )
        # Only M3 -> M1 remains live (M2 -> M1 went with M2).
        assert live_final == 1

    def test_propagation_to_active_version(
        self, client, admin_user, admin_headers,
    ):
        # Edges set on the baseline propagate to the active version twin.
        pid, m1, m2, m3 = self._make_three_milestones(client, admin_headers)
        # Doc 27 publish gate: every milestone must have ≥1 activity.
        for mid, soff, eoff in (
            (m1, 3, 5), (m2, 16, 18), (m3, 31, 33),
        ):
            r = _create_activity(
                client, admin_headers, mid, name=f"A-{mid[:4]}",
                start_offset=soff, end_offset=eoff,
            )
            assert r.status_code == 201, r.text
        # Before publishing, set M2 -> M1 on baseline so the version clones it.
        self._patch_milestone(client, admin_headers, m2, dependsOn=[m1])
        _publish(client, admin_headers, pid)
        vid = _create_version(client, admin_headers, pid)

        # Locate the version's milestone twins.
        ver_milestones = client.get(
            f"/api/v3/projects/{vid}/milestones", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"]
        v_m1 = next(m for m in ver_milestones if m["name"] == "M1")["id"]
        v_m2 = next(m for m in ver_milestones if m["name"] == "M2")["id"]
        # The cloned edge is V_M2 -> V_M1.
        assert self._get_milestone(
            client, admin_headers, v_m2,
        ).json()["data"]["dependsOn"] == [v_m1]

        # Now mutate the baseline edge — drop it. Version twin should drop too.
        assert self._patch_milestone(
            client, admin_headers, m2, dependsOn=[],
        ).status_code == 200
        assert self._get_milestone(
            client, admin_headers, v_m2,
        ).json()["data"]["dependsOn"] == []
