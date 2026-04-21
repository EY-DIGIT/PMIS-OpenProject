"""
Project creation service.
"""
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .....domain.projects.project import Project
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string

from .audit import ACTION_CREATE, project_snapshot, record_audit
from .transitions import (
    PROJECT_CATEGORY_CHOICES,
    PROJECT_STATUS_CHOICES,
    STATUS_NEW,
)


def _verify_user_exists(db: Session, username: str) -> bool:
    return UserRepository(db).get_by_login(username) is not None


def create_project(
    db: Session,
    *,
    actor_id: Optional[int],
    identifier: Optional[str] = None,
    name: str,
    description: Optional[str] = None,
    active: bool = True,
    public: bool = False,
    status_explanation: Optional[str] = None,
    parent_id: Optional[int] = None,
    status: str = STATUS_NEW,
    owner: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> ServiceResult[Project]:
    """Create a new (non-version) project.

    If ``identifier`` is omitted, the server allocates the next ``prj{n:03d}``.
    Commits the transaction on success.
    """
    name = normalize_string(name)
    if not name or len(name) > 255:
        return ServiceResult.fail(
            error="Invalid name. Must be 1-255 characters.",
            error_type="validation_error",
        )

    if description and len(description) > 5000:
        return ServiceResult.fail(
            error="Description too long. Maximum 5000 characters.",
            error_type="validation_error",
        )

    if status_explanation and len(status_explanation) > 5000:
        return ServiceResult.fail(
            error="Status explanation too long. Maximum 5000 characters.",
            error_type="validation_error",
        )

    if status not in PROJECT_STATUS_CHOICES:
        return ServiceResult.fail(
            error=f"Invalid status '{status}'.",
            error_type="validation_error",
        )

    if category is not None and category not in PROJECT_CATEGORY_CHOICES:
        return ServiceResult.fail(
            error=f"Invalid category '{category}'.",
            error_type="validation_error",
        )

    if start_date is not None and start_date <= datetime.now(timezone.utc):
        return ServiceResult.fail(
            error="start_date must be in the future",
            error_type="validation_error",
        )
    if end_date is not None and end_date <= datetime.now(timezone.utc):
        return ServiceResult.fail(
            error="end_date must be in the future",
            error_type="validation_error",
        )
    if start_date is not None and end_date is not None and end_date <= start_date:
        return ServiceResult.fail(
            error="end_date must be after start_date",
            error_type="validation_error",
        )

    if owner is not None and not _verify_user_exists(db, owner):
        return ServiceResult.fail(
            error=f"Owner user '{owner}' does not exist",
            error_type="validation_error",
        )

    repo = ProjectRepository(db)

    # Resolve identifier
    if identifier is None or not identifier.strip():
        identifier = repo.generate_next_identifier()
    else:
        identifier = normalize_string(identifier).lower()
        if not identifier or len(identifier) > 255:
            return ServiceResult.fail(
                error="Invalid identifier. Must be 1-255 characters.",
                error_type="validation_error",
            )
        if not all(c.isalnum() or c in "-_" for c in identifier):
            return ServiceResult.fail(
                error="Invalid identifier format. Allowed: alphanumeric, '-', '_'.",
                error_type="validation_error",
            )
        if repo.exists_by_identifier(identifier):
            return ServiceResult.fail(
                error=f"Project with identifier '{identifier}' already exists",
                error_type="already_exists",
            )

    if parent_id is not None and not repo.exists_by_id(parent_id):
        return ServiceResult.fail(
            error=f"Parent project with ID {parent_id} does not exist",
            error_type="not_found",
        )

    try:
        project = repo.create(
            identifier=identifier,
            name=name,
            description=description,
            active=active,
            public=public,
            status_explanation=status_explanation,
            parent_id=parent_id,
            status=status,
            owner=owner,
            category=category,
            start_date=start_date,
            end_date=end_date,
            is_version=False,
            created_by=actor_id,
        )

        record_audit(
            db,
            project_id=project.id,
            actor_id=actor_id,
            action=ACTION_CREATE,
            before=None,
            after=project_snapshot(project),
        )

        db.commit()
        return ServiceResult.ok(project)

    except Exception as e:
        db.rollback()
        return ServiceResult.fail(
            error=f"Failed to create project: {str(e)}",
            error_type="internal_error",
        )
