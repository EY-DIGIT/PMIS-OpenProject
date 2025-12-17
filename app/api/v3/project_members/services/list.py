"""
Project members list service.
"""
from typing import Tuple, List
from sqlalchemy.orm import Session
from .....core.errors import NotFoundError
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....domain.project_members.membership import Membership
from .....shared.service_result import ServiceResult


def list_project_members(
    db: Session,
    project_id: int,
    page: int = 1,
    page_size: int = 20,
) -> ServiceResult[Tuple[List[Membership], int]]:
    """
    List members of a project with pagination.

    Args:
        db: Database session
        project_id: Project ID
        page: Page number (1-indexed)
        page_size: Number of items per page

    Returns:
        ServiceResult with (memberships, total count) or error
    """
    # Validate project exists
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        return ServiceResult.fail(
            error=f"Project {project_id} not found",
            error_type="not_found"
        )

    # Validate pagination
    if page < 1:
        return ServiceResult.fail(
            error="Page must be >= 1",
            error_type="validation_error"
        )

    if page_size < 1 or page_size > 100:
        return ServiceResult.fail(
            error="Page size must be 1-100",
            error_type="validation_error"
        )

    # List memberships
    try:
        member_repo = ProjectMemberRepository(db)
        memberships, total = member_repo.list_by_project(
            project_id=project_id,
            page=page,
            page_size=page_size,
        )
        return ServiceResult.ok((memberships, total))
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to list memberships: {str(e)}",
            error_type="internal_error"
        )
