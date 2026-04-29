"""Tests for the feature additions across docs 12-18:

Doc 12-14:
- ``TestCategoryOthers``           — project category 'others' + categoryOther
- ``TestVendorsAndProjectVendors`` — vendor catalog + project_vendors mapping
- ``TestMilestoneFields``          — milestone status / depends / vendors
- ``TestStandardActivityFields``   — standard activity status
- ``TestResourceActivityFields``   — resource activity typeOfResourceId +
                                     division + divisionOther

Doc 17-18:
- ``TestVendorContactDetails``     — email / contactPerson / phoneNumber
                                     columns + GET /vendors/{id} detail
                                     endpoint + mapped projects on the
                                     vendor responses
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


class TestVendorLifecycleContracts:
    """Doc 17 vendor lifecycle contracts that weren't otherwise covered:
    newest-first sort, soft-delete name collision, the dedicated
    /vendors/{id}/projects endpoint, and closed/completed project
    filtering on the embedded `projects` array."""

    def test_list_vendors_newest_first(self, client, admin_headers):
        first  = client.post(
            "/api/v3/vendors/create",
            json={"name": "ZZZ-First-V"}, headers=admin_headers,
        ).json()["data"]
        second = client.post(
            "/api/v3/vendors/create",
            json={"name": "AAA-Second-V"}, headers=admin_headers,
        ).json()["data"]
        third  = client.post(
            "/api/v3/vendors/create",
            json={"name": "MMM-Third-V"}, headers=admin_headers,
        ).json()["data"]

        items = client.get(
            "/api/v3/vendors", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"]
        ids = [v["id"] for v in items if v["id"] in (first["id"], second["id"], third["id"])]
        # Newest-first: third came last → first in the list.
        assert ids == [third["id"], second["id"], first["id"]]

    def test_create_vendor_with_soft_deleted_name_returns_409(
        self, client, admin_headers,
    ):
        """`POST /vendors/create` against a name that exists but is
        soft-deleted should 409 with a hint to restore (doc 17 §4)."""
        c = client.post(
            "/api/v3/vendors/create",
            json={"name": "Recyclable Vendor"},
            headers=admin_headers,
        ).json()["data"]
        client.delete(f"/api/v3/vendors/{c['id']}", headers=admin_headers)

        # Same name → 409 with the restore hint.
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "Recyclable Vendor"},
            headers=admin_headers,
        )
        assert resp.status_code == 409, resp.text
        msg = resp.json()["error"]["message"].lower()
        assert "restore" in msg

    def test_get_vendor_projects_endpoint(
        self, client, admin_headers, db_session,
    ):
        """Dedicated `GET /vendors/{id}/projects` returns the live mapped
        projects (doc 17 §4)."""
        v1, _v2 = _seed_vendors(db_session)
        p = _create_project(client, admin_headers, name="VP-1", vendor_ids=[v1])
        assert p.status_code == 201
        resp = client.get(
            f"/api/v3/vendors/{v1}/projects", headers=admin_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["_embedded"]["elements"]
        names = [x["name"] for x in items]
        assert "VP-1" in names

    def test_vendor_projects_excludes_closed_projects(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Both `GET /vendors/{id}/projects` and the embedded `projects`
        array on `GET /vendors` filter out closed (and soft-deleted)
        projects (doc 17 §4 + §7). Soft-deleting a project flips its
        status to 'closed' AND drops the project_vendors mapping, so
        the project disappears from the vendor's view via either
        mechanism."""
        v1, _v2 = _seed_vendors(db_session)

        # Two live projects mapped to v1.
        live = _create_project(
            client, admin_headers, name="Live VP", vendor_ids=[v1],
        ).json()["data"]
        gone = _create_project(
            client, admin_headers, name="Soon-Closed VP", vendor_ids=[v1],
        ).json()["data"]

        # Soft-delete one (flips status to 'closed' + drops mapping).
        client.delete(f"/api/v3/projects/{gone['id']}", headers=admin_headers)

        # /vendors/{id}/projects: only the live one remains.
        scope = client.get(
            f"/api/v3/vendors/{v1}/projects", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"]
        scope_ids = {x["id"] for x in scope}
        assert live["id"] in scope_ids
        assert gone["id"] not in scope_ids

        # /vendors: same filter applies on the embedded `projects` array.
        list_items = client.get(
            "/api/v3/vendors", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"]
        v_row = [x for x in list_items if x["id"] == v1][0]
        embedded_ids = {p["id"] for p in v_row["projects"]}
        assert live["id"] in embedded_ids
        assert gone["id"] not in embedded_ids

    def test_restore_vendor_is_idempotent_on_live_vendor(
        self, client, admin_headers,
    ):
        """Restoring an already-live vendor returns 200 + the current
        snapshot rather than 409 (doc 17 §4 — idempotent)."""
        c = client.post(
            "/api/v3/vendors/create",
            json={"name": "Already Live"},
            headers=admin_headers,
        ).json()["data"]
        resp = client.post(
            f"/api/v3/vendors/{c['id']}/restore", headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["id"] == c["id"]
        assert resp.json()["data"]["deletedAt"] is None


class TestVendorProjectionShape:
    """The `projects` array must carry the same fields across all three
    vendor endpoints (GET /vendors, GET /vendors/{id}, GET /vendors/{id}/projects).
    Doc-18 §8 fix: previously the embedded array on /vendors and
    /vendors/{id} returned only {id, projectCode, name}; the dedicated
    /vendors/{id}/projects endpoint returned {_type, id, projectCode,
    name, status, createdAt}. The shape is now unified to include
    status, isVersion, versionOf, createdAt — so the FE can render
    badges + group versions without a follow-up call."""

    def _setup(self, client, admin_headers, db_session):
        v1, _v2 = _seed_vendors(db_session)
        p = _create_project(client, admin_headers, name="Shape-Probe", vendor_ids=[v1])
        assert p.status_code == 201, p.text
        return v1, p.json()["data"]

    def test_embedded_projects_on_list_carries_full_shape(
        self, client, admin_headers, db_session,
    ):
        v1, p = self._setup(client, admin_headers, db_session)
        items = client.get(
            "/api/v3/vendors", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"]
        v_row = [x for x in items if x["id"] == v1][0]
        proj_row = v_row["projects"][0]
        # New fields the FE needs.
        assert proj_row["_type"] == "Project"
        assert proj_row["status"] == "new"
        assert proj_row["isVersion"] is False
        assert proj_row["versionOf"] is None
        assert proj_row["createdAt"] and "T" in proj_row["createdAt"]

    def test_embedded_projects_on_detail_carries_full_shape(
        self, client, admin_headers, db_session,
    ):
        v1, p = self._setup(client, admin_headers, db_session)
        d = client.get(
            f"/api/v3/vendors/{v1}", headers=admin_headers,
        ).json()["data"]
        proj_row = d["projects"][0]
        assert proj_row["status"] == "new"
        assert proj_row["isVersion"] is False
        assert proj_row["createdAt"]

    def test_dedicated_projects_endpoint_uses_same_shape(
        self, client, admin_headers, db_session,
    ):
        v1, p = self._setup(client, admin_headers, db_session)
        emb = client.get(
            f"/api/v3/vendors/{v1}", headers=admin_headers,
        ).json()["data"]["projects"][0]
        scoped = client.get(
            f"/api/v3/vendors/{v1}/projects", headers=admin_headers,
        ).json()["data"]["_embedded"]["elements"][0]
        # Identical key sets across the two surfaces.
        assert set(emb.keys()) == set(scoped.keys())

    def test_version_appears_with_isVersion_true_and_versionOf_set(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Baseline + version both show up for the vendor; the version
        carries `isVersion=True` and `versionOf=<baseline_id>` so the
        FE can group them visually."""
        v1, p = self._setup(client, admin_headers, db_session)
        # Publish + create a version of the baseline.
        client.post(f"/api/v3/projects/{p['id']}/publish", headers=admin_headers)
        v_resp = client.post(
            f"/api/v3/projects/{p['id']}/versions/create", headers=admin_headers,
        )
        assert v_resp.status_code == 201, v_resp.text
        version = v_resp.json()["data"]

        items = client.get(
            f"/api/v3/vendors/{v1}", headers=admin_headers,
        ).json()["data"]["projects"]
        # Both baseline + version are mapped (version inherits the vendor).
        ids = {x["id"] for x in items}
        assert p["id"] in ids
        assert version["id"] in ids
        # Identify each row.
        baseline_row = [x for x in items if x["id"] == p["id"]][0]
        version_row  = [x for x in items if x["id"] == version["id"]][0]
        assert baseline_row["isVersion"] is False
        assert baseline_row["versionOf"] is None
        assert version_row["isVersion"] is True
        assert version_row["versionOf"] == p["id"]


class TestCreateVendorWithProjects:
    """`POST /vendors/create` accepts `projectIds` to assign mappings
    from the vendor side at creation time (doc 18 §9).  Each id is
    validated: must exist, not be soft-deleted, not be closed/completed."""

    def _make_active_project(self, client, admin_headers, *, name):
        return _create_project(client, admin_headers, name=name).json()["data"]

    def test_create_with_projectIds_attaches_mapping(
        self, client, admin_user, admin_headers, db_session,
    ):
        p1 = self._make_active_project(client, admin_headers, name="VP-A")
        p2 = self._make_active_project(client, admin_headers, name="VP-B")
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-with-projects", "projectIds": [p1["id"], p2["id"]]},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        names = sorted(p["name"] for p in d["projects"])
        assert names == ["VP-A", "VP-B"]

    def test_create_with_empty_projectIds_attaches_nothing(
        self, client, admin_headers,
    ):
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-empty-list", "projectIds": []},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["projects"] == []

    def test_create_with_unknown_project_id_returns_422(
        self, client, admin_headers,
    ):
        from uuid import uuid4
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-bad-id", "projectIds": [str(uuid4())]},
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        assert "unknown project" in resp.json()["error"]["message"].lower()

    def test_create_rejects_closed_project_id(
        self, client, admin_user, admin_headers,
    ):
        """Closed projects are not 'active' — the FE picker should never
        offer them but we double-check on the BE."""
        p = self._make_active_project(client, admin_headers, name="VP-Soon-Closed")
        # Drive the project to 'closed' status.
        client.post(f"/api/v3/projects/{p['id']}/publish", headers=admin_headers)
        cl = client.post(
            f"/api/v3/projects/{p['id']}/close", headers=admin_headers,
        )
        assert cl.status_code == 200, cl.text
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-tries-closed", "projectIds": [p["id"]]},
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        assert "closed" in resp.json()["error"]["message"].lower()

    def test_create_rejects_soft_deleted_project_id(
        self, client, admin_user, admin_headers,
    ):
        p = self._make_active_project(client, admin_headers, name="VP-Soon-Deleted")
        client.delete(f"/api/v3/projects/{p['id']}", headers=admin_headers)
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-tries-deleted", "projectIds": [p["id"]]},
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text

    def test_create_dedupes_repeated_project_ids(
        self, client, admin_user, admin_headers,
    ):
        p = self._make_active_project(client, admin_headers, name="VP-Once")
        resp = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-dupe", "projectIds": [p["id"], p["id"], p["id"]]},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        # Only one mapping row.
        assert len(resp.json()["data"]["projects"]) == 1

    def test_create_then_project_side_query_sees_the_mapping(
        self, client, admin_user, admin_headers,
    ):
        """Bidirectional: a vendor created with projectIds should also
        show up on the project's `vendors` field via GET /projects/{id}."""
        p = self._make_active_project(client, admin_headers, name="VP-Bidir")
        v = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-bidir", "projectIds": [p["id"]]},
            headers=admin_headers,
        ).json()["data"]
        proj_resp = client.get(
            f"/api/v3/projects/{p['id']}", headers=admin_headers,
        )
        assert proj_resp.status_code == 200
        vendors = proj_resp.json()["data"]["vendors"]
        assert any(x["id"] == v["id"] for x in vendors)


class TestPatchVendorWithProjects:
    """PATCH semantics for `projectIds`: omitted leaves mapping unchanged;
    [] clears; non-empty list replaces."""

    def test_patch_replaces_full_project_list(
        self, client, admin_user, admin_headers,
    ):
        p1 = _create_project(client, admin_headers, name="VP-1").json()["data"]
        p2 = _create_project(client, admin_headers, name="VP-2").json()["data"]
        v = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-replace", "projectIds": [p1["id"]]},
            headers=admin_headers,
        ).json()["data"]
        # Replace with a different project.
        resp = client.patch(
            f"/api/v3/vendors/{v['id']}",
            json={"projectIds": [p2["id"]]},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        names = [x["name"] for x in resp.json()["data"]["projects"]]
        assert names == ["VP-2"]

    def test_patch_empty_list_clears_projects(
        self, client, admin_user, admin_headers,
    ):
        p = _create_project(client, admin_headers, name="VP-clear").json()["data"]
        v = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-clear", "projectIds": [p["id"]]},
            headers=admin_headers,
        ).json()["data"]
        resp = client.patch(
            f"/api/v3/vendors/{v['id']}",
            json={"projectIds": []},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["projects"] == []

    def test_patch_omitting_projectIds_leaves_mapping_unchanged(
        self, client, admin_user, admin_headers,
    ):
        p = _create_project(client, admin_headers, name="VP-keep").json()["data"]
        v = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-keep", "projectIds": [p["id"]]},
            headers=admin_headers,
        ).json()["data"]
        # PATCH some other field; mapping should survive.
        resp = client.patch(
            f"/api/v3/vendors/{v['id']}",
            json={"description": "new description"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]["projects"]) == 1

    def test_patch_invalid_project_id_returns_422(
        self, client, admin_user, admin_headers,
    ):
        from uuid import uuid4
        v = client.post(
            "/api/v3/vendors/create",
            json={"name": "V-bad-patch"},
            headers=admin_headers,
        ).json()["data"]
        resp = client.patch(
            f"/api/v3/vendors/{v['id']}",
            json={"projectIds": [str(uuid4())]},
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text


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

    def test_transactional_accepts_status(self, client, admin_headers, db_session):
        """``status`` now applies to all activity types — transactional
        included. Earlier behaviour silently dropped or 422'd it; now it
        persists. The dependency-completion gate keys on
        ``status='completed'`` regardless of activity type."""
        mid = self._milestone(client, admin_headers, db_session)
        resp = client.post(
            f"/api/v3/milestones/{mid}/activities/transactional/create",
            json=self._activity_body(status="completed"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["status"] == "completed"

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
