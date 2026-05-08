"""
Project list service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, union
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.project_member import ProjectMemberModel
from .....infrastructure.db.models.project_vendor import ProjectVendorModel
from .....infrastructure.db.models.user_role_assignment import (
    UserRoleAssignmentModel,
)
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.rbac_repository import RbacRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult
from .....shared.pagination import PaginatedResult, calculate_offset


def list_projects(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    active: Optional[bool] = None,
    public: Optional[bool] = None,
    include_deleted: bool = False,
    caller_id: Optional[str] = None,
) -> ServiceResult[PaginatedResult[Project]]:
    """
    List projects with pagination and optional filtering.

    ``include_deleted=False`` (default) returns only live rows — backs the
    Search Project view. ``include_deleted=True`` returns every row including
    soft-deleted ones — backs the admin "all projects" audit view.

    Doc 44 round 4 — caller-scoped filter:
      * When ``caller_id`` is None (legacy callers / scripts) the listing
        returns all projects, same as before.
      * When ``caller_id`` is supplied AND the caller holds the legacy
        ``admin`` flag (which covers both ``admin`` and ``super_admin``
        per :func:`RbacRepository.user_has_admin_role`), the listing
        returns all projects too — full access for top-tier roles.
      * Otherwise the listing is filtered to projects the caller is
        explicitly associated with, via the union of three sources:

          1. ``project_members`` rows for the caller (legacy + doc-21
             membership table; populated on user create).
          2. Project-scoped ``user_role_assignments`` rows (doc-41
             ``project_admin`` / ``project_member`` / ``division_member``).
          3. Org-scoped ``user_role_assignments`` rows JOIN
             ``project_vendors`` (doc-41 ``org_admin`` sees every project
             owned by their vendor).
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
        if not include_deleted:
            query = query.filter(ProjectModel.deleted_at.is_(None))

        if active is not None:
            query = query.filter(ProjectModel.active == active)
        if public is not None:
            query = query.filter(ProjectModel.public == public)

        # Doc 44 round 4 — caller-scoped filtering. Skip when no caller
        # id was passed (legacy code path) OR when the caller holds the
        # admin / super_admin global tier (full access).
        if caller_id is not None and not RbacRepository(db).user_has_admin_role(caller_id):
            visible_pids = (
                db.query(ProjectMemberModel.project_id)
                .filter(ProjectMemberModel.user_id == caller_id)
                .union(
                    db.query(UserRoleAssignmentModel.project_id)
                    .filter(
                        UserRoleAssignmentModel.user_id == caller_id,
                        UserRoleAssignmentModel.project_id.isnot(None),
                    )
                )
                .union(
                    db.query(ProjectVendorModel.project_id)
                    .join(
                        UserRoleAssignmentModel,
                        UserRoleAssignmentModel.organization_id
                        == ProjectVendorModel.vendor_id,
                    )
                    .filter(
                        UserRoleAssignmentModel.user_id == caller_id,
                        UserRoleAssignmentModel.organization_id.isnot(None),
                    )
                )
            )
            query = query.filter(ProjectModel.id.in_(visible_pids))

        # Get total count
        total = query.count()

        # Newest-first ordering. The Search Project table reads top-down, so
        # the most recently created project should land at row 0. Tie-break on
        # id to keep pagination stable when two rows share a created_at
        # timestamp (possible on bulk seeds).
        query = query.order_by(
            ProjectModel.created_at.desc(),
            ProjectModel.id.desc(),
        )

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
