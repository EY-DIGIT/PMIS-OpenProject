"""
Work Package update service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....domain.work_packages.work_package import WorkPackage
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string


def update_work_package(
    db: Session,
    work_package_id: int,
    subject: Optional[str] = None,
    description: Optional[str] = None,
    assignee_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    done_ratio: Optional[int] = None,
) -> ServiceResult[WorkPackage]:
    """
    Update a work package.

    Args:
        db: Database session
        work_package_id: Work package ID
        subject: New subject
        description: New description
        assignee_id: New assignee ID
        status: New status
        priority: New priority
        done_ratio: New completion percentage

    Returns:
        ServiceResult with updated work package or error
    """
    repository = WorkPackageRepository(db)

    # Get current work package
    wp = repository.get_by_id(work_package_id)
    if not wp:
        return ServiceResult.fail(
            error=f"Work package with ID {work_package_id} does not exist",
            error_type="not_found"
        )

    # Validate subject if provided
    if subject is not None:
        subject = normalize_string(subject)
        if not subject or len(subject) > 255:
            return ServiceResult.fail(
                error="Invalid subject. Must be 1-255 characters.",
                error_type="validation_error"
            )

    # Validate description if provided
    if description is not None and len(description) > 5000:
        return ServiceResult.fail(
            error="Description too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    # Validate done_ratio if provided
    if done_ratio is not None:
        if not isinstance(done_ratio, int) or done_ratio < 0 or done_ratio > 100:
            return ServiceResult.fail(
                error="Done ratio must be between 0 and 100.",
                error_type="validation_error"
            )

    # Validate status if provided
    if status is not None:
        valid_statuses = ["new", "in_progress", "resolved", "closed", "on_hold"]
        if status not in valid_statuses:
            return ServiceResult.fail(
                error=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                error_type="validation_error"
            )

    # Validate priority if provided
    if priority is not None:
        valid_priorities = ["low", "normal", "high", "urgent"]
        if priority not in valid_priorities:
            return ServiceResult.fail(
                error=f"Invalid priority. Must be one of: {', '.join(valid_priorities)}",
                error_type="validation_error"
            )

    # Validate assignee if provided
    if assignee_id is not None:
        # Verify assignee is a project member (this validates user exists + is member)
        member_repo = ProjectMemberRepository(db)
        if not member_repo.is_member(wp.project_id, assignee_id):
            return ServiceResult.fail(
                error="Assignee must be a member of the project",
                error_type="validation_error"
            )

    # Update work package
    try:
        updated_wp = repository.update(
            work_package_id=work_package_id,
            subject=subject,
            description=description,
            assignee_id=assignee_id,
            status=status,
            priority=priority,
            done_ratio=done_ratio,
        )
        return ServiceResult.ok(updated_wp)
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to update work package: {str(e)}",
            error_type="database_error"
        )
