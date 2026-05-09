"""Doc 44 round 8 — alignment-audit BE fixes (monolith side).

Five fixes covered here:

  1. ``GET /vendors/{id}`` rejects non-admin callers requesting a
     vendor other than their own (bug 2).
  2. ``GET /projects`` and ``GET /projects/{id}`` hide pre-publish
     statuses (`draft`, `new`) from non-admin callers (bug 3).
  3. ``ORG_ADMIN_ROLE_PERMISSIONS`` no longer carries
     ``master_data:view`` (bug 4 — seed test; route-level test in
     user-mgmt suite).
  4. ``PATCH /vendors/{id}`` accepts ``user_assignments``-only bodies
     from callers holding ``rbac:assign`` (org_admin); any other
     field still requires ``vendors:manage`` (bug 7).
  5. ``GET /projects/{id}/role-assignments`` exists on the monolith
     (bug 10) — same shape as the user-mgmt route at the same path.

Bug 18 (project_admin gains ``users:read_all``) is verified in the
user-mgmt suite — that's where the perm controls the route.
"""
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.project_vendor import ProjectVendorModel
from app.infrastructure.db.models.role import RoleModel
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.models.user_role_assignment import (
    UserRoleAssignmentModel,
)
from app.infrastructure.db.models.vendor import VendorModel


def _make_user(db_session, login, vendor_id=None):
    u = UserModel(
        login=f"{login}-{uuid4().hex[:6]}",
        email=f"{login}-{uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pmis@1234"),
        first_name="T", last_name="User",
        status="active", two_factor_enabled=False,
        vendor_id=vendor_id,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _make_vendor(db_session, name=None):
    v = VendorModel(
        id=str(uuid4()),
        name=name or f"V-{uuid4().hex[:5]}",
        description="-", active=True,
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


def _make_project(db_session, name=None, status="new"):
    p = ProjectModel(
        id=str(uuid4()),
        project_code=f"UIDAI-PR{uuid4().hex[:14].upper()}",
        name=name or f"P-{uuid4().hex[:5]}",
        description="-", active=True, public=False, status=status,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _link_vendor_project(db_session, vendor, project):
    db_session.add(ProjectVendorModel(
        project_id=project.id, vendor_id=vendor.id,
    ))
    db_session.commit()


def _grant(db_session, user, role_name, project_id=None, organization_id=None):
    role_id = (
        db_session.query(RoleModel).filter(RoleModel.name == role_name).one().id
    )
    db_session.add(UserRoleAssignmentModel(
        user_id=user.id, role_id=role_id,
        project_id=project_id, organization_id=organization_id,
    ))
    db_session.commit()


def _headers(user):
    return {
        "Authorization": "Bearer " + create_access_token({
            "sub": user.login, "user_id": user.id, "email": user.email,
        })
    }


# ---------------------------------------------------------------------------
# Fix 1 — GET /vendors/{id} vendor-scope check (bug 2)
# ---------------------------------------------------------------------------

class TestGetVendorScope:
    """Non-admin callers can only fetch their own vendor."""

    def test_org_admin_blocked_from_other_vendor(
        self, client, admin_user, db_session,
    ):
        own = _make_vendor(db_session, "OwnVendor")
        other = _make_vendor(db_session, "OtherVendor")
        oa = _make_user(db_session, "oa-scope", vendor_id=own.id)
        _grant(db_session, oa, "org_admin", organization_id=own.id)

        resp = client.get(
            f"/api/v3/vendors/{other.id}", headers=_headers(oa),
        )
        assert resp.status_code == 403, resp.text
        assert "your own organization" in resp.text.lower()

    def test_org_admin_allowed_on_own_vendor(
        self, client, admin_user, db_session,
    ):
        own = _make_vendor(db_session, "OwnAllow")
        oa = _make_user(db_session, "oa-allow", vendor_id=own.id)
        _grant(db_session, oa, "org_admin", organization_id=own.id)

        resp = client.get(
            f"/api/v3/vendors/{own.id}", headers=_headers(oa),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["id"] == own.id

    def test_admin_bypasses_scope_check(
        self, client, admin_headers, db_session,
    ):
        v = _make_vendor(db_session, "AdminFetch")
        resp = client.get(
            f"/api/v3/vendors/{v.id}", headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Fix 2 — non-admin sees only post-publish projects (bug 3)
# ---------------------------------------------------------------------------

class TestProjectListPrePublishHidden:
    """Non-admin tiers don't see status in {draft, new}."""

    def test_org_admin_sees_only_published_etc(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "ScopeV")
        p_draft = _make_project(db_session, "draft-proj", status="draft")
        p_new = _make_project(db_session, "new-proj", status="new")
        p_pub = _make_project(db_session, "pub-proj", status="published")
        for p in (p_draft, p_new, p_pub):
            _link_vendor_project(db_session, v, p)

        oa = _make_user(db_session, "oa-status", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.get(
            "/api/v3/projects?pageSize=50", headers=_headers(oa),
        )
        assert resp.status_code == 200, resp.text
        ids = {
            p["id"] for p in resp.json()["data"]["_embedded"]["elements"]
        }
        assert p_pub.id in ids
        assert p_draft.id not in ids
        assert p_new.id not in ids

    def test_admin_sees_all_statuses(
        self, client, admin_headers, db_session,
    ):
        p_draft = _make_project(db_session, "ad-draft", status="draft")
        resp = client.get(
            "/api/v3/projects?pageSize=100", headers=admin_headers,
        )
        ids = {
            p["id"] for p in resp.json()["data"]["_embedded"]["elements"]
        }
        assert p_draft.id in ids


class TestGetProjectPrePublishHidden:
    """Non-admin gets 404 fetching a single pre-publish project."""

    def test_org_admin_404_on_draft(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "GetScope")
        p = _make_project(db_session, "to-hide", status="draft")
        _link_vendor_project(db_session, v, p)
        oa = _make_user(db_session, "oa-getsingle", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.get(f"/api/v3/projects/{p.id}", headers=_headers(oa))
        assert resp.status_code == 404, resp.text

    def test_admin_can_get_draft(
        self, client, admin_headers, db_session,
    ):
        p = _make_project(db_session, "admin-get-draft", status="draft")
        resp = client.get(f"/api/v3/projects/{p.id}", headers=admin_headers)
        assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Fix 3 — org_admin seed excludes master_data:view (bug 4 — seed slice)
# ---------------------------------------------------------------------------

class TestOrgAdminSeedExcludesMasterDataView:
    def test_org_admin_no_master_data_view(self, db_session, admin_user):
        from app.infrastructure.db.repositories.rbac_repository import (
            RbacRepository,
        )
        codes = set(
            RbacRepository(db_session).list_role_permissions(
                db_session.query(RoleModel).filter(
                    RoleModel.name == "org_admin"
                ).one().id
            )
        )
        # Round 8 spec: org_admin must not have any master-data access.
        assert "master_data:view" not in codes
        assert "master_data:manage" not in codes
        # vendors:read kept — org_admin still views their own vendor.
        assert "vendors:read" in codes


# ---------------------------------------------------------------------------
# Fix 4 — PATCH /vendors/{id} body-shape carve-out (bug 7)
# ---------------------------------------------------------------------------

class TestVendorPatchBodyShapeGate:
    """org_admin can PATCH user_assignments-only; anything else still
    requires vendors:manage."""

    def test_org_admin_can_patch_user_assignments_only(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "PA-AssignOnly")
        p = _make_project(db_session, "PA-proj", status="published")
        _link_vendor_project(db_session, v, p)
        oa = _make_user(db_session, "oa-uassign", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)
        target = _make_user(db_session, "pm-target", vendor_id=v.id)

        body = {
            "user_assignments": [
                {
                    "project_id": p.id,
                    "role": "project_member",
                    "user_ids": [target.id],
                },
            ]
        }
        resp = client.patch(
            f"/api/v3/vendors/{v.id}", json=body, headers=_headers(oa),
        )
        assert resp.status_code == 200, resp.text

    def test_org_admin_blocked_when_body_includes_name(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "PA-NameBlock")
        oa = _make_user(db_session, "oa-name", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"name": "hacked", "user_assignments": []},
            headers=_headers(oa),
        )
        assert resp.status_code == 403, resp.text
        assert "vendors:manage" in resp.text.lower()

    def test_org_admin_blocked_on_other_vendor_assignments_only(
        self, client, admin_user, db_session,
    ):
        own = _make_vendor(db_session, "OAOwn-2")
        other = _make_vendor(db_session, "OAOther-2")
        oa = _make_user(db_session, "oa-cross", vendor_id=own.id)
        _grant(db_session, oa, "org_admin", organization_id=own.id)

        resp = client.patch(
            f"/api/v3/vendors/{other.id}",
            json={"user_assignments": []},
            headers=_headers(oa),
        )
        assert resp.status_code == 403, resp.text

    def test_admin_full_patch_still_works(
        self, client, admin_headers, db_session,
    ):
        v = _make_vendor(db_session, "AdminFullPatch")
        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"name": "Renamed", "user_assignments": []},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Fix 5 — GET /projects/{id}/role-assignments on monolith (bug 10)
# ---------------------------------------------------------------------------

class TestProjectRoleAssignmentsOnMonolith:
    def test_returns_role_buckets(
        self, client, admin_headers, db_session,
    ):
        v = _make_vendor(db_session, "RouteV")
        p = _make_project(db_session, "RouteP", status="published")
        _link_vendor_project(db_session, v, p)
        pa = _make_user(db_session, "ra-pa", vendor_id=v.id)
        pm = _make_user(db_session, "ra-pm", vendor_id=v.id)
        _grant(db_session, pa, "project_admin", project_id=p.id)
        _grant(db_session, pm, "project_member", project_id=p.id)

        resp = client.get(
            f"/api/v3/projects/{p.id}/role-assignments",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["projectId"] == p.id
        roles_by_name = {r["roleName"]: r for r in data["roles"]}
        assert "project_admin" in roles_by_name
        assert "project_member" in roles_by_name
        assert any(u["id"] == pa.id for u in roles_by_name["project_admin"]["users"])
        assert any(u["id"] == pm.id for u in roles_by_name["project_member"]["users"])

    def test_404_on_unknown_project(
        self, client, admin_headers,
    ):
        resp = client.get(
            "/api/v3/projects/00000000-0000-0000-0000-000000000000/role-assignments",
            headers=admin_headers,
        )
        assert resp.status_code == 404, resp.text
