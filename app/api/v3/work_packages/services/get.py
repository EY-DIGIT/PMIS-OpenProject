"""
Work Package get service.
"""
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from .....domain.work_packages.work_package import WorkPackage
from .....shared.service_result import ServiceResult


def get_work_package_by_id(
    db: Session,
    work_package_id: int,
) -> ServiceResult[WorkPackage]:
    """
    Get a work package by ID.

    Args:
        db: Database session
        work_package_id: Work package ID

    Returns:
        ServiceResult with work package or error
    """
    repository = WorkPackageRepository(db)

    wp = repository.get_by_id(work_package_id)
    if not wp:
        return ServiceResult.fail(
            error=f"Work package with ID {work_package_id} does not exist",
            error_type="not_found"
        )

    return ServiceResult.ok(wp)


def get_work_package_by_project_and_id(
    db: Session,
    project_id: str,
    work_package_id: int,
) -> ServiceResult[WorkPackage]:
    """
    Get a work package by project and ID.

    Args:
        db: Database session
        project_id: Project ID
        work_package_id: Work package ID

    Returns:
        ServiceResult with work package or error
    """
    repository = WorkPackageRepository(db)

    # Verify project exists
    if not repository.project_exists(project_id):
        return ServiceResult.fail(
            error=f"Project with ID {project_id} does not exist",
            error_type="not_found"
        )

    wp = repository.get_by_project_and_id(project_id, work_package_id)
    if not wp:
        return ServiceResult.fail(
            error=f"Work package with ID {work_package_id} not found in project {project_id}",
            error_type="not_found"
        )

    return ServiceResult.ok(wp)
