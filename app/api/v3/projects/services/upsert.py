"""
Project upsert service.

Idempotent create-or-update by **id** (which is itself a UUID). Used by the
project creation wizard so that re-submitting Step 1 (e.g. after clicking
Back) updates the same row instead of creating duplicates.

Frontend generates a fresh UUID at wizard start (e.g. ``crypto.randomUUID()``)
and sends ``PUT /api/v3/projects/{uuid}`` on every Save & Next click. First
call -> INSERT with that id. Later calls -> UPDATE.
"""
from typing import Optional, Tuple
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....domain.projects.project import Project
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string


def _verify_user_exists(db: Session, username: str) -> bool:
    return UserRepository(db).get_by_login(username) is not None


def _looks_like_uuid(s: str) -> bool:
    try:
        UUID(s)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def upsert_project(
    db: Session,
    id: str,
    name: str,
    current_user_login: Optional[str],
    is_admin: bool,
    description: Optional[str] = None,
    active: bool = True,
    public: bool = False,
    status_explanation: Optional[str] = None,
    parent_id: Optional[str] = None,
    status: str = "new",
    owner: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> ServiceResult[Tuple[Project, bool]]:
    """Create or update a project by its id (UUID string)."""
    if not _looks_like_uuid(id):
        return ServiceResult.fail(
            error="Invalid UUID format in URL.",
            error_type="validation_error",
        )

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
    existing = repository.get_by_id(id)
    if existing is not None and not is_admin:
        if existing.owner is None or existing.owner != current_user_login:
            return ServiceResult.fail(
                error=(
                    "This project already exists and is owned by another user. "
                    "You cannot modify it."
                ),
                error_type="forbidden",
            )

    if parent_id is not None and not repository.exists_by_id(parent_id):
        return ServiceResult.fail(
            error=f"Parent project with ID {parent_id} does not exist",
            error_type="not_found",
        )

    try:
        project, created = repository.upsert_by_id(
            id=id,
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
