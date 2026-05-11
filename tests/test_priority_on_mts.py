"""Doc 41 follow-up — priority on milestones / tasks / subtasks.

Activity already had priority (doc 41 — see tests/test_priority_catalog.py).
This file extends the same coverage to M/T/S/nested-S:

  - REQUIRED on create at all four levels (omission → 422)
  - validates against the live priorities catalog (unknown → 422)
  - admin-added codes (e.g. p4) immediately accepted at every level
  - PATCH /{kind}/{id} updates priority independently
  - the four levels are INDEPENDENT — a milestone with priority p1
    can have an activity p2, task p3, subtask p1, nested subtask p2,
    and none of them constrain each other (no parent-child rule)
  - tree endpoint surfaces priority on every node (M/A/T/S/nested-S)
"""
from uuid import uuid4


def _iso(y, m, d):
    return f"{y:04d}-{m:02d}-{d:02d}T00:00:00+05:30"


def _setup(client, admin_headers):
    """Project + vendor + attached. Returns (pid, vid)."""
    proj = client.post(
        "/api/v3/projects/create",
        headers=admin_headers,
        json={
            "name": f"Pri P {uuid4().hex[:4]}", "owner": "tmd1",
            "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 12, 31),
        },
    ).json()["data"]
    pid = proj["id"]
    v = client.post(
        "/api/v3/master/vendors/create",
        headers=admin_headers,
        json={"name": f"Pri V {uuid4().hex[:4]}", "phoneNumber": "+919999999999"},
    ).json()["data"]
    vid = v["id"]
    client.patch(
        f"/api/v3/projects/{pid}", headers=admin_headers,
        json={"vendorIds": [vid]},
    )
    return pid, vid


def _make_milestone(client, headers, pid, *, priority="p1", name="M1"):
    return client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        headers=headers,
        json={
            "name": name,
            "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 8, 30),
            "priority": priority,
        },
    )


def _make_activity(client, headers, mid, vid, *, priority="p1", name="A1"):
    return client.post(
        f"/api/v3/milestones/{mid}/activities/create",
        headers=headers,
        json={
            "name": name,
            "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 7, 30),
            "ownerDivision": "tmd1", "vendorId": vid,
            "concernedDivision": ["tmd1"],
            "priority": priority,
        },
    )


def _publish(client, headers, pid):
    """Tasks / subtasks can only be created against a published project."""
    pub = client.post(f"/api/v3/projects/{pid}/publish", headers=headers)
    assert pub.status_code in (200, 201), pub.text


def _make_task(client, headers, aid, *, priority="p1", name="T1"):
    return client.post(
        f"/api/v3/activities/{aid}/tasks/create",
        headers=headers,
        json={
            "name": name,
            "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 7, 15),
            "priority": priority,
        },
    )


def _make_subtask(client, headers, tid, *, priority="p1", name="S1"):
    return client.post(
        f"/api/v3/tasks/{tid}/subtasks/create",
        headers=headers,
        json={
            "name": name,
            "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 7, 10),
            "priority": priority,
        },
    )


def _make_nested_subtask(client, headers, sid, *, priority="p1", name="S1.1"):
    return client.post(
        f"/api/v3/subtasks/{sid}/subtasks/create",
        headers=headers,
        json={
            "name": name,
            "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 7, 5),
            "priority": priority,
        },
    )


# ---------------------------------------------------------------------------
# Required-on-create at every level
# ---------------------------------------------------------------------------

class TestRequiredOnCreate:
    def test_milestone_create_requires_priority(self, client, admin_user, admin_headers):
        pid, _vid = _setup(client, admin_headers)
        r = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            headers=admin_headers,
            json={
                "name": "M1",
                "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 8, 30),
                # priority omitted
            },
        )
        assert r.status_code == 422
        assert "priority" in r.text.lower()

    def test_task_create_requires_priority(self, client, admin_user, admin_headers):
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid).json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid).json()["data"]
        r = client.post(
            f"/api/v3/activities/{a['id']}/tasks/create",
            headers=admin_headers,
            json={
                "name": "T1",
                "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 7, 15),
                # priority omitted
            },
        )
        assert r.status_code == 422
        assert "priority" in r.text.lower()

    def test_subtask_create_requires_priority(self, client, admin_user, admin_headers):
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid).json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid).json()["data"]
        _publish(client, admin_headers, pid)
        t = _make_task(client, admin_headers, a["id"]).json()["data"]
        r = client.post(
            f"/api/v3/tasks/{t['id']}/subtasks/create",
            headers=admin_headers,
            json={
                "name": "S1",
                "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 7, 10),
                # priority omitted
            },
        )
        assert r.status_code == 422
        assert "priority" in r.text.lower()

    def test_nested_subtask_create_requires_priority(self, client, admin_user, admin_headers):
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid).json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid).json()["data"]
        _publish(client, admin_headers, pid)
        t = _make_task(client, admin_headers, a["id"]).json()["data"]
        s = _make_subtask(client, admin_headers, t["id"]).json()["data"]
        r = client.post(
            f"/api/v3/subtasks/{s['id']}/subtasks/create",
            headers=admin_headers,
            json={
                "name": "S1.1",
                "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 7, 5),
                # priority omitted
            },
        )
        assert r.status_code == 422
        assert "priority" in r.text.lower()


# ---------------------------------------------------------------------------
# Catalog validation — only seeded codes accepted
# ---------------------------------------------------------------------------

class TestCatalogValidation:
    def test_milestone_unknown_priority_rejected(self, client, admin_user, admin_headers):
        pid, _vid = _setup(client, admin_headers)
        r = _make_milestone(client, admin_headers, pid, priority="zz9")
        assert r.status_code == 422
        assert "priority" in r.text.lower()

    def test_task_unknown_priority_rejected(self, client, admin_user, admin_headers):
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid).json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid).json()["data"]
        _publish(client, admin_headers, pid)
        r = _make_task(client, admin_headers, a["id"], priority="zz9")
        assert r.status_code == 422

    def test_subtask_unknown_priority_rejected(self, client, admin_user, admin_headers):
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid).json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid).json()["data"]
        _publish(client, admin_headers, pid)
        t = _make_task(client, admin_headers, a["id"]).json()["data"]
        r = _make_subtask(client, admin_headers, t["id"], priority="zz9")
        assert r.status_code == 422

    def test_admin_added_code_accepted_at_every_level(
        self, client, admin_user, admin_headers,
    ):
        # Admin adds a brand-new priority code.
        rv = client.post(
            "/api/v3/master/priorities/create",
            headers=admin_headers,
            json={"code": "p9", "name": "Critical", "description": "test"},
        )
        assert rv.status_code in (200, 201), rv.text

        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid, priority="p9").json()["data"]
        assert m["priority"] == "p9"
        a = _make_activity(
            client, admin_headers, m["id"], vid, priority="p9",
        ).json()["data"]
        assert a["priority"] == "p9"
        _publish(client, admin_headers, pid)
        t = _make_task(
            client, admin_headers, a["id"], priority="p9",
        ).json()["data"]
        assert t["priority"] == "p9"
        s = _make_subtask(
            client, admin_headers, t["id"], priority="p9",
        ).json()["data"]
        assert s["priority"] == "p9"
        n = _make_nested_subtask(
            client, admin_headers, s["id"], priority="p9",
        ).json()["data"]
        assert n["priority"] == "p9"


# ---------------------------------------------------------------------------
# Independence — each level carries its own priority, no parent-child rule
# ---------------------------------------------------------------------------

class TestIndependence:
    def test_each_level_holds_its_own_priority(self, client, admin_user, admin_headers):
        """The whole point: M priority does NOT constrain A/T/S/nested.
        Build a hierarchy where every level has a different priority and
        confirm all 5 round-trip correctly."""
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid, priority="p1").json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid, priority="p2").json()["data"]
        _publish(client, admin_headers, pid)
        t = _make_task(client, admin_headers, a["id"], priority="p3").json()["data"]
        s = _make_subtask(client, admin_headers, t["id"], priority="p1").json()["data"]
        n = _make_nested_subtask(client, admin_headers, s["id"], priority="p2").json()["data"]

        # Each level kept its own priority.
        assert m["priority"] == "p1"
        assert a["priority"] == "p2"
        assert t["priority"] == "p3"
        assert s["priority"] == "p1"
        assert n["priority"] == "p2"


# ---------------------------------------------------------------------------
# PATCH updates per-level
# ---------------------------------------------------------------------------

class TestPatchUpdatesPriority:
    def test_milestone_patch_changes_priority(self, client, admin_user, admin_headers):
        pid, _vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid, priority="p1").json()["data"]
        r = client.patch(
            f"/api/v3/milestones/{m['id']}",
            headers=admin_headers, json={"priority": "p2"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["priority"] == "p2"

    def test_task_patch_changes_priority(self, client, admin_user, admin_headers):
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid).json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid).json()["data"]
        _publish(client, admin_headers, pid)
        t = _make_task(client, admin_headers, a["id"], priority="p1").json()["data"]
        r = client.patch(
            f"/api/v3/tasks/{t['id']}",
            headers=admin_headers, json={"priority": "p3"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["priority"] == "p3"

    def test_subtask_patch_changes_priority(self, client, admin_user, admin_headers):
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid).json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid).json()["data"]
        _publish(client, admin_headers, pid)
        t = _make_task(client, admin_headers, a["id"]).json()["data"]
        s = _make_subtask(client, admin_headers, t["id"], priority="p1").json()["data"]
        r = client.patch(
            f"/api/v3/subtasks/{s['id']}",
            headers=admin_headers, json={"priority": "p2"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["priority"] == "p2"

    def test_milestone_patch_unknown_priority_rejected(
        self, client, admin_user, admin_headers,
    ):
        pid, _vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid, priority="p1").json()["data"]
        r = client.patch(
            f"/api/v3/milestones/{m['id']}",
            headers=admin_headers, json={"priority": "zz9"},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Tree endpoint surfaces priority everywhere
# ---------------------------------------------------------------------------

class TestTreeSurfacesPriorityEverywhere:
    def test_tree_emits_priority_on_M_A_T_S_nested(self, client, admin_user, admin_headers):
        pid, vid = _setup(client, admin_headers)
        m = _make_milestone(client, admin_headers, pid, priority="p1").json()["data"]
        a = _make_activity(client, admin_headers, m["id"], vid, priority="p2").json()["data"]
        _publish(client, admin_headers, pid)
        t = _make_task(client, admin_headers, a["id"], priority="p3").json()["data"]
        s = _make_subtask(client, admin_headers, t["id"], priority="p1").json()["data"]
        n = _make_nested_subtask(client, admin_headers, s["id"], priority="p2").json()["data"]

        tree = client.get(
            f"/api/v3/projects/{pid}/tree", headers=admin_headers,
        ).json()["data"]
        # Walk: project -> milestones -> activities -> tasks -> subtasks -> subtasks
        assert tree["milestones"][0]["priority"] == "p1"
        assert tree["milestones"][0]["activities"][0]["priority"] == "p2"
        assert tree["milestones"][0]["activities"][0]["tasks"][0]["priority"] == "p3"
        assert tree["milestones"][0]["activities"][0]["tasks"][0]["subtasks"][0]["priority"] == "p1"
        assert tree["milestones"][0]["activities"][0]["tasks"][0]["subtasks"][0]["subtasks"][0]["priority"] == "p2"
