"""
Work Package update service.

Validates date changes against parent containment rules.
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....infrastructure.db.repositories.work_package_type_repository import WorkPackageTypeRepository
from .....domain.work_packages.work_package import WorkPackage
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string

# Sentinel to distinguish "not provided" from explicit None
_UNSET = object()


def update_work_package(
    db: Session,
    work_package_id: int,
    subject: Optional[str] = None,
    description: Optional[str] = None,
    assignee_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    done_ratio: Optional[int] = None,
    type_id: Optional[int] = None,
    start_date: Optional[datetime] = _UNSET,
    end_date: Optional[datetime] = _UNSET,
) -> ServiceResult[WorkPackage]:
    """
    Update a work package.

    Date containment: if the work package has a parent with dates,
    updated dates must still fall within the parent's range.
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
        member_repo = ProjectMemberRepository(db)
        if not member_repo.is_member(wp.project_id, assignee_id):
            return ServiceResult.fail(
                error="Assignee must be a member of the project",
                error_type="validation_error"
            )

    # Validate type if provided (do NOT allow changing to a type that
    # breaks the hierarchy — but we allow it for now since reparenting
    # isn't supported in update)
    if type_id is not None:
        type_repo = WorkPackageTypeRepository(db)
        type_model = type_repo.get_by_id(type_id)
        if not type_model:
            return ServiceResult.fail(
                error=f"Work package type with ID {type_id} does not exist",
                error_type="not_found"
            )
        if not getattr(type_model, "is_active", False):
            return ServiceResult.fail(
                error=f"Work package type with ID {type_id} is not active",
                error_type="validation_error"
            )

    # --- date validation ---
    effective_start = start_date if start_date is not _UNSET else wp.start_date
    effective_end = end_date if end_date is not _UNSET else wp.end_date

    if effective_start is not None and effective_end is not None:
        # Inclusive: end_date == start_date is allowed.
        if effective_end < effective_start:
            return ServiceResult.fail(
                error="end_date cannot be before start_date.",
                error_type="validation_error"
            )

    # date containment against parent
    if wp.parent_id is not None:
        parent = repository.get_by_id(wp.parent_id)
        if parent and parent.start_date and parent.end_date:
            def _naive(dt):
                if dt is None:
                    return None
                return dt.replace(tzinfo=None) if dt.tzinfo else dt

            p_start = _naive(parent.start_date)
            p_end = _naive(parent.end_date)
            e_start = _naive(effective_start)
            e_end = _naive(effective_end)

            if e_start is not None and e_start < p_start:
                return ServiceResult.fail(
                    error=f"start_date cannot be before parent's start_date ({parent.start_date.isoformat()}).",
                    error_type="validation_error"
                )
            if e_end is not None and e_end > p_end:
                return ServiceResult.fail(
                    error=f"end_date cannot be after parent's end_date ({parent.end_date.isoformat()}).",
                    error_type="validation_error"
                )

    # Build update kwargs — only pass dates if they were explicitly provided
    repo_kwargs = dict(
        work_package_id=work_package_id,
        subject=subject,
        description=description,
        assignee_id=assignee_id,
        status=status,
        priority=priority,
        done_ratio=done_ratio,
        type_id=type_id,
    )
    if start_date is not _UNSET:
        repo_kwargs["start_date"] = start_date
    if end_date is not _UNSET:
        repo_kwargs["end_date"] = end_date

    # Update work package
    try:
        updated_wp = repository.update(**repo_kwargs)
        return ServiceResult.ok(updated_wp)
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to update work package: {str(e)}",
            error_type="database_error"
        )
