"""
Role-Based Access Control (RBAC) system.
"""
from enum import Enum
from typing import Set, Dict


class Role(str, Enum):
    """User roles in the system."""
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    ANONYMOUS = "anonymous"


class Permission(str, Enum):
    """System permissions."""
    # User permissions
    USERS_CREATE = "users:create"
    USERS_READ = "users:read"
    USERS_READ_ALL = "users:read_all"
    USERS_UPDATE = "users:update"
    USERS_UPDATE_ALL = "users:update_all"
    USERS_DELETE = "users:delete"
    USERS_DELETE_ALL = "users:delete_all"


# Role -> Permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.USERS_CREATE,
        Permission.USERS_READ,
        Permission.USERS_READ_ALL,
        Permission.USERS_UPDATE,
        Permission.USERS_UPDATE_ALL,
        Permission.USERS_DELETE,
        Permission.USERS_DELETE_ALL,
    },
    Role.MEMBER: {
        Permission.USERS_READ,
        Permission.USERS_UPDATE,
    },
    Role.VIEWER: {
        Permission.USERS_READ,
    },
    Role.ANONYMOUS: set(),
}


def has_permission(role: Role, permission: Permission) -> bool:
    """
    Check if a role has a specific permission.

    Args:
        role: User role
        permission: Required permission

    Returns:
        True if role has permission, False otherwise
    """
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_role_permissions(role: Role) -> Set[Permission]:
    """
    Get all permissions for a role.

    Args:
        role: User role

    Returns:
        Set of permissions for the role
    """
    return ROLE_PERMISSIONS.get(role, set())
