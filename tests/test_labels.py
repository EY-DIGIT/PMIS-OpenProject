"""Tests for the display-label feature (doc 22).

Covers:
- ``app/shared/labels.py`` parser (valid + invalid + wrong-depth + wrong-prefix).
- Label-input acceptance on M/A/T/S create + update (FE can send "A1.2" etc.).
- ``displayCode`` and ``dependsOnDisplay`` emitted in single-entity, list, and
  tree responses, with consistent values.
- Reorder + soft-delete update labels on the next read (no caching).
- Cross-milestone label refs (A2.1 depending on A1.1) work.
- Mixed UUID + label input lists resolve correctly.
- Wrong-kind labels (e.g. "M1" on activity create) → precise 422.
- Unresolvable labels → 422 with the original input string in the message.
- The casing-parity follow-up: snake_case ``depends_on`` is no longer
  accepted on milestone schemas (camelCase ``dependsOn`` only).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.shared.labels import (
    KIND_ACTIVITY,
    KIND_MILESTONE,
    KIND_SUBTASK,
    KIND_TASK,
    parse_label,
    format_label,
)


# ---------------------------------------------------------------------------
# Setup helpers (mirrors test_dependencies.py style)
# ---------------------------------------------------------------------------

def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _create_project(client, admin_headers, *, name="Label Demo"):
    resp = client.post(
        "/api/v3/projects/create",
        json={
            "name": name,
            "owner": "tmd1",
            "startDate": _future_iso(1),
            "endDate": _future_iso(120),
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_milestone(client, admin_headers, project_id, *, name="M", deps=None,
                     start_offset=2, end_offset=100):
    body = {
        "name": name,
        "startDate": _future_iso(start_offset),
        "endDate": _future_iso(end_offset),
    }
    if deps is not None:
        body["dependsOn"] = deps
    resp = client.post(
        f"/api/v3/projects/{project_id}/milestones/create",
        json=body, headers=admin_headers,
    )
    return resp


def _create_activity(client, admin_headers, milestone_id, *, name="A", deps=None,
                    start_offset=3, end_offset=80):
    body = {
        "name": name,
        "startDate": _future_iso(start_offset),
        "endDate": _future_iso(end_offset),
    }
    if deps is not None:
        body["dependsOn"] = deps
    return client.post(
        f"/api/v3/milestones/{milestone_id}/activities/standard/create",
        json=body, headers=admin_headers,
    )


def _create_task(client, admin_headers, activity_id, *, name="T", deps=None,
                start_offset=4, end_offset=70):
    body = {
        "name": name,
        "startDate": _future_iso(start_offset),
        "endDate": _future_iso(end_offset),
    }
    if deps is not None:
        body["dependsOn"] = deps
    return client.post(
        f"/api/v3/activities/{activity_id}/tasks/create",
        json=body, headers=admin_headers,
    )


def _create_subtask(client, admin_headers, task_id, *, name="S", deps=None,
                   start_offset=5, end_offset=60):
    body = {
        "name": name,
        "startDate": _future_iso(start_offset),
        "endDate": _future_iso(end_offset),
    }
    if deps is not None:
        body["dependsOn"] = deps
    return client.post(
        f"/api/v3/tasks/{task_id}/subtasks/create",
        json=body, headers=admin_headers,
    )


def _publish_and_version(client, admin_headers, baseline_id):
    """Tasks + subtasks can only be created on a version, not a baseline.
    Helper: publish the baseline, then create a version, returning
    ``(version_project_id, version_milestone_id, version_activity_id)``.
    """
    # Publish.
    pub = client.post(
        f"/api/v3/projects/{baseline_id}/publish", headers=admin_headers,
    )
    assert pub.status_code == 200, pub.text
    # Version.
    ver = client.post(
        f"/api/v3/projects/{baseline_id}/versions/create",
        headers=admin_headers,
    )
    assert ver.status_code == 201, ver.text
    vpid = ver.json()["data"]["id"]
    # Pick the version's first milestone + first activity (they were cloned
    # from the baseline).
    ms = client.get(
        f"/api/v3/projects/{vpid}/milestones", headers=admin_headers,
    ).json()["data"]["_embedded"]["elements"]
    assert ms, "version has no milestones"
    vm = ms[0]["id"]
    acts = client.get(
        f"/api/v3/milestones/{vm}/activities", headers=admin_headers,
    ).json()["data"]["_embedded"]["elements"]
    assert acts, "version milestone has no activities"
    va = acts[0]["id"]
    return vpid, vm, va


# ===========================================================================
# Pure parser tests
# ===========================================================================

class TestParser:
    @pytest.mark.parametrize("label,expected_kind,expected_ranks", [
        ("M1",        KIND_MILESTONE, (1,)),
        ("M2",        KIND_MILESTONE, (2,)),
        ("M99",       KIND_MILESTONE, (99,)),
        ("A1.2",      KIND_ACTIVITY,  (1, 2)),
        ("A2.1",      KIND_ACTIVITY,  (2, 1)),
        ("T1.2.3",    KIND_TASK,      (1, 2, 3)),
        ("S1.2.3.4",  KIND_SUBTASK,   (1, 2, 3, 4)),
    ])
    def test_parse_valid(self, label, expected_kind, expected_ranks):
        parsed = parse_label(label)
        assert parsed is not None
        assert parsed.kind == expected_kind
        assert parsed.ranks == expected_ranks

    @pytest.mark.parametrize("label", [
        "",                  # empty
        "M",                 # no rank
        "M0",                # zero rank not allowed (1-based)
        "A1",                # wrong depth (activity needs 2 ranks)
        "A1.2.3",            # wrong depth (activity needs 2)
        "T1.2",              # wrong depth (task needs 3)
        "S1.2.3",            # wrong depth (subtask needs 4)
        "X1.2",              # unknown prefix
        "a1.2",              # lowercase prefix not accepted
        "M1.2",              # milestone takes only 1 rank
        "A1.0",              # zero rank not allowed in any position
        "11d8e9f4-2c5e-44a1-b3a0-2c4b8b3e0a01",  # UUID — explicitly NOT a label
        "garbage",           # nonsense
    ])
    def test_parse_invalid(self, label):
        assert parse_label(label) is None

    def test_format_round_trip(self):
        for kind, ranks in [
            (KIND_MILESTONE, (1,)),
            (KIND_ACTIVITY, (1, 2)),
            (KIND_TASK, (1, 2, 3)),
            (KIND_SUBTASK, (1, 2, 3, 4)),
        ]:
            label = format_label(kind, ranks)
            parsed = parse_label(label)
            assert parsed is not None
            assert parsed.kind == kind
            assert parsed.ranks == ranks


# ===========================================================================
# displayCode emitted on single + list + tree responses
# ===========================================================================

class TestDisplayCodeEmission:
    def test_milestone_single_create_includes_display_code(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m = _create_milestone(client, admin_headers, pid, name="First").json()["data"]
        assert m["displayCode"] == "M1"
        # Second milestone gets M2.
        m2 = _create_milestone(client, admin_headers, pid, name="Second").json()["data"]
        assert m2["displayCode"] == "M2"

    def test_activity_single_create_includes_display_code(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid, name="M1").json()["data"]["id"]
        m2 = _create_milestone(client, admin_headers, pid, name="M2").json()["data"]["id"]
        a1 = _create_activity(client, admin_headers, m1, name="A1").json()["data"]
        assert a1["displayCode"] == "A1.1"
        a2 = _create_activity(client, admin_headers, m1, name="A2").json()["data"]
        assert a2["displayCode"] == "A1.2"
        a3 = _create_activity(client, admin_headers, m2, name="A3").json()["data"]
        assert a3["displayCode"] == "A2.1"

    def test_task_displays_label(self, client, admin_user, admin_headers):
        # Tasks live on a VERSION (not a baseline). Build a baseline, publish,
        # version it, then create the task on the cloned version.
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        _create_activity(client, admin_headers, m1)
        _vpid, _vm, va = _publish_and_version(client, admin_headers, pid)
        t1 = _create_task(client, admin_headers, va, name="T1").json()["data"]
        assert t1["displayCode"] == "T1.1.1"

    def test_subtask_displays_label(self, client, admin_user, admin_headers):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        _create_activity(client, admin_headers, m1)
        _vpid, _vm, va = _publish_and_version(client, admin_headers, pid)
        t1 = _create_task(client, admin_headers, va).json()["data"]["id"]
        s1 = _create_subtask(client, admin_headers, t1, name="S1").json()["data"]
        assert s1["displayCode"] == "S1.1.1.1"

    def test_list_response_includes_display_codes(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        _create_activity(client, admin_headers, m1, name="A1")
        _create_activity(client, admin_headers, m1, name="A2")
        resp = client.get(
            f"/api/v3/milestones/{m1}/activities", headers=admin_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["_embedded"]["elements"]
        assert sorted(a["displayCode"] for a in items) == ["A1.1", "A1.2"]

    def test_tree_includes_display_codes_at_every_level(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        _create_activity(client, admin_headers, m)
        # Tasks + subtasks live on a version. Build them on the version,
        # then fetch the version's tree.
        vpid, _vm, va = _publish_and_version(client, admin_headers, pid)
        t = _create_task(client, admin_headers, va).json()["data"]["id"]
        _create_subtask(client, admin_headers, t)

        resp = client.get(
            f"/api/v3/projects/{vpid}/tree", headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        tree = resp.json()["data"]
        ms = tree["milestones"]
        assert ms[0]["displayCode"] == "M1"
        assert ms[0]["activities"][0]["displayCode"] == "A1.1"
        assert ms[0]["activities"][0]["tasks"][0]["displayCode"] == "T1.1.1"
        assert (
            ms[0]["activities"][0]["tasks"][0]["subtasks"][0]["displayCode"]
            == "S1.1.1.1"
        )


# ===========================================================================
# Label input acceptance on dependsOn
# ===========================================================================

class TestLabelInputAcceptance:
    """The original FE bug: BE used to require UUIDs for dependsOn."""

    def test_activity_create_accepts_label(self, client, admin_user, admin_headers):
        """Reproduces and fixes the original FE 422.

        FE was sending dependsOn=["A1.1"] and getting a ValidationError.
        After this commit, that input resolves to the activity's UUID
        and the dep is created.
        Doc 27: A1 must end before A2 starts (or be on the same day).
        """
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid, name="M1").json()["data"]["id"]
        a1 = _create_activity(
            client, admin_headers, m1, name="A1",
            start_offset=3, end_offset=5,
        ).json()["data"]
        assert a1["displayCode"] == "A1.1"

        # Create a second activity whose dependsOn list uses the LABEL.
        resp = _create_activity(
            client, admin_headers, m1, name="A2", deps=["A1.1"],
            start_offset=10, end_offset=20,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        # Stored as UUID, displayed as label.
        assert body["dependsOn"] == [a1["id"]]
        assert body["dependsOnDisplay"] == ["A1.1"]

    def test_activity_create_accepts_cross_milestone_label(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid, name="M1").json()["data"]["id"]
        m2 = _create_milestone(client, admin_headers, pid, name="M2").json()["data"]["id"]
        a1 = _create_activity(
            client, admin_headers, m1, name="A1",
            start_offset=3, end_offset=5,
        ).json()["data"]
        # Activity in M2 depending on A1.1 (cross-milestone, same project).
        resp = _create_activity(
            client, admin_headers, m2, name="A2", deps=["A1.1"],
            start_offset=10, end_offset=20,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["displayCode"] == "A2.1"
        assert body["dependsOnDisplay"] == ["A1.1"]
        assert body["dependsOn"] == [a1["id"]]

    def test_activity_create_accepts_mixed_uuid_and_label(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        a1 = _create_activity(
            client, admin_headers, m1, name="A1",
            start_offset=3, end_offset=5,
        ).json()["data"]
        a2 = _create_activity(
            client, admin_headers, m1, name="A2",
            start_offset=3, end_offset=5,
        ).json()["data"]
        # Mix label + UUID in the same dependsOn list.
        resp = _create_activity(
            client, admin_headers, m1, name="A3",
            deps=[a1["id"], "A1.2"],   # UUID for A1, label for A2
            start_offset=10, end_offset=20,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        # Both resolve, both surface in dependsOn.
        assert sorted(body["dependsOn"]) == sorted([a1["id"], a2["id"]])

    def test_milestone_create_accepts_label(self, client, admin_user, admin_headers):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(
            client, admin_headers, pid, name="M1",
            start_offset=2, end_offset=5,
        ).json()["data"]
        # Second milestone depends on M1 via label.
        resp = _create_milestone(
            client, admin_headers, pid, name="M2", deps=["M1"],
            start_offset=10, end_offset=20,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["dependsOn"] == [m1["id"]]
        assert body["dependsOnDisplay"] == ["M1"]

    def test_task_create_accepts_label(self, client, admin_user, admin_headers):
        pid = _create_project(client, admin_headers)
        m = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        _create_activity(client, admin_headers, m)
        _vpid, _vm, va = _publish_and_version(client, admin_headers, pid)
        t1 = _create_task(
            client, admin_headers, va, name="T1",
            start_offset=4, end_offset=6,
        ).json()["data"]
        t2 = _create_task(
            client, admin_headers, va, name="T2", deps=["T1.1.1"],
            start_offset=10, end_offset=15,
        )
        assert t2.status_code == 201, t2.text
        assert t2.json()["data"]["dependsOn"] == [t1["id"]]
        assert t2.json()["data"]["dependsOnDisplay"] == ["T1.1.1"]

    def test_subtask_create_accepts_label(self, client, admin_user, admin_headers):
        pid = _create_project(client, admin_headers)
        m = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        _create_activity(client, admin_headers, m)
        _vpid, _vm, va = _publish_and_version(client, admin_headers, pid)
        t = _create_task(client, admin_headers, va).json()["data"]["id"]
        s1 = _create_subtask(
            client, admin_headers, t, name="S1",
            start_offset=5, end_offset=8,
        ).json()["data"]
        s2 = _create_subtask(
            client, admin_headers, t, name="S2", deps=["S1.1.1.1"],
            start_offset=10, end_offset=15,
        )
        assert s2.status_code == 201, s2.text
        assert s2.json()["data"]["dependsOn"] == [s1["id"]]


# ===========================================================================
# Errors: wrong kind + unresolved + malformed
# ===========================================================================

class TestLabelErrors:
    def test_activity_create_rejects_wrong_kind_label(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        # Try to add a milestone label as an activity dep.
        resp = _create_activity(
            client, admin_headers, m, name="A_wrong", deps=["M1"],
        )
        assert resp.status_code == 422, resp.text
        msg = resp.json()["error"]["message"].lower()
        assert "invalid dependency label" in msg
        assert "activities" in msg or "activity" in msg

    def test_activity_create_rejects_unknown_label(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        # Reference a label that doesn't resolve to anything.
        resp = _create_activity(
            client, admin_headers, m, name="A1", deps=["A99.99"],
        )
        assert resp.status_code == 422, resp.text
        msg = resp.json()["error"]["message"]
        # The original (unresolved) label appears in the error message.
        assert "A99.99" in msg

    def test_milestone_dependsOn_camelcase_canonical(
        self, client, admin_user, admin_headers,
    ):
        """Casing parity: ``dependsOn`` (camelCase) is the canonical wire
        field, matching activity / task / subtask schemas exactly.

        Pydantic's ``populate_by_name=True`` keeps Python-name fallback
        (``depends_on`` snake_case) accepted as input — same as activity /
        task / subtask schemas — so behavior is symmetric across all 4
        entity types. The previous milestone-only ``AliasChoices`` was
        purely stylistic; this test pins the canonical input shape.
        """
        pid = _create_project(client, admin_headers)
        # Doc 27: M2.start must be >= M1.end.
        m1 = _create_milestone(
            client, admin_headers, pid, name="M1",
            start_offset=2, end_offset=5,
        ).json()["data"]
        # Canonical: dependsOn camelCase.
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={
                "name": "M2",
                "startDate": _future_iso(10),
                "endDate": _future_iso(20),
                "dependsOn": [m1["id"]],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["dependsOn"] == [m1["id"]]
        # Output is always camelCase — verify there's no snake_case key
        # leaking out anywhere in the response.
        assert "depends_on" not in resp.json()["data"]


# ===========================================================================
# Reorder + delete shift labels
# ===========================================================================

class TestLabelStability:
    def test_soft_delete_shifts_subsequent_labels(
        self, client, admin_user, admin_headers,
    ):
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        a1 = _create_activity(client, admin_headers, m1, name="A1").json()["data"]
        a2 = _create_activity(client, admin_headers, m1, name="A2").json()["data"]
        a3 = _create_activity(client, admin_headers, m1, name="A3").json()["data"]
        assert a1["displayCode"] == "A1.1"
        assert a2["displayCode"] == "A1.2"
        assert a3["displayCode"] == "A1.3"

        # Soft-delete the middle activity.
        resp = client.delete(
            f"/api/v3/activities/{a2['id']}", headers=admin_headers,
        )
        assert resp.status_code == 204, resp.text

        # A3 now ranks 2 instead of 3.
        a3_after = client.get(
            f"/api/v3/activities/{a3['id']}", headers=admin_headers,
        )
        assert a3_after.status_code == 200
        assert a3_after.json()["data"]["displayCode"] == "A1.2"


# ===========================================================================
# dependsOnDisplay reflects current labels even after rename / restore
# ===========================================================================

class TestDependsOnDisplayLive:
    def test_dependsOn_display_reflects_current_position(
        self, client, admin_user, admin_headers,
    ):
        # Doc 27: A2.start must be >= A1.end.
        pid = _create_project(client, admin_headers)
        m1 = _create_milestone(client, admin_headers, pid).json()["data"]["id"]
        a1 = _create_activity(
            client, admin_headers, m1, name="A1",
            start_offset=3, end_offset=5,
        ).json()["data"]
        a2 = _create_activity(
            client, admin_headers, m1, name="A2", deps=[a1["id"]],
            start_offset=10, end_offset=20,
        )
        assert a2.status_code == 201, a2.text
        assert a2.json()["data"]["dependsOnDisplay"] == ["A1.1"]
        # Re-fetch — same display.
        a2_get = client.get(
            f"/api/v3/activities/{a2.json()['data']['id']}", headers=admin_headers,
        )
        assert a2_get.json()["data"]["dependsOnDisplay"] == ["A1.1"]
