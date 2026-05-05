"""Doc 30 follow-up: auto-bump position on explicit-position collision.

Reported bug (portal):
  Swagger UI's multipart "Try it out" auto-fills the ``position`` form
  field with ``0`` when the caller doesn't override it. The first
  milestone created via Swagger gets position 0 fine. The second one
  also tries position 0 because Swagger's default doesn't change — the
  INSERT trips the ``uq_milestones_project_position_live`` unique index
  and the request 500s with a raw psycopg2.errors.UniqueViolation.

  Production stack-trace observed:
    duplicate key value violates unique constraint
    "uq_milestones_project_position_live"
    DETAIL: Key (project_id, "position")=(<pid>, 0) already exists.

Why it's not just a Swagger problem:
  Same crash happens on the JSON path if any client sends
  ``"position": 0`` for a project that already has a position-0
  milestone. Pre-fix, the service only auto-assigned when the field
  was ``None``; an explicit value (even one that collided) was passed
  through verbatim.

Fix (this commit):
  Each create service (milestone / activity / task / subtask, including
  the nested-subtask variant) now consults a ``position_taken`` repo
  method before committing the INSERT. If the caller-supplied position
  is already occupied by a live row in the same parent scope, we
  silently bump to ``next_position`` instead of crashing. Position is
  semantically an ordering hint; "insert at the top" semantics aren't a
  thing on these endpoints — repositioning happens via separate
  update / move flows.

These tests pin the contract for both the JSON path (deliberate
explicit position via the typed body) and the multipart path (the
Swagger-auto-fill scenario the user actually hit).
"""
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from app.infrastructure.db.models.milestone import MilestoneModel
from app.infrastructure.db.models.activity import ActivityModel
from app.infrastructure.db.models.task import TaskModel
from app.infrastructure.db.models.subtask import SubtaskModel


def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


@pytest.fixture(scope="function")
def project_with_one_milestone(client, admin_headers):
    """Bootstrap a project + one milestone (which lands at position 1
    via ``next_position`` — first row in an empty project) so the next
    milestone-create with explicit ``position=1`` collides."""
    pr = client.post(
        "/api/v3/projects/create",
        json={
            "name": "Pos collision project",
            "owner": "tmd1",
            "startDate": _future_iso(1), "endDate": _future_iso(120),
        },
        headers=admin_headers,
    )
    assert pr.status_code == 201, pr.text
    pid = pr.json()["data"]["id"]

    m1 = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={
            "name": "M1",
            "startDate": _future_iso(2), "endDate": _future_iso(100),
        },
        headers=admin_headers,
    )
    assert m1.status_code == 201, m1.text
    return pid, m1.json()["data"]


# ===========================================================================
# Milestone — the user's exact bug
# ===========================================================================

class TestMilestonePositionCollision:
    def test_json_explicit_colliding_position_auto_bumps(
        self, client, admin_headers, project_with_one_milestone, db_session,
    ):
        """JSON path: client sends a position already taken — service
        bumps silently rather than 500-ing on the unique-index INSERT."""
        pid, m1 = project_with_one_milestone
        existing_pos = m1["position"]

        m2 = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={
                "name": "M2-collide",
                "startDate": _future_iso(3), "endDate": _future_iso(99),
                "position": existing_pos,
            },
            headers=admin_headers,
        )
        assert m2.status_code == 201, m2.text
        d = m2.json()["data"]
        assert d["position"] != existing_pos, (
            "Expected service to auto-bump away from the collision; "
            f"got the same position {existing_pos} for M1 and M2."
        )

        # DB: two distinct positions (constraint passes).
        positions = sorted(
            r.position
            for r in db_session.query(MilestoneModel)
            .filter(MilestoneModel.project_id == pid)
            .all()
        )
        assert len(positions) == 2 and positions[0] != positions[1]

    def test_multipart_swagger_default_position_zero_works(
        self, client, admin_headers, project_with_one_milestone,
    ):
        """User's reported scenario verbatim. Swagger's auto-fill
        ``position=0`` must not 500 when there's already a position-0
        milestone (or any other live milestone, depending on
        next_position assignment)."""
        pid, m1 = project_with_one_milestone

        # First, force a milestone INTO position 0 to mirror the user's
        # production state. Send explicit position 0 over JSON.
        m_zero = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={
                "name": "M-pos-0",
                "startDate": _future_iso(2), "endDate": _future_iso(100),
                "position": 0,
            },
            headers=admin_headers,
        )
        assert m_zero.status_code == 201, m_zero.text
        # If position 0 was free (next_position starts at 1), this row
        # took it; otherwise it bumped. Either way, position 0 is now
        # occupied by SOMETHING.

        # Now repeat the user's exact multipart shape (Swagger auto-
        # fills ``position=0``). Date range is anchored to the test
        # project's start (``_future_iso``-based) — the user's report
        # used hardcoded May 2026 dates against a real production
        # project; here we just need any in-range dates so the floor
        # rule passes and the position-collision branch is the only
        # thing under test.
        m2 = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            headers=admin_headers,
            data={
                "name": "M-with-comment",
                "description": "string",
                "startDate": _future_iso(2),
                "endDate":   _future_iso(100),
                "position": "0",   # <-- the Swagger auto-fill
                "status": "",
                "dependsOn": "",
                "vendors": "",
            },
        )
        assert m2.status_code == 201, m2.text

    def test_omitted_position_still_auto_assigns(
        self, client, admin_headers, project_with_one_milestone,
    ):
        """Sanity check: omitting position keeps the existing
        next_position behaviour (no behaviour regression)."""
        pid, _ = project_with_one_milestone
        m2 = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={
                "name": "M-no-pos",
                "startDate": _future_iso(3), "endDate": _future_iso(99),
            },
            headers=admin_headers,
        )
        assert m2.status_code == 201, m2.text
        # Position came from next_position — concrete int >= 1.
        assert m2.json()["data"]["position"] >= 1


# ===========================================================================
# Activity — same fix applied
# ===========================================================================

class TestActivityPositionCollision:
    def test_json_explicit_colliding_position_auto_bumps(
        self, client, admin_headers, project_with_one_milestone,
    ):
        pid, m1 = project_with_one_milestone
        a1 = client.post(
            f"/api/v3/milestones/{m1['id']}/activities/standard/create",
            json={
                "name": "A1",
                "startDate": _future_iso(3), "endDate": _future_iso(80),
            },
            headers=admin_headers,
        ).json()["data"]
        # Explicit collision.
        a2 = client.post(
            f"/api/v3/milestones/{m1['id']}/activities/standard/create",
            json={
                "name": "A2-collide",
                "startDate": _future_iso(3), "endDate": _future_iso(80),
                "position": a1["position"],
            },
            headers=admin_headers,
        )
        assert a2.status_code == 201, a2.text
        assert a2.json()["data"]["position"] != a1["position"]

    def test_multipart_position_zero_does_not_500(
        self, client, admin_headers, project_with_one_milestone,
    ):
        """Same Swagger auto-fill scenario, applied to activity create."""
        _pid, m1 = project_with_one_milestone
        # Seed: an activity at position 0.
        client.post(
            f"/api/v3/milestones/{m1['id']}/activities/standard/create",
            json={
                "name": "A-pos-0",
                "startDate": _future_iso(3), "endDate": _future_iso(80),
                "position": 0,
            },
            headers=admin_headers,
        )
        # Multipart with the colliding default 0.
        a2 = client.post(
            f"/api/v3/milestones/{m1['id']}/activities/standard/create",
            headers=admin_headers,
            data={
                "name": "A-mp-collide",
                "startDate": _future_iso(3), "endDate": _future_iso(80),
                "position": "0",
            },
        )
        assert a2.status_code == 201, a2.text


# ===========================================================================
# Task + Subtask (top-level + nested) — round out the coverage
# ===========================================================================

@pytest.fixture(scope="function")
def version_task(client, admin_headers, project_with_one_milestone):
    """Build a versioned project so task + subtask creates are allowed."""
    pid, m1 = project_with_one_milestone
    a1 = client.post(
        f"/api/v3/milestones/{m1['id']}/activities/standard/create",
        json={
            "name": "A1",
            "startDate": _future_iso(3), "endDate": _future_iso(80),
        },
        headers=admin_headers,
    ).json()["data"]
    pub = client.post(f"/api/v3/projects/{pid}/publish", headers=admin_headers)
    assert pub.status_code == 200, pub.text
    vr = client.post(f"/api/v3/projects/{pid}/versions/create", headers=admin_headers)
    assert vr.status_code == 201, vr.text
    vid = vr.json()["data"]["id"]
    tree = client.get(f"/api/v3/projects/{vid}/tree", headers=admin_headers).json()["data"]
    v_a1 = tree["milestones"][0]["activities"][0]["id"]
    t1 = client.post(
        f"/api/v3/activities/{v_a1}/tasks/create",
        json={
            "name": "T1",
            "startDate": _future_iso(4), "endDate": _future_iso(70),
        },
        headers=admin_headers,
    ).json()["data"]
    return v_a1, t1["id"]


class TestTaskPositionCollision:
    def test_explicit_collision_auto_bumps(
        self, client, admin_headers, version_task,
    ):
        v_a1, t1_id = version_task
        # Use a fresh task to avoid colliding with T1's auto-assigned slot.
        t2 = client.post(
            f"/api/v3/activities/{v_a1}/tasks/create",
            json={
                "name": "T-collide",
                "startDate": _future_iso(5), "endDate": _future_iso(60),
                "position": 1,  # T1 took position 1 already
            },
            headers=admin_headers,
        )
        assert t2.status_code == 201, t2.text
        assert t2.json()["data"]["position"] != 1


class TestSubtaskPositionCollision:
    def test_top_level_subtask_collision_auto_bumps(
        self, client, admin_headers, version_task,
    ):
        _, tid = version_task
        s1 = client.post(
            f"/api/v3/tasks/{tid}/subtasks/create",
            json={
                "name": "S1",
                "startDate": _future_iso(5), "endDate": _future_iso(60),
            },
            headers=admin_headers,
        ).json()["data"]
        s2 = client.post(
            f"/api/v3/tasks/{tid}/subtasks/create",
            json={
                "name": "S2-collide",
                "startDate": _future_iso(5), "endDate": _future_iso(60),
                "position": s1["position"],
            },
            headers=admin_headers,
        )
        assert s2.status_code == 201, s2.text
        assert s2.json()["data"]["position"] != s1["position"]

    def test_nested_subtask_collision_auto_bumps(
        self, client, admin_headers, version_task,
    ):
        """Nested-subtask uniqueness scope is parent_subtask_id, not
        task_id. Same auto-bump must apply on that scope."""
        _, tid = version_task
        s1 = client.post(
            f"/api/v3/tasks/{tid}/subtasks/create",
            json={
                "name": "S1-parent",
                "startDate": _future_iso(5), "endDate": _future_iso(60),
            },
            headers=admin_headers,
        ).json()["data"]
        # First nested child — auto-assigned.
        n1 = client.post(
            f"/api/v3/subtasks/{s1['id']}/subtasks/create",
            json={
                "name": "N1",
                "startDate": _future_iso(6), "endDate": _future_iso(55),
            },
            headers=admin_headers,
        ).json()["data"]
        # Second nested child colliding on N1's position.
        n2 = client.post(
            f"/api/v3/subtasks/{s1['id']}/subtasks/create",
            json={
                "name": "N2-collide",
                "startDate": _future_iso(6), "endDate": _future_iso(55),
                "position": n1["position"],
            },
            headers=admin_headers,
        )
        assert n2.status_code == 201, n2.text
        assert n2.json()["data"]["position"] != n1["position"]
