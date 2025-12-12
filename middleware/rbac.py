"""
Role-Based Access Control (RBAC) middleware and decorators.

Provides authorization checks at the routing level based on user roles and permissions.
"""

from typing import Optional, List, Callable, Any
from functools import wraps
from fastapi import HTTPException, status, Depends
from enum import Enum

try:
    from ..models.user import User
    from ..api.dependencies import get_current_user
except ImportError:
    from models.user import User
    from api.dependencies import get_current_user


class Permission(str, Enum):
    """
    OpenProject-style permissions.

    Global permissions:
    - MANAGE_USER: Create, modify, delete users
    - CREATE_PROJECT: Create new projects
    - ADMIN: Full system administration

    Project-level permissions (checked with project context):
    - VIEW_PROJECT: View project details
    - EDIT_PROJECT: Modify project settings
    - DELETE_PROJECT: Delete projects
    - MANAGE_MEMBERS: Add/remove project members
    - VIEW_MEMBERS: View project members
    - MANAGE_MEETINGS: Create/edit/delete meetings
    - VIEW_MEETINGS: View meetings
    """
    # Global permissions
    MANAGE_USER = "manage_user"
    CREATE_PROJECT = "create_project"
    ADMIN = "admin"

    # Project permissions
    VIEW_PROJECT = "view_project"
    EDIT_PROJECT = "edit_project"
    DELETE_PROJECT = "delete_project"
    MANAGE_MEMBERS = "manage_members"
    VIEW_MEMBERS = "view_members"
    MANAGE_MEETINGS = "manage_meetings"
    VIEW_MEETINGS = "view_meetings"


class Role(str, Enum):
    """
    User roles in the system.
    """
    ADMIN = "admin"
    USER = "user"
    MEMBER = "member"
    GUEST = "guest"


class RBACMiddleware:
    """
    RBAC Middleware for FastAPI.

    This class provides utilities for role-based authorization checks.
    """

    @staticmethod
    def has_global_permission(user: User, permission: Permission) -> bool:
        """
        Check if user has a global permission.

        Args:
            user: The user to check
            permission: The permission to verify

        Returns:
            True if user has the permission, False otherwise
        """
        # Admins have all permissions
        if user.admin:
            return True

        # Map specific permissions to user attributes/roles
        permission_checks = {
            Permission.ADMIN: lambda u: u.admin,
            Permission.MANAGE_USER: lambda u: u.admin,
            Permission.CREATE_PROJECT: lambda u: u.admin or u.is_active(),
        }

        check_func = permission_checks.get(permission)
        if check_func:
            return check_func(user)

        # Default: regular active users have basic permissions
        return user.is_active()

    @staticmethod
    def has_project_permission(
        user: User,
        permission: Permission,
        project_id: Optional[int] = None,
        project = None
    ) -> bool:
        """
        Check if user has a project-level permission.

        Args:
            user: The user to check
            permission: The permission to verify
            project_id: Optional project ID
            project: Optional project object

        Returns:
            True if user has the permission in the project context
        """
        # Admins have all permissions
        if user.admin:
            return True

        # Public read permissions
        if permission in [Permission.VIEW_PROJECT, Permission.VIEW_MEETINGS]:
            if project and hasattr(project, 'public') and project.public:
                return True

        # Check if user is a member of the project
        # TODO: Implement actual project membership check
        # For now, allow if user is active
        if user.is_active():
            return True

        return False

    @staticmethod
    def check_permission(
        user: User,
        permission: Permission,
        project_id: Optional[int] = None,
        project = None
    ) -> None:
        """
        Check permission and raise HTTPException if not authorized.

        Args:
            user: The user to check
            permission: The permission to verify
            project_id: Optional project ID for project-level permissions
            project: Optional project object

        Raises:
            HTTPException: If user lacks the required permission
        """
        # Determine if this is a project-level permission
        project_permissions = {
            Permission.VIEW_PROJECT,
            Permission.EDIT_PROJECT,
            Permission.DELETE_PROJECT,
            Permission.MANAGE_MEMBERS,
            Permission.VIEW_MEMBERS,
            Permission.MANAGE_MEETINGS,
            Permission.VIEW_MEETINGS,
        }

        if permission in project_permissions:
            has_permission = RBACMiddleware.has_project_permission(
                user, permission, project_id, project
            )
        else:
            has_permission = RBACMiddleware.has_global_permission(user, permission)

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission.value} required"
            )


def require_permission(permission: Permission, project_id_param: Optional[str] = None):
    """
    Decorator factory for requiring a specific permission.

    Usage:
        @require_permission(Permission.MANAGE_USER)
        async def create_user(...):
            pass

        @require_permission(Permission.EDIT_PROJECT, project_id_param="project_id")
        async def update_project(project_id: int, ...):
            pass

    Args:
        permission: The required permission
        project_id_param: Name of the parameter containing project_id (for project permissions)

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Extract project_id if specified
            project_id = None
            if project_id_param:
                project_id = kwargs.get(project_id_param)

            # Check permission
            RBACMiddleware.check_permission(current_user, permission, project_id)

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_role(role: Role):
    """
    Decorator factory for requiring a specific role.

    Usage:
        @require_role(Role.ADMIN)
        async def admin_function(...):
            pass

    Args:
        role: The required role

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Check role
            if role == Role.ADMIN and not current_user.admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Administrator role required"
                )

            # USER role just requires active user
            if role == Role.USER and not current_user.is_active():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Active user account required"
                )

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper
    return decorator


# Dependency functions for use with FastAPI Depends

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency to require admin role.

    Usage:
        async def endpoint(current_user: User = Depends(require_admin)):
            pass
    """
    if not current_user.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user


def require_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency to require active user.

    Usage:
        async def endpoint(current_user: User = Depends(require_active_user)):
            pass
    """
    if not current_user.is_active():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active user account required"
        )
    return current_user


def create_permission_dependency(permission: Permission):
    """
    Create a FastAPI dependency for a specific permission.

    Usage:
        require_manage_user = create_permission_dependency(Permission.MANAGE_USER)

        async def endpoint(current_user: User = Depends(require_manage_user)):
            pass
    """
    def check_permission_dependency(current_user: User = Depends(get_current_user)) -> User:
        RBACMiddleware.check_permission(current_user, permission)
        return current_user

    return check_permission_dependency


# Pre-created permission dependencies for common use cases
require_manage_user = create_permission_dependency(Permission.MANAGE_USER)
require_create_project = create_permission_dependency(Permission.CREATE_PROJECT)
require_manage_meetings = create_permission_dependency(Permission.MANAGE_MEETINGS)
