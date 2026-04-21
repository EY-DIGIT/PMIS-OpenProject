"""
Work Package list service.
"""
from typing import List, Tuple
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....domain.work_packages.work_package import WorkPackage
from .....shared.service_result import ServiceResult


def list_work_packages_by_project(
    db: Session,
    project_id: str,
    offset: int = 1,
    limit: int = 20,
    parent_id: int = None,
    type_name: str = None,
) -> ServiceResult[Tuple[List[WorkPackage], int]]:
    """
    List work packages in a project.

    Args:
        db: Database session
        project_id: Project ID
        offset: Page number (1-indexed)
        limit: Items per page
        parent_id: Optional parent work package ID

    Returns:
        ServiceResult with (work packages list, total count) or error
    """
    repository = WorkPackageRepository(db)
    project_repo = ProjectRepository(db)

    # Verify project exists
    if not project_repo.exists_by_id(project_id):
        return ServiceResult.fail(
            error=f"Project with ID {project_id} does not exist",
            error_type="not_found"
        )

    # Validate pagination parameters
    if offset < 1:
        return ServiceResult.fail(
            error="Offset must be >= 1",
            error_type="validation_error"
        )

    if limit < 1 or limit > 100:
        return ServiceResult.fail(
            error="Limit must be between 1 and 100",
            error_type="validation_error"
        )

    # Resolve type filter to type_id
    type_id_filter = None
    if type_name:
        type_id_filter = repository.get_type_id_by_internal_name(type_name)
        if type_id_filter is None:
            return ServiceResult.fail(
                error=f"Unknown type '{type_name}'",
                error_type="validation_error"
            )

    try:
        work_packages, total = repository.list_by_project(
            project_id=project_id,
            offset=offset,
            limit=limit,
            parent_id=parent_id,
            type_id=type_id_filter,
        )
        return ServiceResult.ok((work_packages, total))
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to list work packages: {str(e)}",
            error_type="database_error"
        )
