"""
Project read service.
"""
from sqlalchemy.orm import Session
from .....core.errors import NotFoundError
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult


def get_project_by_id(db: Session, project_id: int) -> ServiceResult[Project]:
    """
    Get project by ID.

    Args:
        db: Database session
        project_id: Project ID

    Returns:
        ServiceResult with project or error
    """
    repository = ProjectRepository(db)
    project = repository.get_by_id(project_id)

    if not project:
        return ServiceResult.fail(
            error=f"Project with ID {project_id} not found",
            error_type="not_found"
        )

    return ServiceResult.ok(project)


def get_project_by_identifier(db: Session, identifier: str) -> ServiceResult[Project]:
    """
    Get project by identifier.

    Args:
        db: Database session
        identifier: Project identifier

    Returns:
        ServiceResult with project or error
    """
    repository = ProjectRepository(db)
    project = repository.get_by_identifier(identifier)

    if not project:
        return ServiceResult.fail(
            error=f"Project with identifier '{identifier}' not found",
            error_type="not_found"
        )

    return ServiceResult.ok(project)
