"""
Project member creation service.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from .....core.errors import ValidationError, AlreadyExistsError, NotFoundError
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....domain.project_members.membership import Membership
from .....shared.service_result import ServiceResult


def add_project_member(
    db: Session,
    project_id: str,
    user_id: str,
    roles: Optional[List[str]] = None,
) -> ServiceResult[Membership]:
    """
    Add a user to a project as a member with specified roles.

    Args:
        db: Database session
        project_id: Project ID
        user_id: User ID
        roles: List of role names (default: empty list)

    Returns:
        ServiceResult with created membership or error
    """
    # Validate project exists
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        return ServiceResult.fail(
            error=f"Project {project_id} not found",
            error_type="not_found"
        )

    # Validate user exists
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        return ServiceResult.fail(
            error=f"User {user_id} not found",
            error_type="not_found"
        )

    # Validate roles
    if roles is None:
        roles = []
    
    if not isinstance(roles, list):
        return ServiceResult.fail(
            error="Roles must be a list",
            error_type="validation_error"
        )

    # Check if member already exists
    member_repo = ProjectMemberRepository(db)
    existing = member_repo.get_by_project_and_user(project_id, user_id)
    if existing:
        return ServiceResult.fail(
            error=f"User {user_id} is already a member of project {project_id}",
            error_type="already_exists"
        )

    # Create membership
    try:
        membership = member_repo.create(
            project_id=project_id,
            user_id=user_id,
            roles=roles,
        )
        return ServiceResult.ok(membership)
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to create membership: {str(e)}",
            error_type="internal_error"
        )
