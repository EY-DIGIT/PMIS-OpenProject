"""Tests for the consolidated master-data router (doc 20).

Covers full CRUD on each catalog under ``/api/v3/master/*``:

- divisions                  (GET / POST / PATCH / DELETE / restore)
- project_status_transitions (GET / POST / PATCH / DELETE / restore)
- resource_types             (GET / POST / PATCH / DELETE / restore)
- vendors                    (delegates to /api/v3/vendors handlers)

Plus negative-path coverage that the doc-20 design hinges on:

- Built-in protection: PATCH / DELETE on ``tmd1`` / ``tmd2`` / ``others``
  divisions returns 403 (they back the strict-division validator on
  every project / user / activity-resource create).
- Auto-insert removal: creating a project with ``owner='others'`` +
  ``ownerOther='Foo'`` no longer adds a row to the divisions catalog.
- Deprecation header: the legacy endpoints (`/api/v3/divisions`,
  `/api/v3/resource_types`, `/api/v3/project_status_transitions`,
  `/api/v3/vendors`) stamp ``Deprecation: true`` + ``Link`` pointing
  at the master-data successor.
- project_owners: the legacy endpoints return 404 (router removed).

See [planned_changes/20.*.md](../planned_changes) for the design.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.infrastructure.db.models.division import DivisionModel
from app.infrastructure.db.models.project_status_transition import (
    ProjectStatusTransitionModel,
)
from app.infrastructure.db.models.resource_type import ResourceTypeModel


def _iso(days: int) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(days=days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Built-in seeds — the master_data router falls back to defaults but tests
# need explicit rows for the negative paths.
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_builtin_divisions(db_session):
    """Seed the three built-in division rows the way init_db would."""
    for code, label, requires_other in (
        ("tmd1", "TMD1", False),
        ("tmd2", "TMD2", False),
        ("others", "Others", True),
    ):
        db_session.add(DivisionModel(
            code=code, label=label,
            is_builtin=True, requires_other=requires_other, active=True,
        ))
    db_session.commit()


@pytest.fixture
def seed_resource_types(db_session):
    """Seed the three real resource-type rows."""
    rows = []
    for code, name in (
        ("asg", "Assignment"),
        ("ccn", "Change Control Notice"),
        ("rfp", "Request for Proposal"),
    ):
        m = ResourceTypeModel(code=code, name=name, active=True)
        db_session.add(m)
        rows.append(m)
    db_session.commit()
    for r in rows:
        db_session.refresh(r)
    return rows


# ===========================================================================
# Divisions
# ===========================================================================

class TestMasterDivisionsList:
    def test_list_returns_active_only_by_default(
        self, client, admin_headers, seed_builtin_divisions, db_session,
    ):
        # Add one inactive row.
        db_session.add(DivisionModel(
            code="legacy", label="Legacy", is_builtin=False,
            requires_other=False, active=False,
        ))
        db_session.commit()

        resp = client.get("/api/v3/master/divisions", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        codes = [r["code"] for r in resp.json()["data"]["_embedded"]["elements"]]
        assert "legacy" not in codes
        assert "tmd1" in codes

    def test_list_with_include_inactive_includes_deactivated_rows(
        self, client, admin_headers, seed_builtin_divisions, db_session,
    ):
        db_session.add(DivisionModel(
            code="legacy", label="Legacy", is_builtin=False,
            requires_other=False, active=False,
        ))
        db_session.commit()
        resp = client.get(
            "/api/v3/master/divisions?include_inactive=true",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["_embedded"]["elements"]
        codes = [r["code"] for r in items]
        assert "legacy" in codes
        legacy = [r for r in items if r["code"] == "legacy"][0]
        assert legacy["active"] is False

    def test_list_does_not_stamp_deprecation(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.get("/api/v3/master/divisions", headers=admin_headers)
        # Master-data IS the successor — must NOT carry the deprecation
        # marker that the legacy endpoint emits.
        assert "deprecation" not in {k.lower() for k in resp.headers.keys()}


class TestMasterDivisionsCreate:
    def test_admin_can_create_with_explicit_code(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.post(
            "/api/v3/master/divisions/create",
            headers=admin_headers,
            json={"code": "engineering", "label": "Engineering"},
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["code"] == "engineering"
        assert d["label"] == "Engineering"
        assert d["isBuiltin"] is False
        assert d["requiresOther"] is False
        assert d["active"] is True

    def test_create_derives_code_from_label_when_omitted(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.post(
            "/api/v3/master/divisions/create",
            headers=admin_headers,
            json={"label": "Field Operations"},
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["code"] == "field_operations"

    def test_create_rejects_duplicate_code(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        # tmd1 already exists.
        resp = client.post(
            "/api/v3/master/divisions/create",
            headers=admin_headers,
            json={"code": "tmd1", "label": "Whatever"},
        )
        assert resp.status_code == 409, resp.text

    def test_member_cannot_create(
        self, client, member_headers, seed_builtin_divisions,
    ):
        resp = client.post(
            "/api/v3/master/divisions/create",
            headers=member_headers,
            json={"label": "Engineering"},
        )
        assert resp.status_code == 403, resp.text


class TestMasterDivisionsUpdate:
    def test_admin_can_update_label(
        self, client, admin_headers, seed_builtin_divisions, db_session,
    ):
        db_session.add(DivisionModel(
            code="engineering", label="Engineering",
            is_builtin=False, requires_other=False, active=True,
        ))
        db_session.commit()
        resp = client.patch(
            "/api/v3/master/divisions/engineering",
            headers=admin_headers,
            json={"label": "Engineering & R&D"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["label"] == "Engineering & R&D"
        # Code is unchanged.
        assert resp.json()["data"]["code"] == "engineering"

    def test_patch_builtin_returns_403(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.patch(
            "/api/v3/master/divisions/tmd1",
            headers=admin_headers,
            json={"label": "Renamed"},
        )
        assert resp.status_code == 403, resp.text

    def test_patch_unknown_returns_404(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.patch(
            "/api/v3/master/divisions/no_such_code",
            headers=admin_headers,
            json={"label": "x"},
        )
        assert resp.status_code == 404


class TestMasterDivisionsDelete:
    def test_admin_can_soft_delete_user_added_row(
        self, client, admin_headers, seed_builtin_divisions, db_session,
    ):
        db_session.add(DivisionModel(
            code="engineering", label="Engineering",
            is_builtin=False, requires_other=False, active=True,
        ))
        db_session.commit()
        resp = client.delete(
            "/api/v3/master/divisions/engineering",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["active"] is False

        # Default list now hides it.
        list_resp = client.get(
            "/api/v3/master/divisions", headers=admin_headers,
        )
        codes = [r["code"] for r in list_resp.json()["data"]["_embedded"]["elements"]]
        assert "engineering" not in codes

    def test_delete_builtin_returns_403(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.delete(
            "/api/v3/master/divisions/tmd1",
            headers=admin_headers,
        )
        assert resp.status_code == 403, resp.text

    def test_restore_brings_row_back(
        self, client, admin_headers, seed_builtin_divisions, db_session,
    ):
        db_session.add(DivisionModel(
            code="engineering", label="Engineering",
            is_builtin=False, requires_other=False, active=False,
        ))
        db_session.commit()
        resp = client.post(
            "/api/v3/master/divisions/engineering/restore",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["active"] is True


class TestMasterDivisionsContactDetails:
    """Email + phoneNumber on divisions (mirrors the vendors pattern)."""

    def test_response_carries_email_and_phone_keys(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        # Even on rows that never had contact details set, the response
        # exposes both keys (with null values) so the FE doesn't have to
        # branch on key-presence.
        resp = client.get("/api/v3/master/divisions", headers=admin_headers)
        assert resp.status_code == 200
        for row in resp.json()["data"]["_embedded"]["elements"]:
            assert "email" in row
            assert "phoneNumber" in row

    def test_create_with_email_and_phone(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.post(
            "/api/v3/master/divisions/create",
            headers=admin_headers,
            json={
                "code": "platform",
                "label": "Platform Engineering",
                "email": "platform@uidai.example",
                "phoneNumber": "+91 80 1234 5678",
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["email"] == "platform@uidai.example"
        assert d["phoneNumber"] == "+91 80 1234 5678"

    def test_create_email_validation(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.post(
            "/api/v3/master/divisions/create",
            headers=admin_headers,
            json={
                "code": "bogus",
                "label": "Bogus",
                "email": "not-an-email",
            },
        )
        assert resp.status_code == 422, resp.text

    def test_create_without_contact_details_leaves_nulls(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.post(
            "/api/v3/master/divisions/create",
            headers=admin_headers,
            json={"code": "qa", "label": "QA"},
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["email"] is None
        assert d["phoneNumber"] is None

    def test_patch_email_and_phone_on_user_added_row(
        self, client, admin_headers, seed_builtin_divisions, db_session,
    ):
        db_session.add(DivisionModel(
            code="qa", label="QA",
            is_builtin=False, requires_other=False, active=True,
        ))
        db_session.commit()
        resp = client.patch(
            "/api/v3/master/divisions/qa",
            headers=admin_headers,
            json={"email": "qa@uidai.example", "phoneNumber": "+91 80 9999 0000"},
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["email"] == "qa@uidai.example"
        assert d["phoneNumber"] == "+91 80 9999 0000"

    def test_patch_email_on_builtin_succeeds(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        # Built-ins accept contact-detail patches but reject label /
        # requiresOther changes. Admins need to be able to attach a
        # mailbox / hotline to TMD1, TMD2, etc.
        resp = client.patch(
            "/api/v3/master/divisions/tmd1",
            headers=admin_headers,
            json={"email": "tmd1@uidai.example", "phoneNumber": "+91 80 1111 1111"},
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["email"] == "tmd1@uidai.example"
        assert d["phoneNumber"] == "+91 80 1111 1111"
        # Built-in flag unchanged.
        assert d["isBuiltin"] is True

    def test_patch_label_on_builtin_still_403(
        self, client, admin_headers, seed_builtin_divisions,
    ):
        resp = client.patch(
            "/api/v3/master/divisions/tmd1",
            headers=admin_headers,
            json={"label": "Renamed", "email": "x@y.example"},
        )
        # Even though email is fine, the label change on a built-in
        # row is rejected and the whole patch fails atomically.
        assert resp.status_code == 403, resp.text

    def test_patch_empty_string_clears_stored_contact(
        self, client, admin_headers, seed_builtin_divisions, db_session,
    ):
        db_session.add(DivisionModel(
            code="qa", label="QA",
            is_builtin=False, requires_other=False, active=True,
            email="qa@uidai.example", phone_number="+91 80 9999 0000",
        ))
        db_session.commit()
        resp = client.patch(
            "/api/v3/master/divisions/qa",
            headers=admin_headers,
            json={"email": "", "phoneNumber": ""},
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["email"] is None
        assert d["phoneNumber"] is None

    def test_patch_omitting_contact_keys_leaves_them_alone(
        self, client, admin_headers, seed_builtin_divisions, db_session,
    ):
        db_session.add(DivisionModel(
            code="qa", label="QA",
            is_builtin=False, requires_other=False, active=True,
            email="qa@uidai.example", phone_number="+91 80 9999 0000",
        ))
        db_session.commit()
        resp = client.patch(
            "/api/v3/master/divisions/qa",
            headers=admin_headers,
            json={"label": "QA Renamed"},
        )
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["label"] == "QA Renamed"
        # Email + phoneNumber unchanged.
        assert d["email"] == "qa@uidai.example"
        assert d["phoneNumber"] == "+91 80 9999 0000"


# ===========================================================================
# Project status transitions
# ===========================================================================

class TestMasterTransitionsCRUD:
    def test_list_returns_seeded_rows(
        self, client, admin_headers, db_session,
    ):
        db_session.add(ProjectStatusTransitionModel(
            from_status="new", to_status="draft",
            requires_admin=False, active=True,
        ))
        db_session.commit()
        resp = client.get(
            "/api/v3/master/project_status_transitions",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]["_embedded"]["elements"]
        edges = {(r["fromStatus"], r["toStatus"]) for r in rows}
        assert ("new", "draft") in edges

    def test_create_new_transition(self, client, admin_headers):
        resp = client.post(
            "/api/v3/master/project_status_transitions/create",
            headers=admin_headers,
            json={
                "fromStatus": "draft",
                "toStatus": "review",
                "requiresAdmin": True,
                "description": "Submit for review",
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["fromStatus"] == "draft"
        assert d["toStatus"] == "review"
        assert d["requiresAdmin"] is True

    def test_create_duplicate_edge_returns_409(
        self, client, admin_headers, db_session,
    ):
        db_session.add(ProjectStatusTransitionModel(
            from_status="new", to_status="draft",
            requires_admin=False, active=True,
        ))
        db_session.commit()
        resp = client.post(
            "/api/v3/master/project_status_transitions/create",
            headers=admin_headers,
            json={"fromStatus": "new", "toStatus": "draft"},
        )
        assert resp.status_code == 409, resp.text

    def test_update_patches_policy_flags(
        self, client, admin_headers, db_session,
    ):
        row = ProjectStatusTransitionModel(
            from_status="new", to_status="published",
            requires_admin=False, active=True,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        resp = client.patch(
            f"/api/v3/master/project_status_transitions/{row.id}",
            headers=admin_headers,
            json={"requiresAdmin": True, "description": "Admin only"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["requiresAdmin"] is True
        assert resp.json()["data"]["description"] == "Admin only"

    def test_delete_then_restore(
        self, client, admin_headers, db_session,
    ):
        row = ProjectStatusTransitionModel(
            from_status="x", to_status="y",
            requires_admin=False, active=True,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        rid = row.id

        del_resp = client.delete(
            f"/api/v3/master/project_status_transitions/{rid}",
            headers=admin_headers,
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["data"]["active"] is False

        restore_resp = client.post(
            f"/api/v3/master/project_status_transitions/{rid}/restore",
            headers=admin_headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["data"]["active"] is True

    def test_member_cannot_modify(
        self, client, member_headers,
    ):
        resp = client.post(
            "/api/v3/master/project_status_transitions/create",
            headers=member_headers,
            json={"fromStatus": "draft", "toStatus": "review"},
        )
        assert resp.status_code == 403


# ===========================================================================
# Resource types
# ===========================================================================

class TestMasterResourceTypesCRUD:
    def test_list_returns_active(
        self, client, admin_headers, seed_resource_types,
    ):
        resp = client.get(
            "/api/v3/master/resource_types", headers=admin_headers,
        )
        assert resp.status_code == 200
        codes = [r["code"] for r in resp.json()["data"]["_embedded"]["elements"]]
        assert sorted(codes) == ["asg", "ccn", "rfp"]

    def test_create_new_type(self, client, admin_headers):
        resp = client.post(
            "/api/v3/master/resource_types/create",
            headers=admin_headers,
            json={"code": "po", "name": "Purchase Order"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["code"] == "po"

    def test_create_duplicate_code_returns_409(
        self, client, admin_headers, seed_resource_types,
    ):
        resp = client.post(
            "/api/v3/master/resource_types/create",
            headers=admin_headers,
            json={"code": "asg", "name": "Whatever"},
        )
        assert resp.status_code == 409

    def test_update_renames(
        self, client, admin_headers, seed_resource_types,
    ):
        rt = seed_resource_types[0]
        resp = client.patch(
            f"/api/v3/master/resource_types/{rt.id}",
            headers=admin_headers,
            json={"name": "Assignment (renamed)"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["name"] == "Assignment (renamed)"
        # Code is unchanged.
        assert resp.json()["data"]["code"] == "asg"

    def test_delete_then_restore(
        self, client, admin_headers, seed_resource_types,
    ):
        rt = seed_resource_types[0]
        del_resp = client.delete(
            f"/api/v3/master/resource_types/{rt.id}",
            headers=admin_headers,
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["data"]["active"] is False
        restore_resp = client.post(
            f"/api/v3/master/resource_types/{rt.id}/restore",
            headers=admin_headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["data"]["active"] is True

    def test_member_cannot_create(self, client, member_headers):
        resp = client.post(
            "/api/v3/master/resource_types/create",
            headers=member_headers,
            json={"code": "po", "name": "Purchase Order"},
        )
        assert resp.status_code == 403


# ===========================================================================
# Vendors (delegates to existing handlers)
# ===========================================================================

class TestMasterVendorsCRUD:
    def test_admin_can_list(self, client, admin_headers):
        resp = client.get("/api/v3/master/vendors", headers=admin_headers)
        assert resp.status_code == 200
        # Master-data IS the successor — must NOT carry deprecation.
        assert "deprecation" not in {k.lower() for k in resp.headers.keys()}

    def test_admin_can_create_then_get(self, client, admin_headers):
        resp = client.post(
            "/api/v3/master/vendors/create",
            headers=admin_headers,
            json={
                "name": "Acme Corp",
                "description": "Test vendor",
                "email": "ops@acme.example",
                "contactPerson": "Jane Doe",
                "phoneNumber": "+91 80 1234 5678",
            },
        )
        assert resp.status_code == 201, resp.text
        vendor_id = resp.json()["data"]["id"]

        get_resp = client.get(
            f"/api/v3/master/vendors/{vendor_id}", headers=admin_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["name"] == "Acme Corp"
        # Deprecation header is stripped when delegating.
        assert "deprecation" not in {k.lower() for k in get_resp.headers.keys()}

    def test_admin_can_soft_delete_then_restore(
        self, client, admin_headers,
    ):
        create = client.post(
            "/api/v3/master/vendors/create",
            headers=admin_headers,
            json={"name": "Acme Corp", "phoneNumber": "9876543210"},
        )
        vendor_id = create.json()["data"]["id"]

        del_resp = client.delete(
            f"/api/v3/master/vendors/{vendor_id}", headers=admin_headers,
        )
        # 204 No Content per the legacy handler shape.
        assert del_resp.status_code in (200, 204)

        restore_resp = client.post(
            f"/api/v3/master/vendors/{vendor_id}/restore",
            headers=admin_headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["data"]["deletedAt"] is None

    def test_member_cannot_create(self, client, member_headers):
        resp = client.post(
            "/api/v3/master/vendors/create",
            headers=member_headers,
            json={"name": "Acme Corp"},
        )
        assert resp.status_code == 403


# ===========================================================================
# Auto-insert removal — the key Part-1 behavioural change in doc 20
# ===========================================================================

class TestOwnerOtherDoesNotPolluteDivisionsCatalog:
    """Project create/update/upsert with owner='others' + ownerOther='Foo'
    no longer auto-inserts a row into the divisions catalog. The label
    stays on the project row only. Repeats one of the assertions in
    test_catalogs_and_other_reason.py for completeness in this test file
    too — auto-insert removal is a core Part-1 contract of doc 20."""

    def test_create_with_owner_other_leaves_catalog_unchanged(
        self, client, admin_user, admin_headers, db_session,
    ):
        # Seed the minimum status transitions and division built-ins.
        db_session.add(ProjectStatusTransitionModel(
            from_status=None, to_status="new",
            requires_admin=False, active=True,
        ))
        db_session.commit()

        before = client.get(
            "/api/v3/master/divisions?include_inactive=true",
            headers=admin_headers,
        )
        before_codes = sorted(
            r["code"] for r in before.json()["data"]["_embedded"]["elements"]
        )

        resp = client.post(
            "/api/v3/projects/create",
            headers=admin_headers,
            json={
                "name": "P", "owner": "others", "ownerOther": "Marketing",
                "status": "new",
                "startDate": _iso(2), "endDate": _iso(60),
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["ownerOther"] == "Marketing"

        after = client.get(
            "/api/v3/master/divisions?include_inactive=true",
            headers=admin_headers,
        )
        after_codes = sorted(
            r["code"] for r in after.json()["data"]["_embedded"]["elements"]
        )
        assert after_codes == before_codes, (
            f"divisions catalog changed unexpectedly: {before_codes} -> {after_codes}"
        )


# ===========================================================================
# Legacy endpoint deprecation + project_owners removal
# ===========================================================================

class TestLegacyEndpointsStillRespond:
    """Legacy reads continue to work but stamp Deprecation headers
    pointing at their /api/v3/master/* successor."""

    def test_legacy_divisions_get_carries_deprecation(
        self, client, admin_headers,
    ):
        resp = client.get("/api/v3/divisions", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"
        assert "/api/v3/master/divisions" in resp.headers.get("Link", "")

    def test_legacy_resource_types_get_carries_deprecation(
        self, client, admin_headers,
    ):
        resp = client.get("/api/v3/resource_types", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"
        assert "/api/v3/master/resource_types" in resp.headers.get("Link", "")

    def test_legacy_project_status_transitions_get_carries_deprecation(
        self, client, admin_headers,
    ):
        resp = client.get(
            "/api/v3/project_status_transitions", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"

    def test_legacy_vendors_get_carries_deprecation(
        self, client, admin_headers,
    ):
        resp = client.get("/api/v3/vendors", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.headers.get("Deprecation") == "true"


class TestProjectOwnersRouterRemoved:
    """The /api/v3/project_owners endpoints were removed entirely in
    doc 20 along with the underlying table. Hits return 404."""

    def test_get_project_owners_404(self, client, admin_headers):
        resp = client.get("/api/v3/project_owners", headers=admin_headers)
        assert resp.status_code == 404

    def test_post_project_owners_create_404(self, client, admin_headers):
        resp = client.post(
            "/api/v3/project_owners/create",
            headers=admin_headers,
            json={"login": "admin"},
        )
        assert resp.status_code == 404

    def test_delete_project_owners_404(
        self, client, admin_user, admin_headers,
    ):
        resp = client.delete(
            f"/api/v3/project_owners/{admin_user.id}", headers=admin_headers,
        )
        assert resp.status_code == 404
