"""Doc 28: ``GET /tasks/{id}/subtasks`` returns top-level subtasks with
nested children embedded recursively.

Reported bug: pre-fix, the endpoint returned every subtask under the
task FLAT — top-level + nested all at the same array level, sorted by
``(position, id)``. The FE rendered each row at the same indentation
and nesting was invisible. Confirmed via a doc-26 version project where
the user created s1 → s1.1 → s1.1.1 via the correct nested-create
endpoint, but the listing API showed all three as siblings under T1.

Root cause: ``SubtaskRepository.list_by_task`` filtered only by
``task_id``. ``task_id`` is denormalized to the root task on every
nested subtask, so the filter pulled the entire subtree.

Fix: scope ``list_by_task`` to ``parent_subtask_id IS NULL`` (top-level
only) and use a sibling ``list_nested_under_task`` to pull every nested
descendant. The controller then groups nested rows by
``parent_subtask_id`` and embeds them recursively in each top-level
row's ``subtasks: [...]`` array — same shape as the tree endpoint's
subtask node.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.models.milestone import MilestoneModel
from app.infrastructure.db.models.activity import ActivityModel
from app.infrastructure.db.models.task import TaskModel
from app.infrastructure.db.models.subtask import SubtaskModel


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------

def _make_subtree(db_session, sample_project):
    """Direct ORM inserts: a task with a 4-deep subtask chain plus a
    sibling branch. Same shape used in the manual reproduction.

    Layout:
      T1
       ├─ s1                            (top-level)
       │   ├─ s1.1                      (depth 2)
       │   │   └─ s1.1.1                (depth 3)
       │   │       └─ s1.1.1.1          (depth 4)
       │   └─ s1.2                      (depth 2)
       └─ s2                            (top-level)
           └─ s2.1                      (depth 2)
    """
    now = datetime.now(timezone.utc)
    m = MilestoneModel(
        id=str(uuid4()), project_id=sample_project.id, name="M1",
        description="-",
        start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
        position=1, status="not_completed",
        created_at=now, updated_at=now,
    )
    db_session.add(m); db_session.commit(); db_session.refresh(m)

    a = ActivityModel(
        id=str(uuid4()), project_id=sample_project.id, milestone_id=m.id,
        name="A1", description="-", type="standard",
        start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
        position=1,
        created_at=now, updated_at=now,
    )
    db_session.add(a); db_session.commit(); db_session.refresh(a)

    t = TaskModel(
        id=str(uuid4()), project_id=sample_project.id, activity_id=a.id,
        name="T1", description="-", type="standard",
        start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
        position=1,
        created_at=now, updated_at=now,
    )
    db_session.add(t); db_session.commit(); db_session.refresh(t)

    def make_sub(parent_id, name, position):
        s = SubtaskModel(
            id=str(uuid4()), project_id=sample_project.id, task_id=t.id,
            parent_subtask_id=parent_id,
            name=name, description="-", type="standard",
            start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
            position=position,
            created_at=now, updated_at=now,
        )
        db_session.add(s); db_session.commit(); db_session.refresh(s)
        return s

    s1 = make_sub(None, "s1", 1)
    s11 = make_sub(s1.id, "s1.1", 1)
    s111 = make_sub(s11.id, "s1.1.1", 1)
    s1111 = make_sub(s111.id, "s1.1.1.1", 1)
    s12 = make_sub(s1.id, "s1.2", 2)
    s2 = make_sub(None, "s2", 2)
    s21 = make_sub(s2.id, "s2.1", 1)

    return t, {
        "s1": s1, "s11": s11, "s111": s111, "s1111": s1111,
        "s12": s12, "s2": s2, "s21": s21,
    }


# ===========================================================================
# Pagination + count semantics
# ===========================================================================

class TestPaginationCountsTopLevelOnly:
    """``total`` reflects ONLY top-level subtasks, not subtree size."""

    def test_total_counts_only_top_level(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        task, _ = _make_subtree(db_session, sample_project)
        resp = client.get(
            f"/api/v3/tasks/{task.id}/subtasks", headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        # Subtree has 7 subtasks total, 2 are top-level (s1, s2).
        assert data["total"] == 2, data
        assert data["count"] == 2

    def test_top_level_rows_only_at_collection_level(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        task, ids = _make_subtree(db_session, sample_project)
        resp = client.get(
            f"/api/v3/tasks/{task.id}/subtasks", headers=admin_headers,
        )
        elements = resp.json()["data"]["_embedded"]["elements"]
        ids_in_response = {e["id"] for e in elements}
        # Only s1 + s2 should be at the top level.
        assert ids_in_response == {ids["s1"].id, ids["s2"].id}


# ===========================================================================
# Nested children embedded under each top-level row
# ===========================================================================

class TestNestedEmbedding:
    def test_each_top_level_carries_subtasks_key(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        task, _ = _make_subtree(db_session, sample_project)
        resp = client.get(
            f"/api/v3/tasks/{task.id}/subtasks", headers=admin_headers,
        )
        elements = resp.json()["data"]["_embedded"]["elements"]
        for el in elements:
            assert "subtasks" in el, f"missing 'subtasks' key on {el['name']}"
            assert isinstance(el["subtasks"], list)

    def test_immediate_children_correctly_grouped(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        task, ids = _make_subtree(db_session, sample_project)
        resp = client.get(
            f"/api/v3/tasks/{task.id}/subtasks", headers=admin_headers,
        )
        by_name = {e["name"]: e for e in resp.json()["data"]["_embedded"]["elements"]}
        s1 = by_name["s1"]
        s2 = by_name["s2"]
        assert {c["name"] for c in s1["subtasks"]} == {"s1.1", "s1.2"}
        assert {c["name"] for c in s2["subtasks"]} == {"s2.1"}

    def test_deep_recursive_nesting(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        task, ids = _make_subtree(db_session, sample_project)
        resp = client.get(
            f"/api/v3/tasks/{task.id}/subtasks", headers=admin_headers,
        )
        elements = resp.json()["data"]["_embedded"]["elements"]
        # Walk s1 → s1.1 → s1.1.1 → s1.1.1.1 (4 levels).
        s1 = next(e for e in elements if e["name"] == "s1")
        s11 = next(c for c in s1["subtasks"] if c["name"] == "s1.1")
        s111 = next(c for c in s11["subtasks"] if c["name"] == "s1.1.1")
        s1111 = next(c for c in s111["subtasks"] if c["name"] == "s1.1.1.1")
        assert s1111["parentSubtaskId"] == ids["s111"].id
        assert s1111["subtasks"] == []   # leaf

    def test_leaf_subtasks_have_empty_subtasks_array(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        task, ids = _make_subtree(db_session, sample_project)
        resp = client.get(
            f"/api/v3/tasks/{task.id}/subtasks", headers=admin_headers,
        )
        elements = resp.json()["data"]["_embedded"]["elements"]
        # s1.2 and s2.1 are leaves.
        s1 = next(e for e in elements if e["name"] == "s1")
        s2 = next(e for e in elements if e["name"] == "s2")
        s12 = next(c for c in s1["subtasks"] if c["name"] == "s1.2")
        s21 = next(c for c in s2["subtasks"] if c["name"] == "s2.1")
        assert s12["subtasks"] == []
        assert s21["subtasks"] == []

    def test_display_codes_extend_with_depth(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        task, _ = _make_subtree(db_session, sample_project)
        resp = client.get(
            f"/api/v3/tasks/{task.id}/subtasks", headers=admin_headers,
        )
        elements = resp.json()["data"]["_embedded"]["elements"]
        # All top-level: depth 4 (S{m}.{a}.{t}.{s})
        for el in elements:
            assert el["displayCode"].count(".") == 3, el["displayCode"]
        # First child: depth 5
        s1 = next(e for e in elements if e["name"] == "s1")
        for c in s1["subtasks"]:
            assert c["displayCode"].count(".") == 4
        # Walk to depth 7 (s1.1.1.1)
        s11 = next(c for c in s1["subtasks"] if c["name"] == "s1.1")
        s111 = s11["subtasks"][0]
        s1111 = s111["subtasks"][0]
        assert s1111["displayCode"].count(".") == 6


# ===========================================================================
# Empty cases
# ===========================================================================

class TestEmptyCases:
    def test_task_with_no_subtasks(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        # Make a task with zero subtasks.
        now = datetime.now(timezone.utc)
        m = MilestoneModel(
            id=str(uuid4()), project_id=sample_project.id, name="M",
            description="-",
            start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
            position=1, status="not_completed",
            created_at=now, updated_at=now,
        )
        db_session.add(m); db_session.commit()
        a = ActivityModel(
            id=str(uuid4()), project_id=sample_project.id, milestone_id=m.id,
            name="A", description="-", type="standard",
            start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
            position=1, created_at=now, updated_at=now,
        )
        db_session.add(a); db_session.commit()
        t = TaskModel(
            id=str(uuid4()), project_id=sample_project.id, activity_id=a.id,
            name="T", description="-", type="standard",
            start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
            position=1, created_at=now, updated_at=now,
        )
        db_session.add(t); db_session.commit()

        resp = client.get(
            f"/api/v3/tasks/{t.id}/subtasks", headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["count"] == 0
        assert data["_embedded"]["elements"] == []

    def test_top_level_with_no_children(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        # Single top-level subtask with zero children.
        now = datetime.now(timezone.utc)
        m = MilestoneModel(
            id=str(uuid4()), project_id=sample_project.id, name="M2",
            description="-",
            start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
            position=1, status="not_completed",
            created_at=now, updated_at=now,
        )
        db_session.add(m); db_session.commit()
        a = ActivityModel(
            id=str(uuid4()), project_id=sample_project.id, milestone_id=m.id,
            name="A2", description="-", type="standard",
            start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
            position=1, created_at=now, updated_at=now,
        )
        db_session.add(a); db_session.commit()
        t = TaskModel(
            id=str(uuid4()), project_id=sample_project.id, activity_id=a.id,
            name="T2", description="-", type="standard",
            start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
            position=1, created_at=now, updated_at=now,
        )
        db_session.add(t); db_session.commit()
        s = SubtaskModel(
            id=str(uuid4()), project_id=sample_project.id, task_id=t.id,
            parent_subtask_id=None,
            name="solo", description="-", type="standard",
            start_date=datetime(2026, 8, 1), end_date=datetime(2026, 12, 31),
            position=1, created_at=now, updated_at=now,
        )
        db_session.add(s); db_session.commit()

        resp = client.get(
            f"/api/v3/tasks/{t.id}/subtasks", headers=admin_headers,
        )
        data = resp.json()["data"]
        assert data["total"] == 1
        elements = data["_embedded"]["elements"]
        assert len(elements) == 1
        assert elements[0]["name"] == "solo"
        assert elements[0]["subtasks"] == []


# ===========================================================================
# Soft-deleted children are excluded by default
# ===========================================================================

class TestSoftDeletedFiltering:
    def test_soft_deleted_nested_subtask_excluded_by_default(
        self, client, admin_user, admin_headers, db_session, sample_project,
    ):
        task, ids = _make_subtree(db_session, sample_project)
        # Soft-delete s1.1.1.1 (the deepest leaf) directly.
        ids["s1111"].deleted_at = datetime.now(timezone.utc)
        db_session.add(ids["s1111"]); db_session.commit()

        resp = client.get(
            f"/api/v3/tasks/{task.id}/subtasks", headers=admin_headers,
        )
        elements = resp.json()["data"]["_embedded"]["elements"]
        s1 = next(e for e in elements if e["name"] == "s1")
        s11 = next(c for c in s1["subtasks"] if c["name"] == "s1.1")
        s111 = next(c for c in s11["subtasks"] if c["name"] == "s1.1.1")
        # s1.1.1.1 was the only child of s1.1.1; should be filtered out.
        assert s111["subtasks"] == []
