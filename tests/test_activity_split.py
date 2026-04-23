"""Tests for the split-by-type activity-create endpoints.

Four endpoints replace the single catch-all ``POST .../activities/create``:
    POST /milestones/{id}/activities/standard/create
    POST /milestones/{id}/activities/resource/count/create
    POST /milestones/{id}/activities/resource/details/create
    POST /milestones/{id}/activities/transactional/create

Each schema carries only the fields its type needs. The URL encodes the
type / mode, so no type discriminator is in the body.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.models.resource_type import ResourceTypeModel


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _setup_project_and_milestone(client, headers):
    p = client.post(
        "/api/v3/projects/create",
        json={
            "name": "SplitTest",
            "owner": "admin",
            "startDate": _iso(1),
            "endDate": _iso(120),
        },
        headers=headers,
    )
    assert p.status_code == 201, p.text
    pid = p.json()["data"]["id"]
    m = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={"name": "M1", "startDate": _iso(3), "endDate": _iso(60)},
        headers=headers,
    )
    assert m.status_code == 201, m.text
    return pid, m.json()["data"]["id"]


def _seed_resource_type(db_session):
    rt = ResourceTypeModel(code="splt", name="Split-test RT", active=True)
    db_session.add(rt)
    db_session.commit()
    db_session.refresh(rt)
    return rt.id


class TestStandardSplitEndpoint:
    def test_happy_path_defaults_to_not_completed(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json={"name": "A1", "startDate": _iso(4), "endDate": _iso(20)},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["type"] == "standard"
        assert body["status"] == "not_completed"
        assert body["resourceMode"] is None
        assert body["resourceCount"] is None
        assert body["resource"] is None

    def test_accepts_status(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json={
                "name": "A1", "startDate": _iso(4), "endDate": _iso(20),
                "status": "completed",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["status"] == "completed"

    def test_rejects_invalid_status(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json={
                "name": "A1", "startDate": _iso(4), "endDate": _iso(20),
                "status": "bogus",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_accepts_depends_on(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        # First activity (target for the dep).
        r1 = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json={"name": "A-target", "startDate": _iso(4), "endDate": _iso(20)},
            headers=admin_headers,
        )
        a_target = r1.json()["data"]["id"]
        # Second activity depends on the first.
        r2 = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json={
                "name": "A-source", "startDate": _iso(4), "endDate": _iso(20),
                "dependsOn": [a_target],
            },
            headers=admin_headers,
        )
        assert r2.status_code == 201, r2.text
        assert a_target in r2.json()["data"]["dependsOn"]


class TestResourceCountSplitEndpoint:
    def test_happy_path(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/count/create",
            json={
                "name": "A-count", "startDate": _iso(4), "endDate": _iso(20),
                "resourceCount": 5,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["type"] == "resource"
        assert body["resourceMode"] == "count"
        assert body["resourceCount"] == 5
        assert body["resource"] is None
        assert body.get("status") is None

    def test_resource_count_required(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/count/create",
            json={"name": "A", "startDate": _iso(4), "endDate": _iso(20)},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "resourceCount" in resp.text

    def test_resource_count_rejects_zero(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/count/create",
            json={
                "name": "A", "startDate": _iso(4), "endDate": _iso(20),
                "resourceCount": 0,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestResourceDetailsSplitEndpoint:
    def test_happy_path(self, client, admin_user, admin_headers, db_session):
        rt_id = _seed_resource_type(db_session)
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json={
                "name": "A-details", "startDate": _iso(4), "endDate": _iso(20),
                "resource": {
                    "resourceName": "Alice",
                    "typeOfResourceId": rt_id,
                    "division": "tmd1",
                },
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["type"] == "resource"
        assert body["resourceMode"] == "details"
        assert body["resource"]["resourceName"] == "Alice"
        assert body["resource"]["typeOfResourceId"] == rt_id
        assert body["resource"]["division"] == "tmd1"

    def test_type_of_resource_id_required(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json={
                "name": "A-details", "startDate": _iso(4), "endDate": _iso(20),
                "resource": {"resourceName": "Alice", "division": "tmd1"},
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "typeOfResourceId" in resp.text

    def test_division_required(self, client, admin_user, admin_headers, db_session):
        rt_id = _seed_resource_type(db_session)
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json={
                "name": "A", "startDate": _iso(4), "endDate": _iso(20),
                "resource": {"resourceName": "Alice", "typeOfResourceId": rt_id},
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "division" in resp.text.lower()

    def test_resource_block_required(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json={"name": "A", "startDate": _iso(4), "endDate": _iso(20)},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_division_others_requires_label(self, client, admin_user, admin_headers, db_session):
        rt_id = _seed_resource_type(db_session)
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json={
                "name": "A", "startDate": _iso(4), "endDate": _iso(20),
                "resource": {
                    "resourceName": "A",
                    "typeOfResourceId": rt_id,
                    "division": "others",
                },
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestTransactionalSplitEndpoint:
    def test_happy_path(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/transactional/create",
            json={"name": "A-tx", "startDate": _iso(4), "endDate": _iso(20)},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["type"] == "transactional"
        assert body.get("status") is None
        assert body["resourceMode"] is None
        assert body["resourceCount"] is None
        assert body["resource"] is None

    def test_extra_status_silently_ignored(self, client, admin_user, admin_headers):
        """Transactional schema has no ``status`` field. Pydantic's default
        extras='ignore' discards unknown fields. The activity is created
        with status=None — the split endpoint cleans up what was previously
        a service-layer 422."""
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/transactional/create",
            json={
                "name": "A", "startDate": _iso(4), "endDate": _iso(20),
                "status": "completed",   # ignored
                "resourceCount": 3,      # ignored
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body.get("status") is None
        assert body.get("resourceCount") is None


class TestLegacyCatchAllGone:
    """The old catch-all POST .../activities/create no longer exists."""

    def test_legacy_endpoint_404s(self, client, admin_user, admin_headers):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/create",
            json={
                "name": "A", "type": "standard",
                "startDate": _iso(4), "endDate": _iso(20),
            },
            headers=admin_headers,
        )
        # FastAPI returns 404 when no route matches the path.
        assert resp.status_code in (404, 405), resp.text


class TestSharedValidationsStillApply:
    """The service-layer date rules and milestone lookup still fire
    regardless of which split endpoint was called."""

    def test_standard_rejects_start_before_project_start(
        self, client, admin_user, admin_headers,
    ):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json={
                "name": "A", "startDate": _iso(-5),  # before project start
                "endDate": _iso(20),
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_resource_count_rejects_end_before_start(
        self, client, admin_user, admin_headers,
    ):
        _, mid = _setup_project_and_milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/count/create",
            json={
                "name": "A", "startDate": _iso(20), "endDate": _iso(4),
                "resourceCount": 1,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_standard_on_version_rejected(self, client, admin_user, admin_headers):
        """The baseline-only guard still fires on the split endpoints."""
        pid, mid = _setup_project_and_milestone(client, admin_headers)
        # Publish + version.
        client.post(f"/api/v3/projects/{pid}/publish", headers=admin_headers)
        vr = client.post(
            f"/api/v3/projects/{pid}/versions/create", headers=admin_headers,
        )
        assert vr.status_code == 201, vr.text
        vid = vr.json()["data"]["id"]
        # Fetch the version's cloned milestone.
        ms = client.get(
            f"/api/v3/projects/{vid}/milestones", headers=admin_headers,
        )
        version_mid = ms.json()["data"]["_embedded"]["elements"][0]["id"]
        # Attempt to create on the version — must be rejected.
        resp = client.post(
            f"/api/v3/milestones/{version_mid}/activities/standard/create",
            json={"name": "A", "startDate": _iso(4), "endDate": _iso(20)},
            headers=admin_headers,
        )
        assert resp.status_code == 403, resp.text
