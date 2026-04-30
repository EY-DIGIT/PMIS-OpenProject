"""
Project member deletion service.
"""
from sqlalchemy.orm import Session
from .....core.errors import NotFoundError
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....shared.service_result import ServiceResult


def delete_project_member(
    db: Session,
    membership_id: int,
) -> ServiceResult[None]:
    """
    Delete a membership.

    Args:
        db: Database session
        membership_id: Membership ID

    Returns:
        ServiceResult with success or error
    """
    # Validate membership exists
    member_repo = ProjectMemberRepository(db)
    membership = member_repo.get_by_id(membership_id)
    if not membership:
        return ServiceResult.fail(
            error=f"Membership {membership_id} not found",
            error_type="not_found"
        )

    # Delete membership
    try:
        deleted = member_repo.delete(membership_id)
        if deleted:
            return ServiceResult.ok(None)
        else:
            return ServiceResult.fail(
                error=f"Failed to delete membership {membership_id}",
                error_type="internal_error"
            )
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to delete membership: {str(e)}",
            error_type="internal_error"
        )
