"""End-to-end tests for doc 25 — human-readable Vendor + User codes.

Covers:
  - Vendor create stamps a ``vendorCode`` in ``VN-XXXX-YYMMDDHHMMSS`` format.
  - Vendor lookup endpoints accept either UUID or vendor code (auto-detect).
  - User create stamps a ``userCode`` in ``US-XXXX-YYMMDDHHMMSS`` format.
  - User lookup endpoints accept either integer id or user code (auto-detect).
  - Cross-entity vendor input acceptance:
      * POST /users/create   — ``vendorId`` accepts UUID or VN-... code
      * POST /projects/create — ``vendorIds`` entries can be either form
      * Mixed (UUID + code in same list) works and rejects unknown tokens.
  - Backfill helper writes ``vendor_code`` for legacy rows missing it.
"""
import re
from uuid import uuid4

import pytest

from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.vendor import VendorModel


# ---------------------------------------------------------------------------
# Helpers + local fixtures
# ---------------------------------------------------------------------------

# Format check: prefix-{4 alphanum slug}-{12 digit IST timestamp} optionally
# followed by ``-N`` collision suffix.
_VENDOR_CODE_RE = re.compile(r"^VN-[A-Z0-9]{4}-\d{12}(-\d+)?$")
_USER_CODE_RE = re.compile(r"^US-[A-Z0-9]{4}-\d{12}(-\d+)?$")


def _create_vendor(client, headers, *, name=None, phone="+91 98765 43210"):
    """Create a vendor via the public endpoint and return the response body."""
    body = {
        "name": name or f"Vendor-{uuid4().hex[:6]}",
        "description": "doc25 test vendor",
        "phoneNumber": phone,
    }
    resp = client.post("/api/v3/vendors/create", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _seed_project(db_session):
    """Drop a live project row so user-create's projectIds picker has a target."""
    p = ProjectModel(
        id=str(uuid4()),
        project_code=f"UIDAI-PR{uuid4().hex[:14].upper()}",
        name="doc25 project",
        description="-",
        active=True,
        public=False,
        status="new",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _user_body(*, vendor_ref, project_ids, login=None,
               email=None, division="tmd1"):
    """Build a valid POST /users/create payload."""
    suffix = uuid4().hex[:6]
    return {
        "login": login or f"user-{suffix}",
        "email": email or f"u{suffix}@example.com",
        "password": "password123",
        "firstName": "Doc",
        "lastName": "Twentyfive",
        "admin": False,
        "vendorId": vendor_ref,
        "division": division,
        "projectIds": list(project_ids),
        "phoneNumber": "+91 98765 43210",
    }


# ===========================================================================
# Vendor side
# ===========================================================================

class TestVendorCodeOnCreate:
    """POST /vendors/create stamps a vendorCode in the response."""

    def test_response_includes_vendor_code(self, client, admin_user, admin_headers):
        body = _create_vendor(client, admin_headers, name="Acme Corp")
        assert "vendorCode" in body
        assert body["vendorCode"] is not None
        assert _VENDOR_CODE_RE.match(body["vendorCode"]), body["vendorCode"]

    def test_slug_derived_from_first_4_uppercased(
        self, client, admin_user, admin_headers,
    ):
        body = _create_vendor(client, admin_headers, name="Acme Corporation Pvt Ltd")
        # First 4 alphanum of "Acme Corporation Pvt Ltd" → "ACME"
        assert body["vendorCode"].startswith("VN-ACME-")

    def test_short_name_padded_with_zeros(
        self, client, admin_user, admin_headers,
    ):
        body = _create_vendor(client, admin_headers, name="z")
        assert body["vendorCode"].startswith("VN-Z000-")

    def test_collision_suffix_via_repo(self, db_session):
        """Vendors with the SAME name are blocked by the
        ``vendors.name`` UNIQUE constraint, so the API-level collision
        case for the deterministic code can't fire in production. But
        two DIFFERENT names that happen to slug to the same prefix in
        the same minute (e.g. ``Acme1`` + ``Acme2`` both → ``ACME``)
        will collide on the code — exercise the suffixing path here.
        """
        from datetime import datetime, timezone

        from app.infrastructure.db.repositories.vendor_repository import (
            VendorRepository,
        )

        repo = VendorRepository(db_session)
        # Pin both creates to the SAME minute by patching the helper's
        # ``_utcnow``. Use distinct names that share the slug "ACME".
        import app.infrastructure.db.repositories.vendor_repository as vrm

        fixed = datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc)
        original = vrm._utcnow
        vrm._utcnow = lambda: fixed
        try:
            a = repo.create(name="Acme1")
            b = repo.create(name="Acme2")
            db_session.commit()
        finally:
            vrm._utcnow = original

        assert a.vendor_code != b.vendor_code
        # Both codes should share the ACME slug + same timestamp; the
        # second carries a -N suffix.
        codes = sorted([a.vendor_code, b.vendor_code], key=len)
        assert codes[1].startswith(codes[0] + "-"), (codes[0], codes[1])


class TestVendorLookupByCode:
    """GET / PATCH / DELETE / restore on /vendors/{id} accept VN-... codes."""

    def test_get_by_uuid_still_works(self, client, admin_user, admin_headers):
        v = _create_vendor(client, admin_headers)
        resp = client.get(f"/api/v3/vendors/{v['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["vendorCode"] == v["vendorCode"]

    def test_get_by_vendor_code(self, client, admin_user, admin_headers):
        v = _create_vendor(client, admin_headers)
        resp = client.get(
            f"/api/v3/vendors/{v['vendorCode']}", headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["id"] == v["id"]
        assert body["vendorCode"] == v["vendorCode"]

    def test_patch_by_vendor_code(self, client, admin_user, admin_headers):
        v = _create_vendor(client, admin_headers)
        resp = client.patch(
            f"/api/v3/vendors/{v['vendorCode']}",
            json={"description": "patched-by-code"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["description"] == "patched-by-code"

    def test_delete_then_restore_by_vendor_code(
        self, client, admin_user, admin_headers,
    ):
        v = _create_vendor(client, admin_headers)
        d = client.delete(
            f"/api/v3/vendors/{v['vendorCode']}", headers=admin_headers,
        )
        assert d.status_code in (200, 204), d.text
        # Default GET hides deleted rows.
        gone = client.get(
            f"/api/v3/vendors/{v['vendorCode']}", headers=admin_headers,
        )
        assert gone.status_code == 404
        # Restore by code.
        r = client.post(
            f"/api/v3/vendors/{v['vendorCode']}/restore",
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["id"] == v["id"]

    def test_unknown_code_returns_404(self, client, admin_user, admin_headers):
        resp = client.get(
            "/api/v3/vendors/VN-XXXX-260101000000", headers=admin_headers,
        )
        assert resp.status_code == 404


# ===========================================================================
# User side
# ===========================================================================

class TestUserCodeOnCreate:
    """POST /users/create stamps a userCode in the response."""

    def test_response_includes_user_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _create_vendor(client, admin_headers)
        p = _seed_project(db_session)
        body = _user_body(vendor_ref=v["id"], project_ids=[p.id])
        resp = client.post(
            "/api/v3/users/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert "userCode" in d
        assert d["userCode"] is not None
        assert _USER_CODE_RE.match(d["userCode"]), d["userCode"]

    def test_slug_from_login(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _create_vendor(client, admin_headers)
        p = _seed_project(db_session)
        body = _user_body(
            vendor_ref=v["id"], project_ids=[p.id], login="adminlike",
        )
        resp = client.post(
            "/api/v3/users/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        # First 4 of "adminlike" → "ADMI".
        assert resp.json()["data"]["userCode"].startswith("US-ADMI-")


class TestUserLookupByCode:
    """GET / PATCH / DELETE on /users/{id} accept US-... codes."""

    def _create_user(self, client, admin_headers, db_session):
        v = _create_vendor(client, admin_headers)
        p = _seed_project(db_session)
        resp = client.post(
            "/api/v3/users/create",
            json=_user_body(vendor_ref=v["id"], project_ids=[p.id]),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]

    def test_get_by_int_id_still_works(
        self, client, admin_user, admin_headers, db_session,
    ):
        u = self._create_user(client, admin_headers, db_session)
        resp = client.get(
            f"/api/v3/users/{u['id']}", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["userCode"] == u["userCode"]

    def test_get_by_user_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        u = self._create_user(client, admin_headers, db_session)
        resp = client.get(
            f"/api/v3/users/{u['userCode']}", headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["id"] == u["id"]
        assert body["userCode"] == u["userCode"]

    def test_patch_by_user_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        u = self._create_user(client, admin_headers, db_session)
        resp = client.patch(
            f"/api/v3/users/{u['userCode']}",
            json={"firstName": "Patched"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["firstName"] == "Patched"

    def test_delete_then_restore_by_user_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        u = self._create_user(client, admin_headers, db_session)
        d = client.delete(
            f"/api/v3/users/{u['userCode']}", headers=admin_headers,
        )
        assert d.status_code in (200, 204), d.text
        # Restore endpoint via code.
        r = client.post(
            f"/api/v3/users/{u['userCode']}/restore", headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["id"] == u["id"]

    def test_unknown_user_code_returns_404(
        self, client, admin_user, admin_headers,
    ):
        resp = client.get(
            "/api/v3/users/US-XXXX-260101000000", headers=admin_headers,
        )
        assert resp.status_code == 404


# ===========================================================================
# Cross-entity acceptance: create-user / create-project accept VN-... codes
# ===========================================================================

class TestCrossEntityVendorInputAcceptance:
    def test_user_create_accepts_vendor_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _create_vendor(client, admin_headers)
        p = _seed_project(db_session)
        body = _user_body(vendor_ref=v["vendorCode"], project_ids=[p.id])
        resp = client.post(
            "/api/v3/users/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        # The persisted FK is the canonical UUID, not the code.
        assert resp.json()["data"]["vendor"]["id"] == v["id"]

    def test_user_create_rejects_unknown_vendor_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        p = _seed_project(db_session)
        body = _user_body(
            vendor_ref="VN-XXXX-260101000000", project_ids=[p.id],
        )
        resp = client.post(
            "/api/v3/users/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_project_create_accepts_vendor_codes_in_list(
        self, client, admin_user, admin_headers,
    ):
        a = _create_vendor(client, admin_headers, name="ProjVendorA")
        b = _create_vendor(client, admin_headers, name="ProjVendorB")
        # Mix UUID + code in the same list.
        body = {
            "name": "Doc25 Mixed",
            "description": "tests vendor code in projectIds",
            "owner": "tmd1",
            "vendorIds": [a["id"], b["vendorCode"]],
        }
        resp = client.post(
            "/api/v3/projects/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        attached = sorted(v["name"] for v in resp.json()["data"]["vendors"])
        assert attached == ["ProjVendorA", "ProjVendorB"]

    def test_project_create_rejects_list_with_unknown_code(
        self, client, admin_user, admin_headers,
    ):
        v = _create_vendor(client, admin_headers, name="OnlyOne")
        body = {
            "name": "Doc25 BadList",
            "description": "tests unknown code rejection",
            "owner": "tmd1",
            "vendorIds": [v["vendorCode"], "VN-XXXX-260101000000"],
        }
        resp = client.post(
            "/api/v3/projects/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 422
        # Error message should name the unresolved token (not a UUID).
        assert "VN-XXXX-260101000000" in resp.json()["error"]["message"]


# ===========================================================================
# Backfill helper — exercises the migration's row-by-row code generator.
# Targets the same code path as the alembic ``upgrade()`` step 2 but runs it
# directly against the test DB so we don't have to spin up alembic in pytest.
# ===========================================================================

class TestBackfillBehavior:
    def test_backfill_assigns_codes_to_legacy_rows(self, db_session):
        from datetime import datetime, timezone

        from sqlalchemy import text

        from app.shared.code_generators import build_code, generate_unique_code

        # Insert two rows DIRECTLY (bypassing the repo) to simulate the
        # legacy state pre-doc-25.
        v1 = VendorModel(
            id=str(uuid4()),
            name="LegacyA",
            description="",
            active=True,
            created_at=datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc),
        )
        v2 = VendorModel(
            id=str(uuid4()),
            name="LegacyB",
            description="",
            active=True,
            created_at=datetime(2026, 5, 2, 9, 0, 16, tzinfo=timezone.utc),
        )
        db_session.add_all([v1, v2])
        db_session.commit()

        # NULL out vendor_code so the row looks like a pre-migration legacy row.
        db_session.execute(text(
            "UPDATE vendors SET vendor_code = NULL WHERE id IN (:a, :b)"
        ), {"a": v1.id, "b": v2.id})
        db_session.commit()

        # Run the migration's inner loop manually.
        rows = db_session.execute(text(
            "SELECT id, name, created_at FROM vendors WHERE vendor_code IS NULL"
        )).fetchall()
        assert len(rows) >= 2

        for row in rows:
            vid, vname, vcreated = row[0], row[1], row[2]
            base = build_code("VN", vname or "", vcreated)
            code = generate_unique_code(
                db_session.connection(),
                table="vendors", code_column="vendor_code",
                base_code=base, exclude_id=vid,
            )
            db_session.execute(text(
                "UPDATE vendors SET vendor_code = :c WHERE id = :i"
            ), {"c": code, "i": vid})
        db_session.commit()

        # Both rows now carry a code; both unique.
        codes = db_session.execute(text(
            "SELECT vendor_code FROM vendors WHERE id IN (:a, :b)"
        ), {"a": v1.id, "b": v2.id}).fetchall()
        codes_list = [c[0] for c in codes]
        assert all(_VENDOR_CODE_RE.match(c) for c in codes_list), codes_list
        assert len(set(codes_list)) == 2  # unique
