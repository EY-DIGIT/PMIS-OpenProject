"""Project membership has been unified into ``user_role_assignments``
(the legacy ``project_members`` table was dropped — see alembic
migration ``baddc1146b85``).

These tests pin the contract:

  * users created with ``projectIds`` show those projects in the
    ``projects`` field of the user response,
  * users added via ``POST /projects/{id}/role-assignments`` show the
    project in their user response too (this was the original
    regression — modern path was invisible),
  * a project soft-delete cascades to URA project-scoped rows.
"""
from uuid import uuid4

import pytest

from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.role import RoleModel
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.models.user_role_assignment import (
    UserRoleAssignmentModel,
)
from app.infrastructure.db.models.vendor import VendorModel


def _vendor(db_session):
    v = VendorModel(
        id=str(uuid4()),
        vendor_code=f"VN-{uuid4().hex[:6].upper()}",
        name=f"V-{uuid4().hex[:4]}", active=True,
        phone_number="+919999999999", email="ops@v.example",
    )
    db_session.add(v); db_session.commit(); db_session.refresh(v)
    return v


def _project(db_session, name=None):
    p = ProjectModel(
        id=str(uuid4()),
        project_code=f"PR-{uuid4().hex[:8].upper()}",
        name=name or f"P-{uuid4().hex[:5]}",
        status="published",
    )
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    return p


class TestUserCreatedWithProjectIds:
    def test_projects_array_populated_on_user_response(
        self, client, admin_headers, db_session,
    ):
        """Original regression: POST /users/create with projectIds wrote
        only legacy project_members rows; GET /users/{id} read URA and
        showed projects=[]. After unification, projectIds writes URA
        and the response shows the project."""
        v = _vendor(db_session)
        p = _project(db_session, "via-create")
        # Map vendor to project so the user passes vendor scope.
        from app.infrastructure.db.models.project_vendor import ProjectVendorModel
        db_session.add(ProjectVendorModel(project_id=p.id, vendor_id=v.id))
        db_session.commit()

        r = client.post(
            "/api/v3/users/create",
            headers=admin_headers,
            json={
                "login": f"u-{uuid4().hex[:6]}",
                "email": f"u-{uuid4().hex[:6]}@x.com",
                "password": "Pmis@1234",
                "firstName": "U", "lastName": "T",
                "vendorId": v.id,
                "phoneNumber": "+919999999999",
                "division": "tmd1",
                "projectIds": [p.id],
            },
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()["data"]
        assert {x["id"] for x in body["projects"]} == {p.id}

        # URA row was written; legacy table is gone.
        ura_rows = (
            db_session.query(UserRoleAssignmentModel)
            .filter(UserRoleAssignmentModel.user_id == body["id"])
            .all()
        )
        assert len(ura_rows) == 1
        assert ura_rows[0].project_id == p.id


class TestUserAddedViaModernRoleAssignmentFlow:
    def test_projects_array_includes_role_assignment_project(
        self, client, admin_user, admin_headers, db_session,
    ):
        """A user added to a project only via URA (no legacy
        project_members row could exist) must surface that project in
        the GET /users/{id} response. This was broken before the
        unification — _load_projects_for_user queried only the legacy
        table."""
        from app.core.security import hash_password
        u = UserModel(
            login=f"u-{uuid4().hex[:6]}",
            email=f"u-{uuid4().hex[:6]}@x.com",
            hashed_password=hash_password("Pmis@1234"),
            first_name="Modern", last_name="User",
            status="active", two_factor_enabled=False,
        )
        db_session.add(u); db_session.commit(); db_session.refresh(u)

        p = _project(db_session, "via-ura")
        pm_role_id = (
            db_session.query(RoleModel.id)
            .filter(RoleModel.name == "project_member")
            .scalar()
        )
        db_session.add(UserRoleAssignmentModel(
            user_id=u.id, role_id=pm_role_id, project_id=p.id,
        ))
        db_session.commit()

        r = client.get(f"/api/v3/users/{u.id}", headers=admin_headers)
        assert r.status_code == 200, r.text
        projects = r.json()["data"]["projects"]
        assert {x["id"] for x in projects} == {p.id}


class TestSameUserMultipleProjectTierRolesDistinct:
    def test_same_project_appears_once_under_multiple_roles(
        self, client, admin_user, admin_headers, db_session,
    ):
        """A user holding e.g. project_admin AND project_member on the
        same project should only see that project once in projects[]."""
        from app.core.security import hash_password
        u = UserModel(
            login=f"u-{uuid4().hex[:6]}",
            email=f"u-{uuid4().hex[:6]}@x.com",
            hashed_password=hash_password("Pmis@1234"),
            first_name="Dual", last_name="Role",
            status="active", two_factor_enabled=False,
        )
        db_session.add(u); db_session.commit(); db_session.refresh(u)

        p = _project(db_session, "dual-role-proj")
        pm_id = db_session.query(RoleModel.id).filter(
            RoleModel.name == "project_member").scalar()
        pa_id = db_session.query(RoleModel.id).filter(
            RoleModel.name == "project_admin").scalar()
        db_session.add_all([
            UserRoleAssignmentModel(user_id=u.id, role_id=pm_id, project_id=p.id),
            UserRoleAssignmentModel(user_id=u.id, role_id=pa_id, project_id=p.id),
        ])
        db_session.commit()

        r = client.get(f"/api/v3/users/{u.id}", headers=admin_headers)
        projects = r.json()["data"]["projects"]
        assert [x["id"] for x in projects] == [p.id]


class TestSoftDeleteCascadesToURA:
    def test_deleting_project_clears_project_scoped_ura_rows(
        self, client, admin_user, admin_headers, db_session,
    ):
        """When a project is soft-deleted, project-scoped URA rows for
        that project are wiped (cascade-delete in projects/services/
        delete.py). Other-scope URA rows on the same user are
        untouched."""
        from app.core.security import hash_password
        u = UserModel(
            login=f"u-{uuid4().hex[:6]}",
            email=f"u-{uuid4().hex[:6]}@x.com",
            hashed_password=hash_password("Pmis@1234"),
            first_name="Cascade", last_name="User",
            status="active", two_factor_enabled=False,
        )
        db_session.add(u); db_session.commit(); db_session.refresh(u)

        v = _vendor(db_session)
        p = _project(db_session, "to-delete")
        pm_id = db_session.query(RoleModel.id).filter(
            RoleModel.name == "project_member").scalar()
        oa_id = db_session.query(RoleModel.id).filter(
            RoleModel.name == "org_admin").scalar()
        db_session.add_all([
            UserRoleAssignmentModel(user_id=u.id, role_id=pm_id, project_id=p.id),
            UserRoleAssignmentModel(user_id=u.id, role_id=oa_id, organization_id=v.id),
        ])
        db_session.commit()

        r = client.delete(f"/api/v3/projects/{p.id}", headers=admin_headers)
        assert r.status_code in (200, 204), r.text

        # Project-scoped row gone; org-scoped row preserved.
        remaining = (
            db_session.query(UserRoleAssignmentModel)
            .filter(UserRoleAssignmentModel.user_id == u.id)
            .all()
        )
        assert len(remaining) == 1
        assert remaining[0].organization_id == v.id
        assert remaining[0].project_id is None
