"""User listing service."""
from typing import Optional

from sqlalchemy.orm import Session

from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.pagination import PaginatedResult, calculate_offset
from .....shared.service_result import ServiceResult


def list_users(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    is_admin: bool = False,
    include_deleted: bool = False,
    vendor_id_filter: Optional[str] = None,
    exclude_admin_tier: bool = False,
) -> ServiceResult[PaginatedResult]:
    """List users with pagination, newest first.

    Mirror of user-mgmt's service. Round 7 added the vendor scope
    filter; round 10 added admin-tier exclusion. Both default-off so
    legacy callers see no behaviour change. The controller wires the
    filters from caller context.
    """
    if page < 1:
        return ServiceResult.fail(
            error="Page number must be >= 1",
            error_type="validation_error",
        )
    if page_size < 1 or page_size > 200:
        return ServiceResult.fail(
            error="Page size must be between 1 and 200",
            error_type="validation_error",
        )

    if not is_admin and status is None:
        status = "active"
    elif not is_admin and status != "active":
        return ServiceResult.fail(
            error="Only admin users can filter by non-active status",
            error_type="authorization_error",
        )

    if include_deleted and not is_admin:
        return ServiceResult.fail(
            error="Only admin users can view soft-deleted users.",
            error_type="authorization_error",
        )

    offset = calculate_offset(page, page_size)
    repo = UserRepository(db)

    try:
        users, total = repo.list(
            offset=offset,
            limit=page_size,
            status=status,
            include_deleted=include_deleted,
            vendor_id=vendor_id_filter,
            exclude_admin_tier=exclude_admin_tier,
        )
        return ServiceResult.ok(PaginatedResult(
            items=users, total=total, page=page, page_size=page_size,
        ))
    except Exception as e:  # noqa: BLE001
        return ServiceResult.fail(
            error=f"Failed to list users: {e}",
            error_type="internal_error",
        )
