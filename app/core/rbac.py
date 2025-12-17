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
    
    # Project permissions
    PROJECTS_CREATE = "projects:create"
    PROJECTS_READ = "projects:read"
    PROJECTS_READ_ALL = "projects:read_all"
    PROJECTS_UPDATE = "projects:update"
    PROJECTS_UPDATE_ALL = "projects:update_all"
    PROJECTS_DELETE = "projects:delete"
    PROJECTS_DELETE_ALL = "projects:delete_all"
    
    # Project Members permissions
    PROJECT_MEMBERS_READ = "project_members:read"
    PROJECT_MEMBERS_ADD = "project_members:add"
    PROJECT_MEMBERS_UPDATE = "project_members:update"
    PROJECT_MEMBERS_DELETE = "project_members:delete"
    
    # Roles permissions
    ROLES_READ = "roles:read"
    ROLES_CREATE = "roles:create"
    ROLES_UPDATE = "roles:update"
    ROLES_DELETE = "roles:delete"


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
        Permission.PROJECTS_CREATE,
        Permission.PROJECTS_READ,
        Permission.PROJECTS_READ_ALL,
        Permission.PROJECTS_UPDATE,
        Permission.PROJECTS_UPDATE_ALL,
        Permission.PROJECTS_DELETE,
        Permission.PROJECTS_DELETE_ALL,
        Permission.PROJECT_MEMBERS_READ,
        Permission.PROJECT_MEMBERS_ADD,
        Permission.PROJECT_MEMBERS_UPDATE,
        Permission.PROJECT_MEMBERS_DELETE,
        Permission.ROLES_READ,
        Permission.ROLES_CREATE,
        Permission.ROLES_UPDATE,
        Permission.ROLES_DELETE,
    },
    Role.MEMBER: {
        Permission.USERS_READ,
        Permission.USERS_UPDATE,
        Permission.PROJECTS_READ,
        Permission.PROJECTS_CREATE,
        Permission.PROJECTS_UPDATE,
        Permission.PROJECT_MEMBERS_READ,
        Permission.PROJECT_MEMBERS_ADD,
        Permission.PROJECT_MEMBERS_UPDATE,
    },
    Role.VIEWER: {
        Permission.USERS_READ,
        Permission.PROJECTS_READ,
        Permission.PROJECT_MEMBERS_READ,
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
