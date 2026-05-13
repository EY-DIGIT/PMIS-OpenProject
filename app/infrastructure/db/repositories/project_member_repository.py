"""Project Member repository — URA-backed compatibility layer.

The legacy ``project_members`` table was retired in favour of the
doc-41 scoped-RBAC ``user_role_assignments`` (URA) table. This
repository keeps its existing API surface so the seven callers
(meetings participants, work_packages, /api/v3/project_members/*
endpoints) don't need to change — every method now reads or writes
URA rows scoped to a project with the canonical ``project_member``
role.

The ``roles`` field on the domain ``Membership`` was always written
as ``[]`` in code (verified pre-migration). It's preserved on the
domain object for API back-compat but is no longer load-bearing.
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ...db.models.role import RoleModel
from ...db.models.user_role_assignment import UserRoleAssignmentModel
from ....domain.project_members.membership import Membership


_PROJECT_MEMBER_ROLE = "project_member"


class ProjectMemberRepository:
    """URA-backed project membership repository.

    Project membership is now represented as a ``user_role_assignments``
    row with ``project_id = <project>`` and ``role = project_member``.
    The ``Membership`` domain object the caller sees is hydrated from
    the URA row; the legacy ``id`` field is the URA primary key.
    """

    def __init__(self, db: Session):
        self.db = db

    def _role_id(self) -> int:
        rid = (
            self.db.query(RoleModel.id)
            .filter(RoleModel.name == _PROJECT_MEMBER_ROLE)
            .scalar()
        )
        if rid is None:
            raise RuntimeError(
                f"{_PROJECT_MEMBER_ROLE} role not seeded — RBAC sync did not run"
            )
        return rid

    def _to_domain(self, ura: UserRoleAssignmentModel) -> Membership:
        # ``roles`` and ``updated_at`` are kept on the domain shape for
        # back-compat with old callers; the URA row doesn't carry an
        # updated_at column so we surface created_at for both fields.
        return Membership(
            id=ura.id,
            project_id=ura.project_id,
            user_id=ura.user_id,
            roles=[],
            created_at=ura.created_at,
            updated_at=ura.created_at,
        )

    def _query_for_project(self, project_id: str):
        return (
            self.db.query(UserRoleAssignmentModel)
            .filter(UserRoleAssignmentModel.project_id == project_id)
            .filter(UserRoleAssignmentModel.role_id == self._role_id())
        )

    def _query_for_user(self, user_id: str):
        return (
            self.db.query(UserRoleAssignmentModel)
            .filter(UserRoleAssignmentModel.user_id == user_id)
            .filter(UserRoleAssignmentModel.project_id.isnot(None))
            .filter(UserRoleAssignmentModel.role_id == self._role_id())
        )

    def create(
        self,
        project_id: str,
        user_id: str,
        roles: List[str],
    ) -> Membership:
        # ``roles`` arg ignored (always [] in legacy callers).
        ura = UserRoleAssignmentModel(
            user_id=user_id,
            role_id=self._role_id(),
            project_id=project_id,
        )
        self.db.add(ura)
        self.db.commit()
        self.db.refresh(ura)
        return self._to_domain(ura)

    def get_by_id(self, membership_id: int) -> Optional[Membership]:
        # Any project-scoped URA row counts as a membership lookup
        # by id (project_admin / project_member / division_member). The
        # role-restricted variants live in ``list_by_project`` /
        # ``list_by_user`` where the caller's intent is "list
        # memberships at the project_member tier".
        ura = (
            self.db.query(UserRoleAssignmentModel)
            .filter(UserRoleAssignmentModel.id == membership_id)
            .filter(UserRoleAssignmentModel.project_id.isnot(None))
            .first()
        )
        return self._to_domain(ura) if ura else None

    def get_by_project_and_user(
        self, project_id: str, user_id: str,
    ) -> Optional[Membership]:
        ura = (
            self._query_for_project(project_id)
            .filter(UserRoleAssignmentModel.user_id == user_id)
            .first()
        )
        return self._to_domain(ura) if ura else None

    def exists_by_project_and_user(
        self, project_id: str, user_id: str,
    ) -> bool:
        return self.get_by_project_and_user(project_id, user_id) is not None

    def list_by_project(
        self,
        project_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Membership], int]:
        q = self._query_for_project(project_id)
        total = q.count()
        offset = (page - 1) * page_size
        models = q.offset(offset).limit(page_size).all()
        return [self._to_domain(m) for m in models], total

    def list_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Membership], int]:
        q = self._query_for_user(user_id)
        total = q.count()
        offset = (page - 1) * page_size
        models = q.offset(offset).limit(page_size).all()
        return [self._to_domain(m) for m in models], total

    def update(
        self,
        membership_id: int,
        roles: List[str],
    ) -> Optional[Membership]:
        # ``roles`` ignored — URA membership rows carry a single role
        # (project_member) and changing it is out of scope for the
        # legacy update flow.
        ura = (
            self.db.query(UserRoleAssignmentModel)
            .filter(UserRoleAssignmentModel.id == membership_id)
            .first()
        )
        if not ura:
            return None
        return self._to_domain(ura)

    def delete(self, membership_id: int) -> bool:
        # Symmetric with ``get_by_id``: delete any project-scoped URA
        # row by id. Global / org-scoped rows are never reachable
        # through this URL (project_id IS NULL guards them).
        ura = (
            self.db.query(UserRoleAssignmentModel)
            .filter(UserRoleAssignmentModel.id == membership_id)
            .filter(UserRoleAssignmentModel.project_id.isnot(None))
            .first()
        )
        if not ura:
            return False
        self.db.delete(ura)
        self.db.commit()
        return True

    def delete_by_project_and_user(
        self, project_id: str, user_id: str,
    ) -> bool:
        ura = (
            self._query_for_project(project_id)
            .filter(UserRoleAssignmentModel.user_id == user_id)
            .first()
        )
        if not ura:
            return False
        self.db.delete(ura)
        self.db.commit()
        return True

    def exists(self, project_id: str, user_id: str) -> bool:
        return self.exists_by_project_and_user(project_id, user_id)

    def is_member(self, project_id: str, user_id: str) -> bool:
        return self.exists(project_id, user_id)
