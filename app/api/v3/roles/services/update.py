"""
Role update service.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.role_repository import RoleRepository
from .....domain.roles.role import Role
from .....shared.service_result import ServiceResult


def update_role(
    db: Session,
    role_id: int,
    name: Optional[str] = None,
    permissions: Optional[List[str]] = None
) -> ServiceResult[Role]:
    """
    Update a role.

    Args:
        db: Database session
        role_id: Role ID to update
        name: New role name
        permissions: New permissions list

    Returns:
        ServiceResult with updated role or error
    """
    repository = RoleRepository(db)

    # Check if role exists
    role = repository.get_by_id(role_id)
    if not role:
        return ServiceResult.fail(
            error=f"Role with ID {role_id} not found",
            error_type="not_found"
        )

    # Cannot modify builtin roles
    if role.builtin:
        return ServiceResult.fail(
            error="Cannot modify builtin roles",
            error_type="forbidden"
        )

    # Validate name if provided
    if name is not None:
        if not isinstance(name, str) or len(name) == 0:
            return ServiceResult.fail(
                error="Role name must be a non-empty string",
                error_type="validation_error"
            )

        if len(name) > 255:
            return ServiceResult.fail(
                error="Role name must not exceed 255 characters",
                error_type="validation_error"
            )

        # Check for duplicate name
        existing = repository.get_by_name(name)
        if existing and existing.id != role_id:
            return ServiceResult.fail(
                error=f"Role with name '{name}' already exists",
                error_type="already_exists"
            )

    # Validate permissions if provided
    if permissions is not None:
        if not isinstance(permissions, list):
            return ServiceResult.fail(
                error="Permissions must be a list",
                error_type="validation_error"
            )

    try:
        updated_role = repository.update(
            role_id=role_id,
            name=name,
            permissions=permissions
        )
        return ServiceResult.ok(updated_role)
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to update role: {str(e)}",
            error_type="database_error"
        )
