"""
Project update service.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string


def verify_user_exists(db: Session, username: str) -> bool:
    """
    Verify if a user exists in the system by username.
    
    Args:
        db: Database session
        username: Username to verify
        
    Returns:
        True if user exists, False otherwise
    """
    user_repo = UserRepository(db)
    user = user_repo.get_by_login(username)
    return user is not None


def update_project(
    db: Session,
    project_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    active: Optional[bool] = None,
    public: Optional[bool] = None,
    status_explanation: Optional[str] = None,
    parent_id: Optional[int] = None,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
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
        status: New project status
        owner: New project owner username
        category: New project category
        start_date: New project start date
        end_date: New project end date

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
    # Use existing dates if new ones not provided
    effective_start = start_date if start_date is not None else project.start_date
    effective_end = end_date if end_date is not None else project.end_date
    
    if effective_start is not None and effective_end is not None and effective_end <= effective_start:
        return ServiceResult.fail(
            error="end_date must be after start_date",
            error_type="validation_error"
        )

    # Validate owner: must be a valid username in the system
    if owner is not None and not verify_user_exists(db, owner):
        return ServiceResult.fail(
            error=f"Owner user with username '{owner}' does not exist",
            error_type="validation_error"
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
            status=status,
            owner=owner,
            category=category,
            start_date=start_date,
            end_date=end_date,
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
