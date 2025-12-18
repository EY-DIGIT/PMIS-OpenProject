"""
Work Package creation service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....core.errors import ValidationError
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....domain.work_packages.work_package import WorkPackage
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string


def create_work_package(
    db: Session,
    project_id: int,
    subject: str,
    description: Optional[str] = None,
    parent_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    status: str = "new",
    priority: str = "normal",
    done_ratio: int = 0,
) -> ServiceResult[WorkPackage]:
    """
    Create a new work package.

    Args:
        db: Database session
        project_id: Project ID
        subject: Work package subject
        description: Work package description
        parent_id: Parent work package ID (for subtasks)
        assignee_id: Assigned user ID
        status: Work package status
        priority: Work package priority
        done_ratio: Completion percentage (0-100)

    Returns:
        ServiceResult with created work package or error
    """
    # Normalize and validate subject
    subject = normalize_string(subject)
    if not subject or len(subject) > 255:
        return ServiceResult.fail(
            error="Invalid subject. Must be 1-255 characters.",
            error_type="validation_error"
        )

    # Validate description length
    if description and len(description) > 5000:
        return ServiceResult.fail(
            error="Description too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    # Validate done_ratio
    if not isinstance(done_ratio, int) or done_ratio < 0 or done_ratio > 100:
        return ServiceResult.fail(
            error="Done ratio must be between 0 and 100.",
            error_type="validation_error"
        )

    # Validate status
    valid_statuses = ["new", "in_progress", "resolved", "closed", "on_hold"]
    if status not in valid_statuses:
        return ServiceResult.fail(
            error=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            error_type="validation_error"
        )

    # Validate priority
    valid_priorities = ["low", "normal", "high", "urgent"]
    if priority not in valid_priorities:
        return ServiceResult.fail(
            error=f"Invalid priority. Must be one of: {', '.join(valid_priorities)}",
            error_type="validation_error"
        )

    repository = WorkPackageRepository(db)
    project_repo = ProjectRepository(db)
    member_repo = ProjectMemberRepository(db)

    # Validate project exists
    if not project_repo.exists_by_id(project_id):
        return ServiceResult.fail(
            error=f"Project with ID {project_id} does not exist",
            error_type="not_found"
        )

    # Validate parent work package if specified
    if parent_id is not None:
        parent = repository.get_by_id(parent_id)
        if not parent:
            return ServiceResult.fail(
                error=f"Parent work package with ID {parent_id} does not exist",
                error_type="not_found"
            )

        # Verify parent belongs to same project
        if parent.project_id != project_id:
            return ServiceResult.fail(
                error="Parent work package must belong to the same project",
                error_type="validation_error"
            )

    # Validate assignee if specified
    if assignee_id is not None:
        # Verify assignee is a project member (this validates user exists + is member)
        if not member_repo.is_member(project_id, assignee_id):
            return ServiceResult.fail(
                error="Assignee must be a member of the project",
                error_type="validation_error"
            )

    # Create work package
    try:
        wp = repository.create(
            subject=subject,
            project_id=project_id,
            description=description,
            parent_id=parent_id,
            assignee_id=assignee_id,
            status=status,
            priority=priority,
            done_ratio=done_ratio,
        )
        return ServiceResult.ok(wp)
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to create work package: {str(e)}",
            error_type="database_error"
        )
