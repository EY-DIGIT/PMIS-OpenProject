"""
Project delete service.
"""
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....shared.service_result import ServiceResult


def delete_project(db: Session, project_id: int) -> ServiceResult[None]:
    """
    Delete a project.

    Args:
        db: Database session
        project_id: Project ID

    Returns:
        ServiceResult with None or error
    """
    repository = ProjectRepository(db)

    # Check if project exists
    if not repository.exists_by_id(project_id):
        return ServiceResult.fail(
            error=f"Project with ID {project_id} not found",
            error_type="not_found"
        )

    # Delete project
    try:
        deleted = repository.delete(project_id)

        if not deleted:
            return ServiceResult.fail(
                error=f"Project with ID {project_id} not found",
                error_type="not_found"
            )

        return ServiceResult.ok(None)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to delete project: {str(e)}",
            error_type="internal_error"
        )
