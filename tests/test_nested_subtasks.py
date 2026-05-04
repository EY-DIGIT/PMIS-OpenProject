"""Tests for nested subtasks (doc 24 part 2).

Covers:
- POST /subtasks/{id}/subtasks/create produces a child subtask with
  parent_subtask_id set and the same root task_id
- Variable-depth labels resolve and surface (S{m}.{a}.{t}.{s1}.{s2}.{s3})
- dependsOn between subtasks at different nesting depths in the same project
- Cascade-on-delete soft-deletes the entire descendant subtree
- Position uniqueness is enforced per parent (top-level vs children)
- SUBTASK_MAX_NESTING_DEPTH env cap rejects creates beyond the limit
- Tree endpoint nests subtasks recursively under their parent subtask
- The legacy POST /tasks/{id}/subtasks/create still works (parent_subtask_id NULL)
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.infrastructure.db.models.subtask import SubtaskModel


def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _create_project(client, headers, *, name="Nest Demo"):
    resp = client.post(
        "/api/v3/projects/create",
        json={
            "name": name, "owner": "tmd1",
            "startDate": _future_iso(1), "endDate": _future_iso(120),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_milestone(client, headers, pid, *, name="M"):
    resp = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={
            "name": name,
            "startDate": _future_iso(2), "endDate": _future_iso(100),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_activity(client, headers, milestone_id, *, name="A"):
    resp = client.post(
        f"/api/v3/milestones/{milestone_id}/activities/standard/create",
        json={
            "name": name,
            "startDate": _future_iso(3), "endDate": _future_iso(80),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _publish(client, headers, pid):
    resp = client.post(f"/api/v3/projects/{pid}/publish", headers=headers)
    assert resp.status_code == 200, resp.text


def _create_version(client, headers, pid):
    resp = client.post(f"/api/v3/projects/{pid}/versions/create", headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _build_version_with_one_task(client, headers):
    """Returns ``(version_project_id, version_task_id)``."""
    pid = _create_project(client, headers)
    m1 = _create_milestone(client, headers, pid, name="M1")
    _create_activity(client, headers, m1, name="A1")
    _publish(client, headers, pid)
    vid = _create_version(client, headers, pid)
    # Locate version twin of A1.
    tree = client.get(f"/api/v3/projects/{vid}/tree", headers=headers).json()["data"]
    v_a1 = tree["milestones"][0]["activities"][0]["id"]
    t_resp = client.post(
        f"/api/v3/activities/{v_a1}/tasks/create",
        json={
            "name": "T1",
            "startDate": _future_iso(4), "endDate": _future_iso(70),
        },
        headers=headers,
    )
    assert t_resp.status_code == 201, t_resp.text
    return vid, t_resp.json()["data"]["id"]


def _create_subtask_under_task(client, headers, task_id, *, name="S",
                               depends_on=None):
    body = {
        "name": name,
        "startDate": _future_iso(5), "endDate": _future_iso(60),
    }
    if depends_on is not None:
        body["dependsOn"] = depends_on
    return client.post(
        f"/api/v3/tasks/{task_id}/subtasks/create",
        json=body, headers=headers,
    )


def _create_subtask_under_subtask(client, headers, parent_subtask_id, *,
                                  name="S", depends_on=None):
    body = {
        "name": name,
        "startDate": _future_iso(6), "endDate": _future_iso(55),
    }
    if depends_on is not None:
        body["dependsOn"] = depends_on
    return client.post(
        f"/api/v3/subtasks/{parent_subtask_id}/subtasks/create",
        json=body, headers=headers,
    )


# ===========================================================================
# Basic nesting + parent linkage
# ===========================================================================

class TestNestedSubtaskCreate:
    def test_top_level_create_still_works(
        self, client, admin_user, admin_headers,
    ):
        _, tid = _build_version_with_one_task(client, admin_headers)
        resp = _create_subtask_under_task(client, admin_headers, tid, name="S1")
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["taskId"] == tid
        assert body["parentSubtaskId"] is None

    def test_create_subtask_under_subtask(
        self, client, admin_user, admin_headers,
    ):
        _, tid = _build_version_with_one_task(client, admin_headers)
        s1 = _create_subtask_under_task(
            client, admin_headers, tid, name="S1",
        ).json()["data"]
        resp = _create_subtask_under_subtask(
            client, admin_headers, s1["id"], name="S1.1",
        )
        assert resp.status_code == 201, resp.text
        nested = resp.json()["data"]
        assert nested["taskId"] == tid  # root task carried through
        assert nested["parentSubtaskId"] == s1["id"]

    def test_three_levels_deep(self, client, admin_user, admin_headers):
        _, tid = _build_version_with_one_task(client, admin_headers)
        s1 = _create_subtask_under_task(client, admin_headers, tid, name="S1").json()["data"]
        s11 = _create_subtask_under_subtask(client, admin_headers, s1["id"], name="S1.1").json()["data"]
        s111 = _create_subtask_under_subtask(client, admin_headers, s11["id"], name="S1.1.1").json()["data"]
        assert s111["parentSubtaskId"] == s11["id"]
        assert s111["taskId"] == tid

    def test_parent_subtask_must_exist(
        self, client, admin_user, admin_headers,
    ):
        # Must have a live version-only project for the writability guard
        # to pass before the not-found check on the parent subtask.
        _, _tid = _build_version_with_one_task(client, admin_headers)
        bogus = str(uuid4())
        resp = _create_subtask_under_subtask(
            client, admin_headers, bogus, name="orphan",
        )
        assert resp.status_code == 404


# ===========================================================================
# Labels
# ===========================================================================

class TestNestedSubtaskLabels:
    def test_labels_extend_with_depth(
        self, client, admin_user, admin_headers,
    ):
        _, tid = _build_version_with_one_task(client, admin_headers)
        s1 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        s11 = _create_subtask_under_subtask(client, admin_headers, s1["id"]).json()["data"]
        s111 = _create_subtask_under_subtask(client, admin_headers, s11["id"]).json()["data"]
        # Top-level: S1.1.1.1 (m=1, a=1, t=1, s=1)
        assert s1["displayCode"] == "S1.1.1.1"
        # One level deeper: S1.1.1.1.1
        assert s11["displayCode"] == "S1.1.1.1.1"
        # Two levels deeper: S1.1.1.1.1.1
        assert s111["displayCode"] == "S1.1.1.1.1.1"

    def test_label_input_resolves_for_nested_subtask(
        self, client, admin_user, admin_headers,
    ):
        # depends_on accepts both UUIDs and labels — the nested label
        # ``S1.1.1.1.1`` should resolve to its UUID at write time.
        _, tid = _build_version_with_one_task(client, admin_headers)
        s1 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        s11 = _create_subtask_under_subtask(client, admin_headers, s1["id"]).json()["data"]
        # Create a sibling at top-level that depends on the nested via label.
        sibling = _create_subtask_under_task(
            client, admin_headers, tid, name="Sib", depends_on=["S1.1.1.1.1"],
        )
        assert sibling.status_code == 201, sibling.text
        assert sibling.json()["data"]["dependsOn"] == [s11["id"]]


# ===========================================================================
# Dependencies across nesting depths (no hierarchy rule, doc 24)
# ===========================================================================

class TestNestedSubtaskDeps:
    def test_top_level_can_depend_on_nested(
        self, client, admin_user, admin_headers,
    ):
        _, tid = _build_version_with_one_task(client, admin_headers)
        s1 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        s11 = _create_subtask_under_subtask(client, admin_headers, s1["id"]).json()["data"]
        sibling = _create_subtask_under_task(
            client, admin_headers, tid, name="Sib",
            depends_on=[s11["id"]],
        )
        assert sibling.status_code == 201, sibling.text
        assert sibling.json()["data"]["dependsOn"] == [s11["id"]]

    def test_nested_can_depend_on_nested_in_different_branch(
        self, client, admin_user, admin_headers,
    ):
        _, tid = _build_version_with_one_task(client, admin_headers)
        # Branch A: S1 → S1.1
        s1 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        s11 = _create_subtask_under_subtask(client, admin_headers, s1["id"]).json()["data"]
        # Branch B: S2 → S2.1
        s2 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        s21 = _create_subtask_under_subtask(
            client, admin_headers, s2["id"], depends_on=[s11["id"]],
        )
        assert s21.status_code == 201, s21.text
        assert s21.json()["data"]["dependsOn"] == [s11["id"]]


# ===========================================================================
# Cascade soft-delete across nested descendants
# ===========================================================================

class TestNestedSubtaskCascadeDelete:
    def test_delete_collapses_entire_descendant_tree(
        self, client, admin_user, admin_headers, db_session,
    ):
        _, tid = _build_version_with_one_task(client, admin_headers)
        s1 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        s11 = _create_subtask_under_subtask(client, admin_headers, s1["id"]).json()["data"]
        s111 = _create_subtask_under_subtask(client, admin_headers, s11["id"]).json()["data"]
        # Sibling under task to verify it's NOT cascaded.
        sib = _create_subtask_under_task(client, admin_headers, tid, name="Sib").json()["data"]

        resp = client.delete(f"/api/v3/subtasks/{s1['id']}", headers=admin_headers)
        assert resp.status_code == 204

        db_session.expire_all()
        rows = (
            db_session.query(SubtaskModel)
            .filter(SubtaskModel.id.in_([s1["id"], s11["id"], s111["id"], sib["id"]]))
            .all()
        )
        by_id = {r.id: r for r in rows}
        assert by_id[s1["id"]].deleted_at is not None
        assert by_id[s11["id"]].deleted_at is not None
        assert by_id[s111["id"]].deleted_at is not None
        # Sibling stays alive.
        assert by_id[sib["id"]].deleted_at is None


# ===========================================================================
# Position uniqueness — separate per parent (doc 24)
# ===========================================================================

class TestPositionUniquenessPerParent:
    def test_different_parents_can_share_position(
        self, client, admin_user, admin_headers,
    ):
        # Two top-level subtasks under the task get positions 1 and 2.
        # Each can have a child at position 1 — both children sit under
        # different parent_subtask_id values, so the partial-unique
        # ``(parent_subtask_id, position) WHERE deleted_at IS NULL``
        # accepts both.
        _, tid = _build_version_with_one_task(client, admin_headers)
        s1 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        s2 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        c1 = _create_subtask_under_subtask(client, admin_headers, s1["id"]).json()["data"]
        c2 = _create_subtask_under_subtask(client, admin_headers, s2["id"]).json()["data"]
        # Both children should auto-assign position 1 (each is the first
        # child of its respective parent).
        assert c1["position"] == 1
        assert c2["position"] == 1


# ===========================================================================
# Depth cap env var
# ===========================================================================

class TestDepthCap:
    def test_depth_cap_rejects_beyond_limit(
        self, client, admin_user, admin_headers, monkeypatch,
    ):
        monkeypatch.setattr(settings, "SUBTASK_MAX_NESTING_DEPTH", 2)
        _, tid = _build_version_with_one_task(client, admin_headers)
        # depth 1: top-level child of task — allowed.
        s1 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        # depth 2: child of s1 — allowed.
        s11 = _create_subtask_under_subtask(client, admin_headers, s1["id"]).json()["data"]
        # depth 3: child of s11 — REJECTED (cap is 2).
        resp = _create_subtask_under_subtask(client, admin_headers, s11["id"])
        assert resp.status_code == 422, resp.text
        assert "depth" in resp.json()["error"]["message"].lower()

    def test_no_cap_allows_arbitrary_depth(
        self, client, admin_user, admin_headers, monkeypatch,
    ):
        monkeypatch.setattr(settings, "SUBTASK_MAX_NESTING_DEPTH", None)
        _, tid = _build_version_with_one_task(client, admin_headers)
        s = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        for _ in range(10):
            s = _create_subtask_under_subtask(client, admin_headers, s["id"]).json()["data"]
        # 10 nested levels accepted without complaint.
        assert s["parentSubtaskId"] is not None


# ===========================================================================
# Tree endpoint nests subtasks recursively
# ===========================================================================

class TestTreeNestsSubtasks:
    def test_tree_includes_nested_subtasks(
        self, client, admin_user, admin_headers,
    ):
        _, tid = _build_version_with_one_task(client, admin_headers)
        s1 = _create_subtask_under_task(client, admin_headers, tid).json()["data"]
        s11 = _create_subtask_under_subtask(client, admin_headers, s1["id"]).json()["data"]

        # Find the version's project id from the task we just created.
        from app.infrastructure.db.models.task import TaskModel
        # We don't have db_session here, so derive vid by walking the API.
        # Easier path: hit GET /tasks/{tid} → projectId.
        task_get = client.get(f"/api/v3/tasks/{tid}", headers=admin_headers)
        vid = task_get.json()["data"]["projectId"]

        tree = client.get(
            f"/api/v3/projects/{vid}/tree", headers=admin_headers,
        ).json()["data"]
        # Drill down to the task → top-level subtask → nested subtask.
        version_task = tree["milestones"][0]["activities"][0]["tasks"][0]
        assert len(version_task["subtasks"]) == 1
        top = version_task["subtasks"][0]
        assert top["id"] == s1["id"]
        assert top["parentSubtaskId"] is None
        assert len(top["subtasks"]) == 1
        nested = top["subtasks"][0]
        assert nested["id"] == s11["id"]
        assert nested["parentSubtaskId"] == s1["id"]
        # Display codes carry through the nesting.
        assert nested["displayCode"] == "S1.1.1.1.1"
