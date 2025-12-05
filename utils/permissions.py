"""
Permission definitions and utilities.

Based on OpenProject stable/16 branch permissions system.
"""
from typing import Dict, List
from sqlalchemy.orm import Session

# Core project permissions
PROJECT_PERMISSIONS = {
    'view_project': {
        'description': 'View project',
        'public': True,
        'require': None
    },
    'search_project': {
        'description': 'Search within project',
        'public': True,
        'require': None
    },
    'edit_project': {
        'description': 'Edit project settings',
        'public': False,
        'require': 'member'
    },
    'edit_project_attributes': {
        'description': 'Edit project custom fields',
        'public': False,
        'require': 'member'
    },
    'manage_members': {
        'description': 'Manage project members',
        'public': False,
        'require': 'member'
    },
    'view_members': {
        'description': 'View project members',
        'public': False,
        'require': None
    },
    'add_subprojects': {
        'description': 'Create subprojects',
        'public': False,
        'require': 'member'
    },
    'archive_project': {
        'description': 'Archive project',
        'public': False,
        'require': 'member'
    },
    'copy_projects': {
        'description': 'Copy project',
        'public': False,
        'require': 'member'
    },
}

# Global permissions (not project-specific)
GLOBAL_PERMISSIONS = {
    'add_project': {
        'description': 'Create new projects',
    },
    'add_portfolios': {
        'description': 'Create portfolios',
    },
    'add_programs': {
        'description': 'Create programs',
    },
}

# Default role configurations
DEFAULT_ROLES = [
    {
        'name': 'Project admin',
        'position': 1,
        'permissions': [
            'view_project',
            'search_project',
            'edit_project',
            'edit_project_attributes',
            'manage_members',
            'view_members',
            'add_subprojects',
            'archive_project',
            'copy_projects',
        ]
    },
    {
        'name': 'Member',
        'position': 2,
        'permissions': [
            'view_project',
            'search_project',
            'view_members',
        ]
    },
    {
        'name': 'Reader',
        'position': 3,
        'permissions': [
            'view_project',
            'search_project',
        ]
    },
]


def seed_default_roles(db: Session):
    """
    Seed default roles with permissions.

    Args:
        db: Database session

    Returns:
        List of created Role objects
    """
    from models import Role, RolePermission

    created_roles = []

    for role_data in DEFAULT_ROLES:
        # Check if role already exists
        existing = db.query(Role).filter_by(name=role_data['name']).first()
        if existing:
            print(f"Role '{role_data['name']}' already exists, skipping")
            continue

        # Create role
        role = Role(
            name=role_data['name'],
            position=role_data['position']
        )
        db.add(role)
        db.flush()

        # Add permissions
        for perm in role_data['permissions']:
            rp = RolePermission(role_id=role.id, permission=perm)
            db.add(rp)

        created_roles.append(role)
        print(f"Created role: {role.name} with {len(role_data['permissions'])} permissions")

    db.commit()
    return created_roles


def get_all_permissions() -> List[str]:
    """Get list of all available permissions"""
    return list(PROJECT_PERMISSIONS.keys()) + list(GLOBAL_PERMISSIONS.keys())


def get_permission_info(permission: str) -> Dict:
    """
    Get information about a specific permission.

    Args:
        permission: Permission string

    Returns:
        Dict with permission info or None if not found
    """
    if permission in PROJECT_PERMISSIONS:
        return PROJECT_PERMISSIONS[permission]
    elif permission in GLOBAL_PERMISSIONS:
        return GLOBAL_PERMISSIONS[permission]
    return None
