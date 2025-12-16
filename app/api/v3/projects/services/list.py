"""
Project list service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult
from .....shared.pagination import PaginatedResult, calculate_offset


def list_projects(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    active: Optional[bool] = None,
    public: Optional[bool] = None,
) -> ServiceResult[PaginatedResult[Project]]:
    """
    List projects with pagination and optional filtering.

    Args:
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        active: Filter by active status
        public: Filter by public status

    Returns:
        ServiceResult with paginated projects or error
    """
    # Validate pagination parameters
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    if page_size > 100:
        page_size = 100

    repository = ProjectRepository(db)
    offset = calculate_offset(page, page_size)

    # Build query with filters
    try:
        query = db.query(ProjectModel)

        if active is not None:
            query = query.filter(ProjectModel.active == active)
        if public is not None:
            query = query.filter(ProjectModel.public == public)

        # Get total count
        total = query.count()

        # Get paginated results
        models = query.offset(offset).limit(page_size).all()
        projects = [repository._to_domain(m) for m in models]

        result = PaginatedResult(
            items=projects,
            total=total,
            page=page,
            page_size=page_size,
        )

        return ServiceResult.ok(result)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to list projects: {str(e)}",
            error_type="internal_error"
        )
