"""Repository for the DB-driven RBAC tables (doc 21 part B + doc 41 scope).

Single class managing CRUD on permissions, role-permission grants,
user-role assignments, and direct user-permission grants. Centralizes
both the read (effective permissions for a user) and write paths so the
rest of the codebase doesn't reach into individual model classes.

Doc 41 added scoped role assignments via ``user_role_assignments``
(org / project scope). The legacy ``user_roles`` rows continue to count
as global-scope grants. ``effective_permissions_for_user`` returns the
flat union (used by ``require_permission``); ``effective_permissions_by_scope``
returns the per-scope view (used by doc-41's
``require_project_permission`` / ``require_org_permission``).

All writes flush but do NOT commit — caller owns the transaction.
"""
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import and_, delete, exists, func
from sqlalchemy.orm import Session

from ....core.permissions import (
    ADMIN_ROLE_NAME,
    # Doc 41 — scoped role names (seeded as empty rows here; their
    # permission sets are owned + seeded by user-mgmt's startup sync).
    SUPER_ADMIN_ROLE_NAME,
    SUPER_ADMIN_ROLE_PERMISSIONS,
    ORG_ADMIN_ROLE_NAME,
    ORG_ADMIN_ROLE_PERMISSIONS,
    PROJECT_ADMIN_ROLE_NAME,
    PROJECT_ADMIN_ROLE_PERMISSIONS,
    PROJECT_MEMBER_ROLE_NAME,
    PROJECT_MEMBER_ROLE_PERMISSIONS,
    DIVISION_MEMBER_ROLE_NAME,
    DIVISION_MEMBER_ROLE_PERMISSIONS,
    ADMIN_ROLE_PERMISSIONS,
    ADMIN_FULL_ROLE_PERMISSIONS,
    USERS_GRANT_SUPERADMIN,
    BUILTIN_PERMISSIONS,
)

# Doc 43 round 4 (2026-05-08): legacy roles retired (mirrors user-mgmt).
# member / viewer / vendor were superseded by doc-41 scoped tiers
# (project_member / division_member / org_admin). Production verified
# zero holders before the seed was removed; the cleanup loop below
# deletes any drifted rows on every boot.
_RETIRED_LEGACY_ROLE_NAMES: tuple[str, ...] = ("member", "viewer", "vendor")
from ..models.permission import PermissionModel
from ..models.role import RoleModel
from ..models.role_permission import RolePermissionModel
from ..models.user_permission import UserPermissionModel
from ..models.user_role import UserRoleModel
from ..models.user_role_assignment import UserRoleAssignmentModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RbacRepository:
    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------
    # Effective permissions for a user
    # -------------------------------------------------------------------

    def effective_permissions_for_user(self, user_id: str) -> Set[str]:
        """Union of role-derived (legacy + scoped) and direct grants.

        Doc 41: union now includes scoped role assignments
        (``user_role_assignments``) too — across every scope.
        """
        if user_id is None:
            return set()
        legacy_role_codes = {
            r[0]
            for r in self.db.query(RolePermissionModel.permission_code)
            .join(UserRoleModel, UserRoleModel.role_id == RolePermissionModel.role_id)
            .filter(UserRoleModel.user_id == user_id)
            .all()
        }
        scoped_role_codes = {
            r[0]
            for r in self.db.query(RolePermissionModel.permission_code)
            .join(
                UserRoleAssignmentModel,
                UserRoleAssignmentModel.role_id == RolePermissionModel.role_id,
            )
            .filter(UserRoleAssignmentModel.user_id == user_id)
            .all()
        }
        direct_codes = {
            r[0]
            for r in self.db.query(UserPermissionModel.permission_code)
            .filter(UserPermissionModel.user_id == user_id)
            .all()
        }
        return legacy_role_codes | scoped_role_codes | direct_codes

    def effective_permissions_by_scope(
        self, user_id: str,
    ) -> Dict[Tuple[str, Optional[str]], Set[str]]:
        """Doc 41 — return permissions grouped by scope key.

        Output shape::

            {
                ("global", None):           {<perm code>, ...},
                ("org", "<vendor_id>"):     {<perm code>, ...},
                ("project", "<project_id>"): {<perm code>, ...},
            }

        Used by ``require_project_permission`` / ``require_org_permission``.
        """
        out: Dict[Tuple[str, Optional[str]], Set[str]] = {}
        if user_id is None:
            return out

        legacy = (
            self.db.query(RolePermissionModel.permission_code)
            .join(UserRoleModel, UserRoleModel.role_id == RolePermissionModel.role_id)
            .filter(UserRoleModel.user_id == user_id)
            .all()
        )
        if legacy:
            out.setdefault(("global", None), set()).update(r[0] for r in legacy)

        directs = (
            self.db.query(UserPermissionModel.permission_code)
            .filter(UserPermissionModel.user_id == user_id)
            .all()
        )
        if directs:
            out.setdefault(("global", None), set()).update(r[0] for r in directs)

        scoped = (
            self.db.query(
                RolePermissionModel.permission_code,
                UserRoleAssignmentModel.organization_id,
                UserRoleAssignmentModel.project_id,
            )
            .join(
                UserRoleAssignmentModel,
                UserRoleAssignmentModel.role_id == RolePermissionModel.role_id,
            )
            .filter(UserRoleAssignmentModel.user_id == user_id)
            .all()
        )
        for code, org_id, project_id in scoped:
            if project_id is not None:
                key = ("project", project_id)
            elif org_id is not None:
                key = ("org", org_id)
            else:
                key = ("global", None)
            out.setdefault(key, set()).add(code)
        return out

    def user_has_admin_role(self, user_id: str) -> bool:
        """True iff the user holds admin or super_admin globally.

        Doc 41 widens this to include super_admin (a strict superset of
        admin) and to honour global rows in ``user_role_assignments``.
        """
        if user_id is None:
            return False
        admin_names = (ADMIN_ROLE_NAME, SUPER_ADMIN_ROLE_NAME)
        legacy = (
            self.db.query(
                exists().where(
                    and_(
                        UserRoleModel.user_id == user_id,
                        UserRoleModel.role_id == RoleModel.id,
                        RoleModel.name.in_(admin_names),
                    )
                )
            ).scalar()
            or False
        )
        if legacy:
            return True
        scoped = (
            self.db.query(
                exists().where(
                    and_(
                        UserRoleAssignmentModel.user_id == user_id,
                        UserRoleAssignmentModel.role_id == RoleModel.id,
                        UserRoleAssignmentModel.organization_id.is_(None),
                        UserRoleAssignmentModel.project_id.is_(None),
                        RoleModel.name.in_(admin_names),
                    )
                )
            ).scalar()
            or False
        )
        return scoped

    # -------------------------------------------------------------------
    # Permission catalog CRUD
    # -------------------------------------------------------------------

    def list_permissions(
        self, *, offset: int = 0, limit: int = 100,
    ) -> Tuple[List[PermissionModel], int]:
        total = self.db.query(func.count(PermissionModel.code)).scalar() or 0
        rows = (
            self.db.query(PermissionModel)
            .order_by(PermissionModel.code.asc())
            .offset(offset).limit(limit)
            .all()
        )
        return rows, total

    def get_permission(self, code: str) -> Optional[PermissionModel]:
        return (
            self.db.query(PermissionModel)
            .filter(PermissionModel.code == code)
            .first()
        )

    def create_permission(
        self, *, code: str, name: str, description: Optional[str],
        is_builtin: bool = False,
    ) -> PermissionModel:
        row = PermissionModel(
            code=code, name=name, description=description, is_builtin=is_builtin,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def update_permission(
        self, code: str, *, name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[PermissionModel]:
        row = self.get_permission(code)
        if row is None:
            return None
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        self.db.flush()
        return row

    def delete_permission(self, code: str) -> bool:
        row = self.get_permission(code)
        if row is None:
            return False
        # Cascade: remove role-grants and direct-grants for this code.
        self.db.execute(
            delete(RolePermissionModel).where(
                RolePermissionModel.permission_code == code
            )
        )
        self.db.execute(
            delete(UserPermissionModel).where(
                UserPermissionModel.permission_code == code
            )
        )
        self.db.delete(row)
        self.db.flush()
        return True

    # -------------------------------------------------------------------
    # Role queries
    # -------------------------------------------------------------------

    def get_role(self, role_id: int) -> Optional[RoleModel]:
        return (
            self.db.query(RoleModel).filter(RoleModel.id == role_id).first()
        )

    def get_role_by_name(self, name: str) -> Optional[RoleModel]:
        return (
            self.db.query(RoleModel).filter(RoleModel.name == name).first()
        )

    def list_role_permissions(self, role_id: int) -> List[str]:
        return sorted(
            r[0]
            for r in self.db.query(RolePermissionModel.permission_code)
            .filter(RolePermissionModel.role_id == role_id)
            .all()
        )

    # -------------------------------------------------------------------
    # Role-permission grants
    # -------------------------------------------------------------------

    def grant_permissions_to_role(
        self, role_id: int, codes: Iterable[str],
    ) -> int:
        existing = {
            r[0]
            for r in self.db.query(RolePermissionModel.permission_code)
            .filter(RolePermissionModel.role_id == role_id)
            .all()
        }
        added = 0
        for c in codes:
            if c in existing:
                continue
            self.db.add(RolePermissionModel(role_id=role_id, permission_code=c))
            existing.add(c)
            added += 1
        if added:
            self.db.flush()
        return added

    def revoke_permission_from_role(
        self, role_id: int, code: str,
    ) -> bool:
        row = (
            self.db.query(RolePermissionModel)
            .filter(
                RolePermissionModel.role_id == role_id,
                RolePermissionModel.permission_code == code,
            )
            .first()
        )
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True

    def _align_role_permissions(
        self, role_id: int, canonical_codes: Iterable[str],
    ) -> None:
        """Doc 44 round 5 — make the role's permission set EXACTLY match
        ``canonical_codes`` on every boot (mirror of user-mgmt's helper).

        Adds missing rows, removes rows whose code isn't canonical.
        Used by the seed loop's self-heal step so spec changes to
        scoped-role permission sets propagate to existing DBs without
        manual SQL.
        """
        desired = set(canonical_codes)
        existing = {
            r[0]
            for r in self.db.query(RolePermissionModel.permission_code)
            .filter(RolePermissionModel.role_id == role_id)
            .all()
        }
        to_add = desired - existing
        to_remove = existing - desired
        for code in to_add:
            self.db.add(RolePermissionModel(
                role_id=role_id, permission_code=code,
            ))
        if to_remove:
            self.db.query(RolePermissionModel).filter(
                RolePermissionModel.role_id == role_id,
                RolePermissionModel.permission_code.in_(to_remove),
            ).delete(synchronize_session=False)
        self.db.flush()

    def replace_role_permissions(
        self, role_id: int, codes: Iterable[str],
    ) -> None:
        desired = set(codes)
        existing = {
            r[0]
            for r in self.db.query(RolePermissionModel.permission_code)
            .filter(RolePermissionModel.role_id == role_id)
            .all()
        }
        to_remove = existing - desired
        if to_remove:
            self.db.execute(
                delete(RolePermissionModel).where(
                    and_(
                        RolePermissionModel.role_id == role_id,
                        RolePermissionModel.permission_code.in_(to_remove),
                    )
                )
            )
        to_add = desired - existing
        for c in to_add:
            self.db.add(RolePermissionModel(role_id=role_id, permission_code=c))
        self.db.flush()

    # -------------------------------------------------------------------
    # User-role assignments
    # -------------------------------------------------------------------

    def list_roles_for_user(self, user_id: str) -> List[RoleModel]:
        return (
            self.db.query(RoleModel)
            .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
            .filter(UserRoleModel.user_id == user_id)
            .order_by(RoleModel.name.asc())
            .all()
        )

    def assign_role_to_user(
        self, user_id: str, role_id: int, *, actor_id: Optional[str] = None,
    ) -> bool:
        existing = (
            self.db.query(UserRoleModel)
            .filter(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_id == role_id,
            )
            .first()
        )
        if existing is not None:
            return False
        self.db.add(
            UserRoleModel(user_id=user_id, role_id=role_id, created_by=actor_id)
        )
        self.db.flush()
        return True

    def unassign_role_from_user(self, user_id: str, role_id: int) -> bool:
        row = (
            self.db.query(UserRoleModel)
            .filter(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_id == role_id,
            )
            .first()
        )
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True

    def count_users_with_role(self, role_id: int) -> int:
        # Joined count against users.deleted_at so soft-deleted holders don't
        # count toward the lockout protection. Local import to avoid cycles.
        from ..models.user import UserModel
        return (
            self.db.query(func.count(UserRoleModel.user_id))
            .join(UserModel, UserModel.id == UserRoleModel.user_id)
            .filter(UserRoleModel.role_id == role_id)
            .filter(UserModel.deleted_at.is_(None))
            .scalar()
        ) or 0

    # -------------------------------------------------------------------
    # Direct user-permission grants
    # -------------------------------------------------------------------

    def list_direct_permissions_for_user(self, user_id: str) -> List[str]:
        return sorted(
            r[0]
            for r in self.db.query(UserPermissionModel.permission_code)
            .filter(UserPermissionModel.user_id == user_id)
            .all()
        )

    def grant_permission_to_user(
        self, user_id: str, code: str, *, actor_id: Optional[str] = None,
    ) -> bool:
        existing = (
            self.db.query(UserPermissionModel)
            .filter(
                UserPermissionModel.user_id == user_id,
                UserPermissionModel.permission_code == code,
            )
            .first()
        )
        if existing is not None:
            return False
        self.db.add(
            UserPermissionModel(
                user_id=user_id, permission_code=code, created_by=actor_id,
            )
        )
        self.db.flush()
        return True

    def revoke_permission_from_user(self, user_id: str, code: str) -> bool:
        row = (
            self.db.query(UserPermissionModel)
            .filter(
                UserPermissionModel.user_id == user_id,
                UserPermissionModel.permission_code == code,
            )
            .first()
        )
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True

    # -------------------------------------------------------------------
    # Startup sync — idempotent, safe to call on every boot
    # -------------------------------------------------------------------

    def sync_builtin_permissions(self) -> Tuple[int, int]:
        """Upsert every code in ``BUILTIN_PERMISSIONS`` into the catalog,
        ensure the ``admin``/``member``/``viewer`` roles exist, and ensure
        the ``admin`` role holds every permission currently in the registry.

        Returns ``(permissions_inserted, role_grants_added)`` for logging.
        """
        permissions_inserted = 0
        for p in BUILTIN_PERMISSIONS:
            row = self.get_permission(p.code)
            if row is None:
                self.create_permission(
                    code=p.code,
                    name=p.name,
                    description=p.description,
                    is_builtin=True,
                )
                permissions_inserted += 1
            else:
                # Refresh built-in metadata so renames in code propagate.
                if row.name != p.name or row.description != p.description:
                    row.name = p.name
                    row.description = p.description
                if not row.is_builtin:
                    row.is_builtin = True
        self.db.flush()

        # Ensure seed roles exist. Descriptions are REFRESHED on every
        # boot so seed-string updates propagate to the live row without
        # DB surgery. Descriptions are FE-visible (returned via
        # /api/v3/master/roles) so they read as user-facing prose — NO
        # internal doc / commit references.
        seed_roles = (
            (ADMIN_ROLE_NAME, "Built-in admin role. Holds every permission except the ability to grant super_admin. Cannot grant the admin or super_admin roles to other users — only super_admin can. Cannot be deleted."),
            (SUPER_ADMIN_ROLE_NAME, "Built-in super_admin role. Holds every permission. The only role that can grant the super_admin or admin roles to other users."),
            (ORG_ADMIN_ROLE_NAME, "Manages users and project memberships within a vendor (organization). Cannot edit project content directly. Can grant project-tier roles only on projects in their vendor."),
            (PROJECT_ADMIN_ROLE_NAME, "Manages tasks, subtasks, and project memberships on a single project. Can grant project_member on that project. Cannot edit milestones / activities or grant project_admin / higher roles."),
            (PROJECT_MEMBER_ROLE_NAME, "Reads project content and contributes task / subtask updates, comments, and attachments. Cannot grant any role."),
            (DIVISION_MEMBER_ROLE_NAME, "Read-only on assigned projects. Workbox / approval workflow not yet enabled."),
        )
        for role_name, role_desc in seed_roles:
            existing = self.get_role_by_name(role_name)
            if existing is None:
                self.db.add(RoleModel(
                    name=role_name, description=role_desc, builtin=True,
                ))
            elif existing.description != role_desc and existing.builtin:
                existing.description = role_desc
        self.db.flush()

        admin_role = self.get_role_by_name(ADMIN_ROLE_NAME)
        super_admin_role = self.get_role_by_name(SUPER_ADMIN_ROLE_NAME)
        org_admin_role = self.get_role_by_name(ORG_ADMIN_ROLE_NAME)
        project_admin_role = self.get_role_by_name(PROJECT_ADMIN_ROLE_NAME)
        project_member_role = self.get_role_by_name(PROJECT_MEMBER_ROLE_NAME)
        division_member_role = self.get_role_by_name(DIVISION_MEMBER_ROLE_NAME)

        # super_admin holds every permission (the new top-tier).
        self.grant_permissions_to_role(super_admin_role.id, SUPER_ADMIN_ROLE_PERMISSIONS)
        # 'admin' role: doc-42b demotion. Used to be granted every code
        # (functionally identical to super_admin). Now seeded with
        # ADMIN_FULL_ROLE_PERMISSIONS (every code EXCEPT
        # users:grant_superadmin). The unconditional revoke below
        # self-heals any drift on existing deploys.
        added = self.grant_permissions_to_role(admin_role.id, ADMIN_FULL_ROLE_PERMISSIONS)
        self.revoke_permission_from_role(admin_role.id, USERS_GRANT_SUPERADMIN)
        # Doc 41 scoped roles — seed only if empty.
        if not self.list_role_permissions(org_admin_role.id):
            self.grant_permissions_to_role(org_admin_role.id, ORG_ADMIN_ROLE_PERMISSIONS)
        if not self.list_role_permissions(project_admin_role.id):
            self.grant_permissions_to_role(project_admin_role.id, PROJECT_ADMIN_ROLE_PERMISSIONS)
        if not self.list_role_permissions(project_member_role.id):
            self.grant_permissions_to_role(project_member_role.id, PROJECT_MEMBER_ROLE_PERMISSIONS)
        if not self.list_role_permissions(division_member_role.id):
            self.grant_permissions_to_role(division_member_role.id, DIVISION_MEMBER_ROLE_PERMISSIONS)

        # Doc 44 round 5 — boot-time self-heal on existing DBs (mirror
        # of user-mgmt). Each call is idempotent — adds missing perms,
        # removes any not in the canonical list. Without this, a spec
        # change to a scoped role's permission set drifts forever on
        # already-seeded deployments.
        self._align_role_permissions(org_admin_role.id, ORG_ADMIN_ROLE_PERMISSIONS)
        self._align_role_permissions(project_admin_role.id, PROJECT_ADMIN_ROLE_PERMISSIONS)
        self._align_role_permissions(project_member_role.id, PROJECT_MEMBER_ROLE_PERMISSIONS)
        self._align_role_permissions(division_member_role.id, DIVISION_MEMBER_ROLE_PERMISSIONS)

        # Doc 43 round 4: drop legacy member/viewer/vendor on every boot.
        # Skip the delete if any user still holds the role; log a warning
        # so an operator can clean up manually. Fresh DBs never see these
        # roles since the seed loop above no longer creates them.
        for legacy_name in _RETIRED_LEGACY_ROLE_NAMES:
            row = self.get_role_by_name(legacy_name)
            if row is None:
                continue
            legacy_holders = (
                self.db.query(UserRoleModel)
                .filter(UserRoleModel.role_id == row.id).count()
            )
            scoped_holders = (
                self.db.query(UserRoleAssignmentModel)
                .filter(UserRoleAssignmentModel.role_id == row.id).count()
            )
            if legacy_holders + scoped_holders > 0:
                import logging
                logging.getLogger(__name__).warning(
                    "Legacy role '%s' still has %d holders (legacy + scoped) "
                    "— skipping cleanup. Reassign users before next boot.",
                    legacy_name, legacy_holders + scoped_holders,
                )
                continue
            self.db.query(RolePermissionModel).filter(
                RolePermissionModel.role_id == row.id,
            ).delete()
            self.db.delete(row)

        self.db.flush()
        return permissions_inserted, added
