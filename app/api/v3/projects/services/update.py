"""
Project update service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string


def update_project(
    db: Session,
    project_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    active: Optional[bool] = None,
    public: Optional[bool] = None,
    status_explanation: Optional[str] = None,
    parent_id: Optional[int] = None,
) -> ServiceResult[Project]:
    """
    Update a project.

    Args:
        db: Database session
        project_id: Project ID
        name: New project name
        description: New project description
        active: New active status
        public: New public status
        status_explanation: New status explanation
        parent_id: New parent project ID

    Returns:
        ServiceResult with updated project or error
    """
    repository = ProjectRepository(db)

    # Check if project exists
    project = repository.get_by_id(project_id)
    if not project:
        return ServiceResult.fail(
            error=f"Project with ID {project_id} not found",
            error_type="not_found"
        )

    # Validate name if provided
    if name is not None:
        name = normalize_string(name)
        if not name or len(name) > 255:
            return ServiceResult.fail(
                error="Invalid name. Must be 1-255 characters.",
                error_type="validation_error"
            )

    # Validate description if provided
    if description is not None and len(description) > 5000:
        return ServiceResult.fail(
            error="Description too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    # Validate status explanation if provided
    if status_explanation is not None and len(status_explanation) > 5000:
        return ServiceResult.fail(
            error="Status explanation too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    # Validate parent project if specified
    if parent_id is not None and parent_id != project.parent_id:
        if not repository.exists_by_id(parent_id):
            return ServiceResult.fail(
                error=f"Parent project with ID {parent_id} does not exist",
                error_type="not_found"
            )

    # Update project
    try:
        updated = repository.update(
            project_id=project_id,
            name=name,
            description=description,
            active=active,
            public=public,
            status_explanation=status_explanation,
            parent_id=parent_id,
        )

        if not updated:
            return ServiceResult.fail(
                error=f"Project with ID {project_id} not found",
                error_type="not_found"
            )

        return ServiceResult.ok(updated)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to update project: {str(e)}",
            error_type="internal_error"
        )
