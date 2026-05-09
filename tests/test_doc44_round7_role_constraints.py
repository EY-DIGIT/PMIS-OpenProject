"""Doc 44 round 7 — monolith-side spec alignment.

  org_admin
    - Has full task / subtask CRUD INCLUDING delete (round 7
      seed-perm change). Verified via the role's seeded permission
      list.

  project_admin
    - Cannot self-unassign from project_members via DELETE
      /memberships/{id} — round-7 self-unassign guard in
      ProjectMembersController.remove_member.

The caller-vs-target matrix tests for project_admin's grant
constraints live in user-mgmt (where the matrix function is).
"""
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.project_member import ProjectMemberModel
from app.infrastructure.db.models.role import RoleModel
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.models.user_role_assignment import (
    UserRoleAssignmentModel,
)


def _make_user(db_session, login):
    u = UserModel(
        login=f"{login}-{uuid4().hex[:6]}",
        email=f"{login}-{uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pmis@1234"),
        first_name="T", last_name="User",
        status="active", two_factor_enabled=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


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


def _headers(user):
    return {
        "Authorization": "Bearer " + create_access_token({
            "sub": user.login, "user_id": user.id, "email": user.email,
        })
    }


# ---------------------------------------------------------------------------
# Seed-perm: org_admin gains tasks:delete + subtasks:delete (round 7).
# ---------------------------------------------------------------------------

class TestOrgAdminTaskDeletePerms:
    def test_org_admin_seed_includes_task_subtask_delete(
        self, db_session, admin_user,
    ):
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
        assert "tasks:delete" in codes
        assert "subtasks:delete" in codes
        # Sanity — the rest of the round-5 set is still there.
        assert "tasks:create" in codes
        assert "subtasks:create" in codes
        assert "tasks:update" in codes


# ---------------------------------------------------------------------------
# project_admin self-unassign guard at the project_members route.
# ---------------------------------------------------------------------------

class TestProjectAdminCannotSelfUnassignFromMembers:
    def test_project_admin_cannot_remove_own_membership(
        self, client, admin_user, db_session,
    ):
        """A project_admin calling DELETE /memberships/{id} on their
        OWN project_members row gets 403 — they can't unassign
        themselves from a project they administer."""
        # Bootstrap: a user holding project_admin on a project, plus
        # the matching project_members row.
        pa = _make_user(db_session, "pa-selfunassign")
        proj = _make_project(db_session)
        pa_role_id = (
            db_session.query(RoleModel).filter(RoleModel.name == "project_admin")
            .one().id
        )
        db_session.add(UserRoleAssignmentModel(
            user_id=pa.id, role_id=pa_role_id, project_id=proj.id,
        ))
        membership = ProjectMemberModel(
            project_id=proj.id, user_id=pa.id, roles=[],
        )
        db_session.add(membership)
        db_session.commit()
        db_session.refresh(membership)

        resp = client.delete(
            f"/api/v3/memberships/{membership.id}",
            headers=_headers(pa),
        )
        assert resp.status_code == 403, resp.text
        assert "unassign themselves" in resp.text.lower()

    def test_admin_can_remove_a_project_admin_membership(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Sanity: the round-7 guard fires only when the CALLER is
        themselves the project_admin being unassigned. An admin /
        super_admin caller can still remove anyone's membership."""
        pa = _make_user(db_session, "pa-target")
        proj = _make_project(db_session)
        pa_role_id = (
            db_session.query(RoleModel).filter(RoleModel.name == "project_admin")
            .one().id
        )
        db_session.add(UserRoleAssignmentModel(
            user_id=pa.id, role_id=pa_role_id, project_id=proj.id,
        ))
        membership = ProjectMemberModel(
            project_id=proj.id, user_id=pa.id, roles=[],
        )
        db_session.add(membership)
        db_session.commit()
        db_session.refresh(membership)

        resp = client.delete(
            f"/api/v3/memberships/{membership.id}",
            headers=admin_headers,
        )
        assert resp.status_code == 204, resp.text
