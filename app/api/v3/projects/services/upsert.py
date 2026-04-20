"""
Project upsert service.

Idempotent create-or-update by identifier. Used by the project creation
wizard so that re-submitting Step 1 (e.g. after clicking Back) updates the
same row instead of creating duplicates.
"""
from typing import Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string


def _verify_user_exists(db: Session, username: str) -> bool:
    return UserRepository(db).get_by_login(username) is not None


def upsert_project(
    db: Session,
    identifier: str,
    name: str,
    current_user_login: Optional[str],
    is_admin: bool,
    description: Optional[str] = None,
    active: bool = True,
    public: bool = False,
    status_explanation: Optional[str] = None,
    parent_id: Optional[int] = None,
    status: str = "new",
    owner: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> ServiceResult[Tuple[Project, bool]]:
    """
    Create or update a project by its identifier.

    Ownership rule: if a row with this identifier already exists, the update
    is only permitted when the caller is the project's owner OR is an admin.
    This prevents an attacker who guesses an identifier from overwriting
    another user's project.

    Returns ServiceResult with (project, created) where created=True for a
    fresh insert, False for an update of an existing row.
    """
    identifier = normalize_string(identifier).lower()
    name = normalize_string(name)

    if not identifier or len(identifier) > 255:
        return ServiceResult.fail(
            error="Invalid identifier. Must be 1-255 characters.",
            error_type="validation_error",
        )
    if not all(c.isalnum() or c in "-_" for c in identifier):
        return ServiceResult.fail(
            error="Invalid identifier format. Only alphanumeric, hyphens, and underscores allowed.",
            error_type="validation_error",
        )
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
    if start_date is not None and end_date is not None and end_date <= start_date:
        return ServiceResult.fail(
            error="end_date must be after start_date",
            error_type="validation_error",
        )
    if owner is not None and not _verify_user_exists(db, owner):
        return ServiceResult.fail(
            error=f"Owner user with username '{owner}' does not exist.",
            error_type="validation_error",
        )

    repository = ProjectRepository(db)

    # Ownership gate on the update path.
    existing = repository.get_by_identifier(identifier)
    if existing is not None and not is_admin:
        if existing.owner is None or existing.owner != current_user_login:
            return ServiceResult.fail(
                error=(
                    f"Project with identifier '{identifier}' exists and is owned "
                    "by another user. You cannot modify it."
                ),
                error_type="forbidden",
            )

    if parent_id is not None and not repository.exists_by_id(parent_id):
        return ServiceResult.fail(
            error=f"Parent project with ID {parent_id} does not exist",
            error_type="not_found",
        )

    try:
        project, created = repository.upsert_by_identifier(
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
        )
        return ServiceResult.ok((project, created))
    except Exception as e:
        return ServiceResult.fail(
            error=f"Failed to upsert project: {str(e)}",
            error_type="internal_error",
        )
