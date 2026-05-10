"""Round 11b — GET /api/v3/projects/{id}/assignable-users.

Returns the union of:
  (a) every user with a project-tier role assignment on this project
      (project_admin, project_member, division_member),
  (b) every user with an org_admin assignment on the project's
      owning vendor(s).

Powers the FE Task / Sub-Task "Assigned To" picker so PA / PM
candidates AND the org admins above them appear, without leaking
PMIS Admin / Super Admin or unrelated users.
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


def _vendor(db, name=None):
    v = VendorModel(
        id=str(uuid4()),
        name=name or f"V-{uuid4().hex[:5]}",
        description="-", active=True,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _project(db, name=None):
    p = ProjectModel(
        id=str(uuid4()),
        project_code=f"UIDAI-PR{uuid4().hex[:14].upper()}",
        name=name or f"P-{uuid4().hex[:5]}",
        status="published", active=True, public=False,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _link(db, vendor, project):
    db.add(ProjectVendorModel(project_id=project.id, vendor_id=vendor.id))
    db.commit()


def _user(db, login, vendor_id=None):
    u = UserModel(
        login=f"{login}-{uuid4().hex[:5]}",
        email=f"{login}-{uuid4().hex[:5]}@example.com",
        hashed_password=hash_password("Pmis@1234"),
        first_name="T", last_name="U",
        status="active", two_factor_enabled=False,
        vendor_id=vendor_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _grant(db, user, role_name, project_id=None, organization_id=None):
    rid = db.query(RoleModel).filter(RoleModel.name == role_name).one().id
    db.add(UserRoleAssignmentModel(
        user_id=user.id, role_id=rid,
        project_id=project_id, organization_id=organization_id,
    ))
    db.commit()


class TestProjectAssignableUsers:
    def test_returns_project_members_and_org_admin(
        self, client, admin_user, admin_headers, db_session,
    ):
        v = _vendor(db_session, "AssignableV")
        p = _project(db_session, "AssignableP")
        _link(db_session, v, p)

        pa = _user(db_session, "ass-pa", vendor_id=v.id)
        pm = _user(db_session, "ass-pm", vendor_id=v.id)
        oa = _user(db_session, "ass-oa", vendor_id=v.id)
        # User in same vendor but NOT on the project AND not an OA —
        # should NOT appear in the dropdown.
        bystander = _user(db_session, "ass-bystander", vendor_id=v.id)

        _grant(db_session, pa, "project_admin", project_id=p.id)
        _grant(db_session, pm, "project_member", project_id=p.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.get(
            f"/api/v3/projects/{p.id}/assignable-users",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        ids = {u["id"] for u in data["users"]}

        assert pa.id in ids
        assert pm.id in ids
        assert oa.id in ids
        assert bystander.id not in ids
        # Each entry carries login + orgRole.
        for u in data["users"]:
            assert "login" in u
            assert "orgRole" in u

    def test_dedupes_users_with_dual_assignment(
        self, client, admin_user, admin_headers, db_session,
    ):
        """A user holding both project_admin (project-scoped) AND
        org_admin (org-scoped) on the same vendor should appear ONCE."""
        v = _vendor(db_session, "DupV")
        p = _project(db_session, "DupP")
        _link(db_session, v, p)
        u = _user(db_session, "dup", vendor_id=v.id)
        _grant(db_session, u, "project_admin", project_id=p.id)
        _grant(db_session, u, "org_admin", organization_id=v.id)

        resp = client.get(
            f"/api/v3/projects/{p.id}/assignable-users",
            headers=admin_headers,
        )
        ids = [u["id"] for u in resp.json()["data"]["users"]]
        assert ids.count(u.id) == 1

    def test_unknown_project_404(self, client, admin_user, admin_headers):
        resp = client.get(
            "/api/v3/projects/00000000-0000-0000-0000-000000000000/"
            "assignable-users",
            headers=admin_headers,
        )
        assert resp.status_code == 404, resp.text

    def test_admin_tier_users_excluded(
        self, client, admin_user, admin_headers, db_session,
    ):
        """A user with admin / super_admin role assignment on the
        project's vendor must NOT appear (spec: only OA among the
        admin tiers can be assigned tasks; PMIS Admin / Super Admin
        stay out of project pickers per round 10)."""
        v = _vendor(db_session, "AdmExcl")
        p = _project(db_session, "AdmExclP")
        _link(db_session, v, p)
        admin_user_2 = _user(db_session, "adm2", vendor_id=v.id)
        # legacy admin role row
        rid = db_session.query(RoleModel).filter(
            RoleModel.name == "admin"
        ).one().id
        from app.infrastructure.db.models.user_role import UserRoleModel
        db_session.add(UserRoleModel(user_id=admin_user_2.id, role_id=rid))
        db_session.commit()

        resp = client.get(
            f"/api/v3/projects/{p.id}/assignable-users",
            headers=admin_headers,
        )
        ids = {u["id"] for u in resp.json()["data"]["users"]}
        assert admin_user_2.id not in ids
