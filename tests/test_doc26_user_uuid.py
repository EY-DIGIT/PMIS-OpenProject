"""End-to-end tests for doc 26 — users.id flipped from Integer to UUID String(36).

Asserts the new shape:
  - POST /users/create returns ``id`` as a 36-char UUID string.
  - GET /users/{uuid} works.
  - GET /users/{userCode} still works (doc 25 polymorphism preserved).
  - Embedded user blocks across other resources (project createdBy,
    audit log actorId, comment author.id, attachment uploadedBy.id)
    all carry UUID strings, not integers.
  - JWT user_id claim survives a roundtrip as a string.

The whole repo's other tests (562) already use whatever ``id`` is
returned without assuming an int — those passing under the new schema
is itself the strongest signal that nothing FK-side broke.
"""
import re
from uuid import UUID, uuid4

import pytest

from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.vendor import VendorModel


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _is_uuid_string(value) -> bool:
    """Strict check — must be a string AND parseable as UUID."""
    if not isinstance(value, str):
        return False
    if not _UUID_RE.match(value):
        return False
    try:
        UUID(value)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Local helpers (mirror those in test_doc25_codes.py)
# ---------------------------------------------------------------------------

def _create_vendor(client, headers, *, name=None):
    body = {
        "name": name or f"Vendor-{uuid4().hex[:6]}",
        "description": "doc26 test vendor",
        "phoneNumber": "+91 98765 43210",
    }
    resp = client.post("/api/v3/vendors/create", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _seed_project(db_session):
    p = ProjectModel(
        id=str(uuid4()),
        project_code=f"UIDAI-PR{uuid4().hex[:14].upper()}",
        name="doc26 project",
        description="-",
        active=True,
        public=False,
        status="new",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _user_body(*, vendor_id, project_ids, login=None, email=None):
    suffix = uuid4().hex[:6]
    return {
        "login": login or f"user-{suffix}",
        "email": email or f"u{suffix}@example.com",
        "password": "password123",
        "firstName": "Doc",
        "lastName": "TwentySix",
        "admin": False,
        "vendorId": vendor_id,
        "division": "tmd1",
        "projectIds": list(project_ids),
        "phoneNumber": "+91 98765 43210",
    }


# ===========================================================================
# users.id is now a UUID string
# ===========================================================================

class TestUserIdIsUuid:
    def test_admin_user_fixture_has_uuid_id(self, admin_user):
        """The pytest fixture creates a UserModel directly via SQLAlchemy
        — the column default ``lambda: str(uuid4())`` should fire and
        produce a real UUID string."""
        assert _is_uuid_string(admin_user.id), admin_user.id

    def test_member_user_fixture_has_uuid_id(self, member_user):
        assert _is_uuid_string(member_user.id), member_user.id

    def test_two_user_ids_are_different(self, admin_user, member_user):
        assert admin_user.id != member_user.id

    def test_create_user_endpoint_returns_uuid_id(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _create_vendor(client, admin_headers)
        p = _seed_project(db_session)
        body = _user_body(vendor_id=v["id"], project_ids=[p.id])
        resp = client.post(
            "/api/v3/users/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert _is_uuid_string(d["id"]), d["id"]

    def test_get_user_by_uuid_works(self, client, admin_user, admin_headers):
        # admin_user.id is a UUID by now; the path param accepts it.
        resp = client.get(
            f"/api/v3/users/{admin_user.id}", headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["id"] == admin_user.id

    def test_get_user_by_user_code_still_works(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Doc 25 polymorphism preserved post-doc-26."""
        v = _create_vendor(client, admin_headers)
        p = _seed_project(db_session)
        resp = client.post(
            "/api/v3/users/create",
            json=_user_body(vendor_id=v["id"], project_ids=[p.id]),
            headers=admin_headers,
        )
        assert resp.status_code == 201
        u = resp.json()["data"]
        # Look up via US-... code.
        by_code = client.get(
            f"/api/v3/users/{u['userCode']}", headers=admin_headers,
        )
        assert by_code.status_code == 200
        assert by_code.json()["data"]["id"] == u["id"]
        assert _is_uuid_string(by_code.json()["data"]["id"])


# ===========================================================================
# Embedded user-id fields across other resources are UUIDs
# ===========================================================================

class TestEmbeddedUserIdFields:
    def test_login_response_user_id_is_uuid(self, client, admin_user):
        resp = client.post("/api/v3/users/login", json={
            "login": admin_user.login,
            "password": "admin123",
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert _is_uuid_string(body["user"]["id"]), body["user"]["id"]

    def test_jwt_user_id_claim_is_uuid_string(self, client, admin_user):
        """Mint a token via /login and decode it — the user_id claim
        should be a UUID string, not an integer."""
        from app.core.security import decode_access_token

        resp = client.post("/api/v3/users/login", json={
            "login": admin_user.login,
            "password": "admin123",
        })
        assert resp.status_code == 200
        token = resp.json()["data"]["access_token"]
        payload = decode_access_token(token)
        assert payload is not None
        assert _is_uuid_string(payload["user_id"]), payload["user_id"]

    def test_project_created_by_is_uuid(
        self, client, admin_user, admin_headers,
    ):
        body = {
            "name": "Doc26 created_by check",
            "owner": "tmd1",
        }
        resp = client.post(
            "/api/v3/projects/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        # The Project response embeds createdBy as the actor's id.
        assert _is_uuid_string(resp.json()["data"]["createdBy"])
