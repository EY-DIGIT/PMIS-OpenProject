"""
Work Package delete service.
"""
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from .....shared.service_result import ServiceResult


def delete_work_package(
    db: Session,
    work_package_id: int,
) -> ServiceResult[None]:
    """
    Delete a work package.

    Args:
        db: Database session
        work_package_id: Work package ID

    Returns:
        ServiceResult with success or error
    """
    repository = WorkPackageRepository(db)

    # Verify work package exists
    wp = repository.get_by_id(work_package_id)
    if not wp:
        return ServiceResult.fail(
            error=f"Work package with ID {work_package_id} does not exist",
            error_type="not_found"
        )

    # Check for subtasks
    subtasks = repository.list_subtasks(work_package_id)
    if subtasks:
        return ServiceResult.fail(
            error="Cannot delete work package with subtasks. Delete subtasks first.",
            error_type="validation_error"
        )

    # Delete work package
    try:
        deleted = repository.delete(work_package_id)
        if deleted:
            return ServiceResult.ok(None)
        else:
            return ServiceResult.fail(
                error="Failed to delete work package",
                error_type="database_error"
            )
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to delete work package: {str(e)}",
            error_type="database_error"
        )
