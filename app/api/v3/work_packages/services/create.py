"""
Work Package creation service.

Enforces the project hierarchy:
  - Depth 0 (no parent): must be type "milestone", requires start_date & end_date
  - Depth 1 (parent is milestone): must be type "activity", requires start_date & end_date
  - Depth 2+ (parent is activity or task): must be type "task"
"""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from .....core.errors import ValidationError
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....infrastructure.db.repositories.work_package_type_repository import WorkPackageTypeRepository
from .....domain.work_packages.work_package import WorkPackage
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string

# Hierarchy rules: depth -> required type internal_name
_DEPTH_TYPE_MAP = {
    0: "milestone",
    1: "activity",
    # 2+ -> "task"
}

# Types that require date ranges
_DATE_REQUIRED_TYPES = {"milestone", "activity"}


def create_work_package(
    db: Session,
    project_id: str,
    subject: str,
    description: Optional[str] = None,
    parent_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    status: str = "new",
    priority: str = "normal",
    done_ratio: int = 0,
    type_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> ServiceResult[WorkPackage]:
    """
    Create a new work package with hierarchy enforcement.

    Hierarchy rules:
      - No parent -> must be Milestone (with date range)
      - Parent is Milestone -> must be Activity (with date range)
      - Parent is Activity or Task -> must be Task (dates optional)
      - Child dates must fall within parent date range (if parent has dates)
    """
    # --- basic field validation ---
    subject = normalize_string(subject)
    if not subject or len(subject) > 255:
        return ServiceResult.fail(
            error="Invalid subject. Must be 1-255 characters.",
            error_type="validation_error"
        )

    if description and len(description) > 5000:
        return ServiceResult.fail(
            error="Description too long. Maximum 5000 characters.",
            error_type="validation_error"
        )

    if not isinstance(done_ratio, int) or done_ratio < 0 or done_ratio > 100:
        return ServiceResult.fail(
            error="Done ratio must be between 0 and 100.",
            error_type="validation_error"
        )

    valid_statuses = ["new", "in_progress", "resolved", "closed", "on_hold"]
    if status not in valid_statuses:
        return ServiceResult.fail(
            error=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            error_type="validation_error"
        )

    valid_priorities = ["low", "normal", "high", "urgent"]
    if priority not in valid_priorities:
        return ServiceResult.fail(
            error=f"Invalid priority. Must be one of: {', '.join(valid_priorities)}",
            error_type="validation_error"
        )

    repository = WorkPackageRepository(db)
    project_repo = ProjectRepository(db)
    member_repo = ProjectMemberRepository(db)

    # --- project exists ---
    if not project_repo.exists_by_id(project_id):
        return ServiceResult.fail(
            error=f"Project with ID {project_id} does not exist",
            error_type="not_found"
        )

    # --- resolve parent & compute depth ---
    depth = 0
    parent = None
    parent_type_name = None
    if parent_id is not None:
        parent = repository.get_by_id(parent_id)
        if not parent:
            return ServiceResult.fail(
                error=f"Parent work package with ID {parent_id} does not exist",
                error_type="not_found"
            )
        if parent.project_id != project_id:
            return ServiceResult.fail(
                error="Parent work package must belong to the same project",
                error_type="validation_error"
            )
        # walk ancestor chain to determine depth
        ancestors = repository.get_ancestor_chain(parent_id)
        depth = len(ancestors) + 1  # ancestors doesn't include parent itself
        parent_type_name = repository.get_type_internal_name(parent.type_id) if parent.type_id else None

    # --- resolve required type for this depth ---
    required_type_name = _DEPTH_TYPE_MAP.get(depth, "task")

    # --- validate / auto-resolve type_id ---
    type_repo = WorkPackageTypeRepository(db)
    if type_id is not None:
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
        # enforce hierarchy type
        actual_internal = getattr(type_model, "internal_name", None)
        if actual_internal != required_type_name:
            return ServiceResult.fail(
                error=(
                    f"At depth {depth}, type must be '{required_type_name}' "
                    f"but got '{actual_internal}'. "
                    f"Hierarchy: project -> milestone -> activity -> task (unlimited nesting)."
                ),
                error_type="validation_error"
            )
    else:
        # auto-resolve type from depth
        resolved_id = repository.get_type_id_by_internal_name(required_type_name)
        if resolved_id is None:
            return ServiceResult.fail(
                error=f"Built-in type '{required_type_name}' not found. Run database init.",
                error_type="validation_error"
            )
        type_id = resolved_id

    # --- date validation ---
    if required_type_name in _DATE_REQUIRED_TYPES:
        if start_date is None or end_date is None:
            return ServiceResult.fail(
                error=f"start_date and end_date are required for type '{required_type_name}'.",
                error_type="validation_error"
            )

    if start_date is not None and end_date is not None:
        # Inclusive: end_date == start_date is allowed.
        if end_date < start_date:
            return ServiceResult.fail(
                error="end_date cannot be before start_date.",
                error_type="validation_error"
            )

    # date containment: child dates must fall within parent dates
    if parent is not None and parent.start_date and parent.end_date:
        # Normalize to naive UTC for comparison (DB stores naive, JSON may send aware)
        def _naive(dt):
            if dt is None:
                return None
            return dt.replace(tzinfo=None) if dt.tzinfo else dt

        p_start = _naive(parent.start_date)
        p_end = _naive(parent.end_date)
        c_start = _naive(start_date)
        c_end = _naive(end_date)

        if c_start is not None and c_start < p_start:
            return ServiceResult.fail(
                error=f"start_date cannot be before parent's start_date ({parent.start_date.isoformat()}).",
                error_type="validation_error"
            )
        if c_end is not None and c_end > p_end:
            return ServiceResult.fail(
                error=f"end_date cannot be after parent's end_date ({parent.end_date.isoformat()}).",
                error_type="validation_error"
            )

    # --- assignee validation ---
    if assignee_id is not None:
        if not member_repo.is_member(project_id, assignee_id):
            return ServiceResult.fail(
                error="Assignee must be a member of the project",
                error_type="validation_error"
            )

    # --- create ---
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
            type_id=type_id,
            start_date=start_date,
            end_date=end_date,
        )
        return ServiceResult.ok(wp)
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to create work package: {str(e)}",
            error_type="database_error"
        )
