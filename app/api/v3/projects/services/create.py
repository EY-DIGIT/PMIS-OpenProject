"""
Project creation service.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .....core.errors import ValidationError, AlreadyExistsError
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string


def verify_user_exists(db: Session, username: str) -> bool:
    """
    Verify if a user exists in the system by username.
    
    This is a placeholder function that queries the user repository.
    In production, integrate with your auth service to validate usernames.
    
    Args:
        db: Database session
        username: Username to verify
        
    Returns:
        True if user exists, False otherwise
    """
    user_repo = UserRepository(db)
    user = user_repo.get_by_login(username)
    return user is not None


def create_project(
    db: Session,
    identifier: str,
    name: str,
    description: Optional[str] = None,
    active: bool = True,
    public: bool = False,
    status_explanation: Optional[str] = None,
    parent_id: Optional[int] = None,
    status: str = "new",
    owner: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
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
        status: Project status (from PROJECT_STATUS_CHOICES in schemas.py)
        owner: Project owner username
        category: Project category (from PROJECT_CATEGORY_CHOICES in schemas.py)
        start_date: Project start date (must be in future)
        end_date: Project end date (must be in future and after start_date)

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

    # Validate dates: must be in the future
    if start_date is not None and start_date <= datetime.now(timezone.utc):
        return ServiceResult.fail(
            error="start_date must be in the future",
            error_type="validation_error"
        )

    if end_date is not None and end_date <= datetime.now(timezone.utc):
        return ServiceResult.fail(
            error="end_date must be in the future",
            error_type="validation_error"
        )

    # Validate end_date is after start_date
    if start_date is not None and end_date is not None and end_date <= start_date:
        return ServiceResult.fail(
            error="end_date must be after start_date",
            error_type="validation_error"
        )

    # Validate owner: must be a valid username in the system
    if owner is not None:
        if not verify_user_exists(db, owner):
            return ServiceResult.fail(
                error=f"Owner user with username '{owner}' does not exist. Verify the user exists by checking the users endpoint.",
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
            status=status,
            owner=owner,
            category=category,
            start_date=start_date,
            end_date=end_date,
        )

        return ServiceResult.ok(project)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to create project: {str(e)}",
            error_type="internal_error"
        )
