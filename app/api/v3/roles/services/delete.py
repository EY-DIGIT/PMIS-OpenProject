"""
Role deletion service.
"""
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.role_repository import RoleRepository
from .....shared.service_result import ServiceResult


def delete_role(
    db: Session,
    role_id: int
) -> ServiceResult[None]:
    """
    Delete a role.

    Args:
        db: Database session
        role_id: Role ID to delete

    Returns:
        ServiceResult with None or error
    """
    repository = RoleRepository(db)

    # Check if role exists and is not builtin
    role = repository.get_by_id(role_id)
    if not role:
        return ServiceResult.fail(
            error=f"Role with ID {role_id} not found",
            error_type="not_found"
        )

    if role.builtin:
        return ServiceResult.fail(
            error="Cannot delete builtin roles",
            error_type="forbidden"
        )

    try:
        success = repository.delete(role_id)
        if success:
            return ServiceResult.ok(None)
        else:
            return ServiceResult.fail(
                error=f"Failed to delete role with ID {role_id}",
                error_type="database_error"
            )
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to delete role: {str(e)}",
            error_type="database_error"
        )
