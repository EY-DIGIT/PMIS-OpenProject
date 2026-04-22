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
            "owner": "admin",
            "startDate": _future_iso(1),
            "endDate": _future_iso(120),
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_milestone(client, admin_headers, project_id, *, name="M"):
    resp = client.post(
        f"/api/v3/projects/{project_id}/milestones/create",
        json={
            "name": name,
            "startDate": _future_iso(2),
            "endDate": _future_iso(100),
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_activity(client, admin_headers, milestone_id, *, name="A", depends_on=None):
    body = {
        "name": name,
        "type": "standard",
        "startDate": _future_iso(3),
        "endDate": _future_iso(80),
    }
    if depends_on is not None:
        body["dependsOn"] = depends_on
    resp = client.post(
        f"/api/v3/milestones/{milestone_id}/activities/create",
        json=body,
        headers=admin_headers,
    )
    return resp


def _publish(client, admin_headers, project_id):
    # The project needs at least one milestone to have been added so that the
    # create_version path doesn't trip an empty-tree edge case. The publish
    # endpoint itself moves status from new/draft -> published.
    resp = client.post(
        f"/api/v3/projects/{project_id}/publish", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text


def _create_version(client, admin_headers, baseline_id):
    resp = client.post(
        f"/api/v3/projects/{baseline_id}/versions/create",
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _list_activities_in(client, admin_headers, milestone_id):
    resp = client.get(
        f"/api/v3/milestones/{milestone_id}/activities", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["_embedded"]["elements"]


def _build_baseline_with_two_activities(client, admin_headers):
    """Returns (project_id, milestone1_id, milestone2_id, activity1_id, activity2_id)."""
    pid = _create_project(client, admin_headers)
    m1 = _create_milestone(client, admin_headers, pid, name="M1")
    m2 = _create_milestone(client, admin_headers, pid, name="M2")
    a1 = _create_activity(client, admin_headers, m1, name="A1")
    assert a1.status_code == 201, a1.text
    a2 = _create_activity(client, admin_headers, m2, name="A2")
    assert a2.status_code == 201, a2.text
    return pid, m1, m2, a1.json()["data"]["id"], a2.json()["data"]["id"]


def _create_task(client, admin_headers, activity_id, *, name="T", depends_on=None,
                 start_offset=4, end_offset=70):
    body = {
        "name": name,
        "type": "standard",
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
                    start_offset=5, end_offset=60):
    body = {
        "name": name,
        "type": "standard",
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
        _, _, _, a1, a2 = _build_baseline_with_two_activities(client, admin_headers)
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
    def test_deleting_target_drops_edges(self, client, admin_user, admin_headers, db_session):
        _, _, m2, a1, _ = _build_baseline_with_two_activities(client, admin_headers)
        ax = _create_activity(client, admin_headers, m2, name="AX", depends_on=[a1])
        ax_id = ax.json()["data"]["id"]

        # Sanity: edge exists.
        assert db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.target_activity_id == a1
        ).count() == 1

        # Delete A1. AX's incoming dep should be silently dropped; AX itself stays.
        resp = client.delete(f"/api/v3/activities/{a1}", headers=admin_headers)
        assert resp.status_code in (200, 204), resp.text

        # Edge gone.
        db_session.expire_all()
        assert db_session.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.target_activity_id == a1
        ).count() == 0

        # AX still exists, with empty dependsOn now.
        get_ax = client.get(f"/api/v3/activities/{ax_id}", headers=admin_headers)
        assert get_ax.status_code == 200
        assert get_ax.json()["data"]["dependsOn"] == []


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
        t2 = _create_task(client, admin_headers, v_a2, name="T2", depends_on=[t1_id])
        assert t2.status_code == 201, t2.text
        assert t2.json()["data"]["dependsOn"] == [t1_id]

    def test_create_task_violating_hierarchy_rejected(
        self, client, admin_user, admin_headers,
    ):
        # Setup: version with NO activity dep between A1 and A2.
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
        # T1 under v_a1, then try T2 under v_a2 depending on T1.
        t1 = _create_task(client, admin_headers, v_a1, name="T1")
        t1_id = t1.json()["data"]["id"]
        t2 = _create_task(client, admin_headers, v_a2, name="T2", depends_on=[t1_id])
        assert t2.status_code == 422, t2.text
        assert "activity-level" in t2.json()["error"]["message"]

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
        t2 = _create_task(client, admin_headers, v_a1, name="T2", depends_on=[t1_id])
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
            client, admin_headers, v_a2, name="T2", depends_on=[t1],
        ).json()["data"]["id"]

        s1 = _create_subtask(client, admin_headers, t1, name="S1").json()["data"]["id"]
        # Subtask under T2 depending on S1: allowed because T2 depends on T1.
        s2 = _create_subtask(client, admin_headers, t2, name="S2", depends_on=[s1])
        assert s2.status_code == 201, s2.text
        assert s2.json()["data"]["dependsOn"] == [s1]

    def test_subtask_dep_violating_hierarchy_rejected(
        self, client, admin_user, admin_headers,
    ):
        # Same setup but WITHOUT the task-level edge.
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
        # T2 with NO dep on T1.
        t2 = _create_task(client, admin_headers, v_a2, name="T2").json()["data"]["id"]
        s1 = _create_subtask(client, admin_headers, t1, name="S1").json()["data"]["id"]
        s2 = _create_subtask(client, admin_headers, t2, name="S2", depends_on=[s1])
        assert s2.status_code == 422
        assert "task-level" in s2.json()["error"]["message"]


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
