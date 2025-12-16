"""
Project creation service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....core.errors import ValidationError, AlreadyExistsError
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string


def create_project(
    db: Session,
    identifier: str,
    name: str,
    description: Optional[str] = None,
    active: bool = True,
    public: bool = False,
    status_explanation: Optional[str] = None,
    parent_id: Optional[int] = None,
) -> ServiceResult[Project]:
    """
    Create a new project.

    Args:
        db: Database session
        identifier: Project identifier
        name: Project name
        description: Project description
        active: Whether project is active
        public: Whether project is public
        status_explanation: Project status explanation
        parent_id: Parent project ID

    Returns:
        ServiceResult with created project or error
    """
    # Normalize inputs
    identifier = normalize_string(identifier).lower()
    name = normalize_string(name)

    # Validate identifier
    if not identifier or len(identifier) > 255:
        return ServiceResult.fail(
            error="Invalid identifier. Must be 1-255 characters.",
            error_type="validation_error"
        )

    # Validate identifier format (alphanumeric, hyphen, underscore)
    if not all(c.isalnum() or c in "-_" for c in identifier):
        return ServiceResult.fail(
            error="Invalid identifier format. Only alphanumeric, hyphens, and underscores allowed.",
            error_type="validation_error"
        )

    # Validate name
    if not name or len(name) > 255:
        return ServiceResult.fail(
            error="Invalid name. Must be 1-255 characters.",
            error_type="validation_error"
        )

    # Validate description length
    if description and len(description) > 5000:
        return ServiceResult.fail(
            error="Description too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    # Validate status explanation length
    if status_explanation and len(status_explanation) > 5000:
        return ServiceResult.fail(
            error="Status explanation too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    # Check for existing project
    repository = ProjectRepository(db)

    if repository.exists_by_identifier(identifier):
        return ServiceResult.fail(
            error=f"Project with identifier '{identifier}' already exists",
            error_type="already_exists"
        )

    # Validate parent project if specified
    if parent_id is not None and not repository.exists_by_id(parent_id):
        return ServiceResult.fail(
            error=f"Parent project with ID {parent_id} does not exist",
            error_type="not_found"
        )

    # Create project
    try:
        project = repository.create(
            identifier=identifier,
            name=name,
            description=description,
            active=active,
            public=public,
            status_explanation=status_explanation,
            parent_id=parent_id,
        )

        return ServiceResult.ok(project)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to create project: {str(e)}",
            error_type="internal_error"
        )
