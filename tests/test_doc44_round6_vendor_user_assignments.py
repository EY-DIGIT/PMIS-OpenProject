"""Doc 44 round 6 — vendor user_assignments matrix on PATCH/POST/GET.

Vendor responses now carry a ``user_assignments`` array of
``{project_id, role, user_ids[]}`` tuples. PATCH /vendors/{id}
(and POST /vendors/create) accept the same shape and reconcile
the ``user_role_assignments`` rows so each (project, role) tuple
holds exactly the listed users.
"""
from uuid import uuid4

import pytest

from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.project_vendor import ProjectVendorModel
from app.infrastructure.db.models.role import RoleModel
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.models.user_role_assignment import (
    UserRoleAssignmentModel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_vendor(client, headers, name=None):
    body = {
        "name": name or f"V-{uuid4().hex[:6]}",
        "description": "doc44 round6",
        "phoneNumber": "9999999999",
    }
    r = client.post("/api/v3/vendors/create", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _make_project(db_session, name=None):
    p = ProjectModel(
        id=str(uuid4()),
        project_code=f"UIDAI-PR{uuid4().hex[:14].upper()}",
        name=name or f"P-{uuid4().hex[:5]}",
        description="-", active=True, public=False, status="new",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _attach_project_to_vendor(db_session, vendor_id, project_id):
    db_session.add(ProjectVendorModel(
        vendor_id=vendor_id, project_id=project_id,
    ))
    db_session.commit()


def _make_user(db_session, login=None):
    from app.core.security import hash_password
    u = UserModel(
        login=login or f"u-{uuid4().hex[:6]}",
        email=f"{login or uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pmis@1234"),
        first_name="T", last_name="User",
        status="active", two_factor_enabled=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


# ---------------------------------------------------------------------------
# PATCH /vendors/{id} with user_assignments
# ---------------------------------------------------------------------------

class TestVendorUserAssignmentsPatch:
    def test_patch_with_user_assignments_creates_role_rows(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _make_vendor(client, admin_headers)
        p = _make_project(db_session)
        _attach_project_to_vendor(db_session, v["id"], p.id)
        u1 = _make_user(db_session)
        u2 = _make_user(db_session)

        body = {
            "user_assignments": [
                {
                    "project_id": p.id,
                    "role": "Project Admin",
                    "user_ids": [u1.id, u2.id],
                },
                {
                    "project_id": p.id,
                    "role": "Project Member",
                    "user_ids": [],
                },
            ],
        }
        r = client.patch(
            f"/api/v3/vendors/{v['id']}",
            headers=admin_headers,
            json=body,
        )
        assert r.status_code == 200, r.text

        # Both u1 and u2 should now hold project_admin on p.
        pa_role_id = (
            db_session.query(RoleModel)
            .filter(RoleModel.name == "project_admin").one().id
        )
        rows = (
            db_session.query(UserRoleAssignmentModel)
            .filter(
                UserRoleAssignmentModel.role_id == pa_role_id,
                UserRoleAssignmentModel.project_id == p.id,
            )
            .all()
        )
        assert {r.user_id for r in rows} == {u1.id, u2.id}

    def test_patch_with_smaller_user_list_revokes_extras(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Sending user_ids=[u1] when the DB has [u1, u2] should revoke u2."""
        v = _make_vendor(client, admin_headers)
        p = _make_project(db_session)
        _attach_project_to_vendor(db_session, v["id"], p.id)
        u1 = _make_user(db_session)
        u2 = _make_user(db_session)

        # Seed both via PATCH.
        client.patch(
            f"/api/v3/vendors/{v['id']}",
            headers=admin_headers,
            json={"user_assignments": [
                {"project_id": p.id, "role": "Project Admin",
                 "user_ids": [u1.id, u2.id]},
            ]},
        )
        # Now reconcile to just [u1] — u2 should disappear.
        r = client.patch(
            f"/api/v3/vendors/{v['id']}",
            headers=admin_headers,
            json={"user_assignments": [
                {"project_id": p.id, "role": "Project Admin",
                 "user_ids": [u1.id]},
            ]},
        )
        assert r.status_code == 200, r.text
        pa_role_id = (
            db_session.query(RoleModel)
            .filter(RoleModel.name == "project_admin").one().id
        )
        rows = (
            db_session.query(UserRoleAssignmentModel)
            .filter(
                UserRoleAssignmentModel.role_id == pa_role_id,
                UserRoleAssignmentModel.project_id == p.id,
            )
            .all()
        )
        assert {r.user_id for r in rows} == {u1.id}

    def test_patch_rejects_project_not_owned_by_vendor(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _make_vendor(client, admin_headers)
        # Project NOT attached to this vendor.
        outside = _make_project(db_session)
        u1 = _make_user(db_session)

        r = client.patch(
            f"/api/v3/vendors/{v['id']}",
            headers=admin_headers,
            json={"user_assignments": [
                {"project_id": outside.id, "role": "Project Admin",
                 "user_ids": [u1.id]},
            ]},
        )
        assert r.status_code == 422, r.text
        assert "not owned" in r.text.lower()

    def test_patch_rejects_unknown_role(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _make_vendor(client, admin_headers)
        p = _make_project(db_session)
        _attach_project_to_vendor(db_session, v["id"], p.id)
        u1 = _make_user(db_session)

        r = client.patch(
            f"/api/v3/vendors/{v['id']}",
            headers=admin_headers,
            json={"user_assignments": [
                {"project_id": p.id, "role": "Wizard",
                 "user_ids": [u1.id]},
            ]},
        )
        assert r.status_code == 422, r.text
        assert "invalid role" in r.text.lower()

    def test_patch_accepts_canonical_role_names_too(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Both 'Project Admin' (display label) and 'project_admin'
        (canonical name) are accepted."""
        v = _make_vendor(client, admin_headers)
        p = _make_project(db_session)
        _attach_project_to_vendor(db_session, v["id"], p.id)
        u1 = _make_user(db_session)

        r = client.patch(
            f"/api/v3/vendors/{v['id']}",
            headers=admin_headers,
            json={"user_assignments": [
                {"project_id": p.id, "role": "project_admin",
                 "user_ids": [u1.id]},
            ]},
        )
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# GET responses include user_assignments
# ---------------------------------------------------------------------------

class TestVendorUserAssignmentsGet:
    def test_get_vendor_returns_user_assignments(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _make_vendor(client, admin_headers)
        p = _make_project(db_session)
        _attach_project_to_vendor(db_session, v["id"], p.id)
        u1 = _make_user(db_session)

        client.patch(
            f"/api/v3/vendors/{v['id']}",
            headers=admin_headers,
            json={"user_assignments": [
                {"project_id": p.id, "role": "Project Admin",
                 "user_ids": [u1.id]},
            ]},
        )
        r = client.get(f"/api/v3/vendors/{v['id']}", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "user_assignments" in data
        ua = data["user_assignments"]
        assert any(
            entry["project_id"] == p.id
            and entry["role"] == "Project Admin"
            and u1.id in entry["user_ids"]
            for entry in ua
        )

    def test_list_vendors_includes_user_assignments(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _make_vendor(client, admin_headers)
        r = client.get("/api/v3/vendors", headers=admin_headers)
        assert r.status_code == 200, r.text
        elements = r.json()["data"]["_embedded"]["elements"]
        target = next(e for e in elements if e["id"] == v["id"])
        assert "user_assignments" in target
        assert isinstance(target["user_assignments"], list)

    def test_get_vendor_with_no_assignments_returns_empty_list(
        self, client, admin_user, admin_headers,
    ):
        v = _make_vendor(client, admin_headers)
        r = client.get(f"/api/v3/vendors/{v['id']}", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["user_assignments"] == []
