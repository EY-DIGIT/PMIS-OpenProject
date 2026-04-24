"""Verify the cycle-detection DFS catches arbitrarily long chains.

The existing cycle check ``DependencyRepository.would_create_cycle_*``
runs a DFS from each candidate target back to the source, with a ``seen``
set guarding against revisits. By construction it handles cycles of any
length, but the existing test suite only exercises 2- and 3-node cases.

This file pushes the chain length out to verify there's no implicit cap.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.infrastructure.db.models.activity_dependency import (
    ActivityDependencyModel,
)


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _create_baseline_with_n_activities(client, admin_headers, n: int):
    """Project with n standard activities under one milestone, all on the
    baseline. Returns (project_id, milestone_id, [activity_ids])."""
    p = client.post(
        "/api/v3/projects/create",
        json={
            "name": "LongCycle",
            "owner": "admin",
            "startDate": _iso(2),
            "endDate": _iso(120),
        },
        headers=admin_headers,
    ).json()["data"]
    pid = p["id"]
    mid = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={"name": "M", "startDate": _iso(3), "endDate": _iso(80)},
        headers=admin_headers,
    ).json()["data"]["id"]
    ids = []
    for i in range(n):
        r = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json={"name": f"A{i}", "startDate": _iso(4), "endDate": _iso(20)},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["data"]["id"])
    return pid, mid, ids


def _link_chain(client, admin_headers, ids):
    """Build a linear dep chain A0 -> A1 -> A2 -> ... -> A(n-1) by
    PATCH-ing each Ai's dependsOn to [A(i+1)]. After this, A(n-1) is the
    deepest leaf with no out-edges."""
    for i in range(len(ids) - 1):
        r = client.patch(
            f"/api/v3/activities/{ids[i]}",
            json={"dependsOn": [ids[i + 1]]},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text


@pytest.mark.parametrize("chain_length", [4, 8, 15])
def test_cycle_check_rejects_back_edge_in_long_chain(
    client, admin_user, admin_headers, chain_length,
):
    """Build a chain A0 -> A1 -> ... -> A(N-1), then try to make A(N-1)
    depend on A0. That closes a cycle of length N — must be rejected."""
    _, _, ids = _create_baseline_with_n_activities(
        client, admin_headers, chain_length,
    )
    _link_chain(client, admin_headers, ids)

    # Closing the loop: A(N-1).dependsOn = [A0] → cycle of length N.
    closing_resp = client.patch(
        f"/api/v3/activities/{ids[-1]}",
        json={"dependsOn": [ids[0]]},
        headers=admin_headers,
    )
    assert closing_resp.status_code == 422, closing_resp.text
    assert "cycle" in closing_resp.json()["error"]["message"].lower()


def test_cycle_check_allows_chain_without_back_edge(
    client, admin_user, admin_headers,
):
    """Same long chain, but never closed back to A0 — must succeed."""
    _, _, ids = _create_baseline_with_n_activities(client, admin_headers, 10)
    _link_chain(client, admin_headers, ids)
    # Sanity: the deepest node really has no outgoing deps.
    last = client.get(
        f"/api/v3/activities/{ids[-1]}", headers=admin_headers,
    ).json()["data"]
    assert last["dependsOn"] == []


def test_dep_history_preserved_after_replace(
    client, admin_user, admin_headers, db_session,
):
    """Removing a dep then re-adding must leave a soft-deleted history row
    AND a fresh live row for the same (source, target) pair."""
    _, _, ids = _create_baseline_with_n_activities(client, admin_headers, 3)
    src, tgt = ids[0], ids[1]
    # Step 1: add edge.
    r1 = client.patch(
        f"/api/v3/activities/{src}",
        json={"dependsOn": [tgt]},
        headers=admin_headers,
    )
    assert r1.status_code == 200, r1.text
    # Step 2: clear all deps (soft-deletes the row).
    client.patch(
        f"/api/v3/activities/{src}",
        json={"dependsOn": []},
        headers=admin_headers,
    )
    # Step 3: re-add the same edge (fresh row, dead row stays).
    r3 = client.patch(
        f"/api/v3/activities/{src}",
        json={"dependsOn": [tgt]},
        headers=admin_headers,
    )
    assert r3.status_code == 200

    # Verify the table has 1 dead + 1 live row for (src, tgt).
    rows = (
        db_session.query(ActivityDependencyModel)
        .filter(ActivityDependencyModel.source_activity_id == src)
        .filter(ActivityDependencyModel.target_activity_id == tgt)
        .all()
    )
    assert len(rows) == 2, f"expected 2 history rows, got {len(rows)}"
    deleted = [r for r in rows if r.deleted_at is not None]
    live = [r for r in rows if r.deleted_at is None]
    assert len(deleted) == 1
    assert len(live) == 1
    # IDs differ — fresh insert, not a re-activation.
    assert deleted[0].id != live[0].id
