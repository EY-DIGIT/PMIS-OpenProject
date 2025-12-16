"""
User listing service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.service_result import ServiceResult
from .....shared.pagination import PaginatedResult, calculate_offset


def list_users(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    is_admin: bool = False
) -> ServiceResult[PaginatedResult]:
    """
    List users with pagination.

    Args:
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        status: Optional status filter
        is_admin: Whether requesting user is admin

    Returns:
        ServiceResult with paginated users or error
    """
    # Validate pagination parameters
    if page < 1:
        return ServiceResult.fail(
            error="Page number must be >= 1",
            error_type="validation_error"
        )

    if page_size < 1 or page_size > 100:
        return ServiceResult.fail(
            error="Page size must be between 1 and 100",
            error_type="validation_error"
        )

    # Non-admin users can only see active users
    if not is_admin and status is None:
        status = "active"
    elif not is_admin and status != "active":
        return ServiceResult.fail(
            error="Only admin users can filter by non-active status",
            error_type="authorization_error"
        )

    # Calculate offset
    offset = calculate_offset(page, page_size)

    # Fetch users
    repository = UserRepository(db)

    try:
        users, total = repository.list(
            offset=offset,
            limit=page_size,
            status=status
        )

        result = PaginatedResult(
            items=users,
            total=total,
            page=page,
            page_size=page_size
        )

        return ServiceResult.ok(result)

    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to list users: {str(e)}",
            error_type="internal_error"
        )
