"""Tests for the feature additions:

- Task 2: project category 'others' + category_other
- Task 3: project vendors (and /vendors endpoint)
- Task 4: milestone status
- Task 5: milestone vendors (subset of project vendors)
- Task 6: milestone depends (pass-through)
- Task 7: activity (standard) status (dependsOn is covered by test_dependencies.py)
- Task 8: activity (resource) type_of_resource_id
- Task 9: activity (resource) division + division_other
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.infrastructure.db.models.vendor import VendorModel
from app.infrastructure.db.models.resource_type import ResourceTypeModel
from app.infrastructure.db.models.project import ProjectModel
from app.shared.project_code import generate_project_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_vendors(db_session: Session):
    """Seed two vendors the tests can reference by id."""
    v1 = VendorModel(name="Vendor A", active=True)
    v2 = VendorModel(name="Vendor B", active=True)
    db_session.add(v1)
    db_session.add(v2)
    db_session.commit()
    db_session.refresh(v1)
    db_session.refresh(v2)
    return v1.id, v2.id


def _seed_resource_types(db_session: Session):
    """Seed the three canonical resource types."""
    t1 = ResourceTypeModel(code="rfp", name="Request for Proposal", active=True)
    t2 = ResourceTypeModel(code="asg", name="Assignment", active=True)
    t3 = ResourceTypeModel(code="ccm", name="Change Control Memo", active=True)
    db_session.add_all([t1, t2, t3])
    db_session.commit()
    return t1.id, t2.id, t3.id


def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _create_project(client, headers, *, name="Demo", category=None, category_other=None,
                    category_other_reason=None, vendor_ids=None):
    body = {
        "name": name,
        "owner": "tmd1",
        "startDate": _future_iso(2),
        "endDate": _future_iso(90),
    }
    if category is not None:
        body["category"] = category
    if category_other is not None:
        body["categoryOther"] = category_other
    if category_other_reason is not None:
        body["categoryOtherReason"] = category_other_reason
    if vendor_ids is not None:
        body["vendorIds"] = vendor_ids
    return client.post("/api/v3/projects/create", json=body, headers=headers)


# ---------------------------------------------------------------------------
# Task 2: project category 'others' + category_other
# ---------------------------------------------------------------------------

class TestCategoryOthers:
    def test_others_requires_category_other(self, client, admin_user, admin_headers):
        resp = _create_project(client, admin_headers, category="others")
        assert resp.status_code == 422
        assert "categoryOther" in resp.json()["error"]["message"]

    def test_others_accepts_category_other_with_reason(self, client, admin_user, admin_headers):
        resp = _create_project(
            client, admin_headers,
            category="others",
            category_other="Partner Engagement",
            category_other_reason="Engagement spans multiple SBUs and doesn't fit MSAP/MSIP/BSP.",
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["category"] == "others"
        assert body["categoryOther"] == "Partner Engagement"
        assert body["categoryOtherReason"].startswith("Engagement spans")

    def test_others_requires_category_other_reason(self, client, admin_user, admin_headers):
        """category='others' now requires BOTH categoryOther AND categoryOtherReason."""
        resp = _create_project(
            client, admin_headers,
            category="others", category_other="Partner Engagement",
        )
        assert resp.status_code == 422
        assert "categoryOtherReason" in resp.json()["error"]["message"]

    def test_non_others_rejects_category_other(self, client, admin_user, admin_headers):
        resp = _create_project(
            client, admin_headers,
            category="MSIP", category_other="stray text",
        )
        assert resp.status_code == 422
        assert "categoryOther" in resp.json()["error"]["message"]

    def test_non_others_rejects_category_other_reason(self, client, admin_user, admin_headers):
        resp = _create_project(
            client, admin_headers,
            category="MSIP", category_other_reason="stray reason",
        )
        assert resp.status_code == 422
        assert "categoryOtherReason" in resp.json()["error"]["message"]

    def test_known_categories_still_valid(self, client, admin_user, admin_headers):
        for cat in ("MSIP", "MSAP", "BSP"):
            resp = _create_project(client, admin_headers, name=f"P-{cat}", category=cat)
            assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Vendors endpoint + Task 3: project vendors
# ---------------------------------------------------------------------------

class TestVendorsAndProjectVendors:
    def test_vendors_endpoint_lists_seeded(self, client, admin_headers, db_session):
        _seed_vendors(db_session)
        resp = client.get("/api/v3/vendors", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["data"]["_embedded"]["elements"]
        names = sorted(i["name"] for i in items)
        assert "Vendor A" in names
        assert "Vendor B" in names

    def test_admin_can_create_vendor(self, client, admin_headers):
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "Freshly Minted", "description": "demo"},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["name"] == "Freshly Minted"

    def test_project_create_attaches_vendors(self, client, admin_headers, db_session):
        v1, v2 = _seed_vendors(db_session)
        resp = _create_project(client, admin_headers, vendor_ids=[v1, v2])
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        names = sorted(v["name"] for v in body["vendors"])
        assert names == ["Vendor A", "Vendor B"]

    def test_project_create_rejects_unknown_vendor(self, client, admin_headers):
        resp = _create_project(client, admin_headers, vendor_ids=[str(uuid4())])
        assert resp.status_code == 422
        assert "vendor" in resp.json()["error"]["message"].lower()


class TestVendorContactDetails:
    """Doc 18: vendors carry email + contactPerson + phoneNumber, and a
    new GET /vendors/{id} endpoint returns the full detail (with mapped
    projects)."""

    def test_create_vendor_with_contact_details(self, client, admin_headers):
        resp = client.post(
            "/api/v3/vendors/create",
            json={
                "name": "Acme Corp",
                "description": "demo",
                "email": "ops@acme.example",
                "contactPerson": "Jane Doe",
                "phoneNumber": "+91 98765 43210",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["name"] == "Acme Corp"
        assert d["email"] == "ops@acme.example"
        assert d["contactPerson"] == "Jane Doe"
        assert d["phoneNumber"] == "+91 98765 43210"

    def test_create_vendor_rejects_invalid_email(self, client, admin_headers):
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "Bad Email", "email": "not-an-email"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_create_vendor_contact_fields_optional(self, client, admin_headers):
        """Old-style payload without contact fields still works — the
        new fields default to None and the response carries nulls."""
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "Minimal Vendor"},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["email"] is None
        assert d["contactPerson"] is None
        assert d["phoneNumber"] is None

    def test_patch_vendor_updates_contact_details(self, client, admin_headers):
        # Create with no contact info.
        c = client.post(
            "/api/v3/vendors/create",
            json={"name": "Vendor For Patch"},
            headers=admin_headers,
        ).json()["data"]
        # Patch in contact details.
        resp = client.patch(
            f"/api/v3/vendors/{c['id']}",
            json={
                "email": "hello@example.com",
                "contactPerson": "John Smith",
                "phoneNumber": "555-1212",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["email"] == "hello@example.com"
        assert d["contactPerson"] == "John Smith"
        assert d["phoneNumber"] == "555-1212"

    def test_get_vendor_by_id_returns_full_detail(self, client, admin_headers):
        c = client.post(
            "/api/v3/vendors/create",
            json={
                "name": "Detail Co",
                "description": "Used to verify GET /vendors/{id}.",
                "email": "ops@detail.example",
                "contactPerson": "Detail Lead",
                "phoneNumber": "+1 555 0000",
            },
            headers=admin_headers,
        ).json()["data"]

        resp = client.get(f"/api/v3/vendors/{c['id']}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["_type"] == "Vendor"
        assert d["id"] == c["id"]
        assert d["name"] == "Detail Co"
        assert d["description"] == "Used to verify GET /vendors/{id}."
        assert d["email"] == "ops@detail.example"
        assert d["contactPerson"] == "Detail Lead"
        assert d["phoneNumber"] == "+1 555 0000"
        # `projects` is always a list — empty here because nothing's mapped.
        assert d["projects"] == []

    def test_get_vendor_by_id_includes_mapped_projects(
        self, client, admin_headers, db_session,
    ):
        """When projects map to the vendor via the project-create vendor_ids
        flow, GET /vendors/{id} returns those projects (id + projectCode +
        name) — closed/completed/soft-deleted projects filtered out."""
        v1, _v2 = _seed_vendors(db_session)
        # Create two projects mapped to Vendor A.
        p1 = _create_project(
            client, admin_headers, name="Mapped P1", vendor_ids=[v1],
        ).json()["data"]
        p2 = _create_project(
            client, admin_headers, name="Mapped P2", vendor_ids=[v1],
        ).json()["data"]

        resp = client.get(f"/api/v3/vendors/{v1}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        names = sorted(p["name"] for p in d["projects"])
        assert names == ["Mapped P1", "Mapped P2"]
        for p in d["projects"]:
            assert p["projectCode"].startswith("UIDAI-PR")
            assert p["id"] in (p1["id"], p2["id"])

    def test_get_vendor_by_id_404_on_missing(self, client, admin_headers):
        from uuid import uuid4
        resp = client.get(
            f"/api/v3/vendors/{uuid4()}", headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_get_vendor_by_id_404_on_soft_deleted(
        self, client, admin_headers,
    ):
        c = client.post(
            "/api/v3/vendors/create",
            json={"name": "Soon Deleted"},
            headers=admin_headers,
        ).json()["data"]
        client.delete(f"/api/v3/vendors/{c['id']}", headers=admin_headers)
        resp = client.get(f"/api/v3/vendors/{c['id']}", headers=admin_headers)
        # Soft-deleted vendor is hidden from the detail endpoint — same
        # rule as the list endpoint.
        assert resp.status_code == 404

    def test_get_vendor_by_id_returns_after_restore(
        self, client, admin_headers,
    ):
        c = client.post(
            "/api/v3/vendors/create",
            json={
                "name": "Round Trip",
                "email": "rt@example.com",
                "contactPerson": "RT",
            },
            headers=admin_headers,
        ).json()["data"]
        client.delete(f"/api/v3/vendors/{c['id']}", headers=admin_headers)
        client.post(
            f"/api/v3/vendors/{c['id']}/restore", headers=admin_headers,
        )
        resp = client.get(f"/api/v3/vendors/{c['id']}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["email"] == "rt@example.com"
        assert d["contactPerson"] == "RT"

    def test_list_vendors_includes_contact_fields(self, client, admin_headers):
        client.post(
            "/api/v3/vendors/create",
            json={
                "name": "On List Co",
                "email": "on-list@example.com",
                "phoneNumber": "555-9999",
            },
            headers=admin_headers,
        )
        resp = client.get("/api/v3/vendors", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["data"]["_embedded"]["elements"]
        match = [i for i in items if i["name"] == "On List Co"]
        assert len(match) == 1
        assert match[0]["email"] == "on-list@example.com"
        assert match[0]["phoneNumber"] == "555-9999"


# ---------------------------------------------------------------------------
# Task 4, 5, 6: milestone status + vendors + depends
# ---------------------------------------------------------------------------

class TestMilestoneFields:
    def _project_with_vendors(self, client, admin_headers, db_session, vendor_ids=None):
        if vendor_ids is None:
            vendor_ids = list(_seed_vendors(db_session))
        r = _create_project(client, admin_headers, vendor_ids=vendor_ids)
        assert r.status_code == 201, r.text
        return r.json()["data"]["id"], vendor_ids

    def _milestone_body(self, **over):
        body = {
            "name": "M1",
            "startDate": _future_iso(3),
            "endDate": _future_iso(30),
        }
        body.update(over)
        return body

    def test_default_status_is_not_completed(self, client, admin_headers, db_session):
        pid, _ = self._project_with_vendors(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json=self._milestone_body(),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["status"] == "not_completed"

    def test_status_accepted(self, client, admin_headers, db_session):
        pid, _ = self._project_with_vendors(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json=self._milestone_body(status="completed"),
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["status"] == "completed"

    def test_status_invalid_rejected(self, client, admin_headers, db_session):
        pid, _ = self._project_with_vendors(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json=self._milestone_body(status="bogus"),
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_depends_passthrough(self, client, admin_headers, db_session):
        pid, _ = self._project_with_vendors(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json=self._milestone_body(depends=[str(uuid4()), str(uuid4())]),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert len(resp.json()["data"]["depends"]) == 2

    def test_milestone_vendors_must_be_subset(self, client, admin_headers, db_session):
        # Project has only vendor_a; vendor_b is NOT on the project.
        v1, v2 = _seed_vendors(db_session)
        pid, _ = self._project_with_vendors(
            client, admin_headers, db_session, vendor_ids=[v1],
        )
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json=self._milestone_body(vendorIds=[v1, v2]),
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "project" in resp.json()["error"]["message"].lower()

    def test_milestone_vendors_happy_path(self, client, admin_headers, db_session):
        v1, v2 = _seed_vendors(db_session)
        pid, _ = self._project_with_vendors(
            client, admin_headers, db_session, vendor_ids=[v1, v2],
        )
        resp = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json=self._milestone_body(vendorIds=[v1]),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert [v["id"] for v in resp.json()["data"]["vendors"]] == [v1]


# ---------------------------------------------------------------------------
# Task 7: activity (standard) status (dependency moved to test_dependencies.py)
# ---------------------------------------------------------------------------

class TestStandardActivityFields:
    def _milestone(self, client, admin_headers, db_session):
        r = _create_project(client, admin_headers)
        assert r.status_code == 201
        pid = r.json()["data"]["id"]
        mr = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={"name": "M1", "startDate": _future_iso(3), "endDate": _future_iso(30)},
            headers=admin_headers,
        )
        assert mr.status_code == 201
        return mr.json()["data"]["id"]

    def _activity_body(self, **over):
        # The split endpoints take no ``type`` field — the URL encodes it.
        body = {
            "name": "A1",
            "startDate": _future_iso(4),
            "endDate": _future_iso(20),
        }
        body.update(over)
        return body

    def test_standard_default_status(self, client, admin_headers, db_session):
        mid = self._milestone(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json=self._activity_body(),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["status"] == "not_completed"

    def test_standard_accepts_status(self, client, admin_headers, db_session):
        """status is accepted on the standard endpoint (dependsOn is covered
        by tests/test_dependencies.py)."""
        mid = self._milestone(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json=self._activity_body(status="completed"),
            headers=admin_headers,
        )
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["status"] == "completed"
        # Fresh activity has no dependencies yet.
        assert body.get("dependsOn") == []

    def test_transactional_has_no_status_field(self, client, admin_headers, db_session):
        """The transactional endpoint's schema has no ``status`` field.
        Sending one is silently ignored (Pydantic default extras="ignore"),
        and the created activity's status is NULL. This replaces the old
        'rejects status' test — the split endpoint makes the wrong
        combination structurally impossible at the contract boundary."""
        mid = self._milestone(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/transactional/create",
            json=self._activity_body(status="completed"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"].get("status") is None

    def test_standard_rejects_invalid_status(self, client, admin_headers, db_session):
        mid = self._milestone(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/standard/create",
            json=self._activity_body(status="nope"),
            headers=admin_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tasks 8, 9: activity (resource) type_of_resource_id + division/division_other
# ---------------------------------------------------------------------------

class TestResourceActivityFields:
    def _milestone(self, client, admin_headers):
        r = _create_project(client, admin_headers)
        pid = r.json()["data"]["id"]
        mr = client.post(
            f"/api/v3/projects/{pid}/milestones/create",
            json={"name": "M1", "startDate": _future_iso(3), "endDate": _future_iso(30)},
            headers=admin_headers,
        )
        return mr.json()["data"]["id"]

    def _resource_activity(self, *, type_of_resource_id=None, division="tmd1", division_other=None):
        # The split endpoint encodes type=resource + resourceMode=details
        # in the URL; body is just the payload data.
        body = {
            "name": "A-res",
            "startDate": _future_iso(4),
            "endDate": _future_iso(20),
            "resource": {
                "resourceName": "Alice",
                "typeOfResourceId": type_of_resource_id,
                "division": division,
            },
        }
        if division_other is not None:
            body["resource"]["divisionOther"] = division_other
        return body

    def test_resource_type_id_required(self, client, admin_headers, db_session):
        mid = self._milestone(client, admin_headers)
        # type_of_resource_id omitted
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json=self._resource_activity(),
            headers=admin_headers,
        )
        assert resp.status_code == 422
        # FastAPI returns a {detail: [...]} for Pydantic-layer 422; our
        # service layer returns {error: {message}}. Accept either shape.
        assert "typeOfResourceId" in resp.text

    def test_resource_type_id_must_exist(self, client, admin_headers, db_session):
        mid = self._milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json=self._resource_activity(type_of_resource_id=str(uuid4())),
            headers=admin_headers,
        )
        assert resp.status_code in (400, 422)

    def test_resource_happy_path(self, client, admin_headers, db_session):
        rfp_id, _, _ = _seed_resource_types(db_session)
        mid = self._milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json=self._resource_activity(type_of_resource_id=rfp_id, division="tmd2"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        res = resp.json()["data"]["resource"]
        assert res["typeOfResourceId"] == rfp_id
        assert res["division"] == "tmd2"
        assert res["divisionOther"] is None

    def test_division_others_requires_label(self, client, admin_headers, db_session):
        rfp_id, _, _ = _seed_resource_types(db_session)
        mid = self._milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json=self._resource_activity(type_of_resource_id=rfp_id, division="others"),
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_division_others_accepts_label(self, client, admin_headers, db_session):
        rfp_id, _, _ = _seed_resource_types(db_session)
        mid = self._milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json=self._resource_activity(
                type_of_resource_id=rfp_id, division="others", division_other="Special Projects",
            ),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        res = resp.json()["data"]["resource"]
        assert res["division"] == "others"
        assert res["divisionOther"] == "Special Projects"

    def test_non_others_rejects_label(self, client, admin_headers, db_session):
        rfp_id, _, _ = _seed_resource_types(db_session)
        mid = self._milestone(client, admin_headers)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/resource/details/create",
            json=self._resource_activity(
                type_of_resource_id=rfp_id, division="tmd1", division_other="stray",
            ),
            headers=admin_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# ResourceTypes endpoint
# ---------------------------------------------------------------------------

class TestResourceTypesEndpoint:
    def test_list_resource_types(self, client, admin_headers, db_session):
        _seed_resource_types(db_session)
        resp = client.get("/api/v3/resource_types", headers=admin_headers)
        assert resp.status_code == 200
        codes = sorted(i["code"] for i in resp.json()["data"]["_embedded"]["elements"])
        assert codes == ["asg", "ccm", "rfp"]

    def test_admin_can_create_resource_type(self, client, admin_headers, db_session):
        resp = client.post(
            "/api/v3/resource_types/create",
            json={"code": "mou", "name": "Memorandum of Understanding"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["code"] == "mou"
