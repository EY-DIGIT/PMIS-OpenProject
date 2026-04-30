"""
Project member update service.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from .....core.errors import NotFoundError, ValidationError
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....domain.project_members.membership import Membership
from .....shared.service_result import ServiceResult


def update_project_member(
    db: Session,
    membership_id: int,
    roles: Optional[List[str]] = None,
) -> ServiceResult[Membership]:
    """
    Update a membership's roles.

    Args:
        db: Database session
        membership_id: Membership ID
        roles: New list of role names

    Returns:
        ServiceResult with updated membership or error
    """
    # Validate membership exists
    member_repo = ProjectMemberRepository(db)
    membership = member_repo.get_by_id(membership_id)
    if not membership:
        return ServiceResult.fail(
            error=f"Membership {membership_id} not found",
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

    # Update membership
    try:
        updated = member_repo.update(
            membership_id=membership_id,
            roles=roles,
        )
        return ServiceResult.ok(updated)
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to update membership: {str(e)}",
            error_type="internal_error"
        )
