"""
Shared write-lock helper for milestones / activities / tasks / subtasks.

Every write path in those modules calls assert_project_editable() before
mutating anything, so the rule for "can this project be edited right now?"
lives in one place.

Rule:
    A project is LOCKED for writes when
      - it has been soft-deleted (deleted_at is not None), OR
      - it is a PUBLISHED baseline (status == 'published' AND is_version is
        False). Versions of published projects remain editable.

Missing columns (before projects-side work adds `is_version` or
`deleted_at`) are tolerated via getattr with safe defaults.
"""
from sqlalchemy.orm import Session

from ..infrastructure.db.models.project import ProjectModel
from .errors import AuthorizationError, NotFoundError


def assert_project_editable(db: Session, project_id: int) -> None:
    """
    Raise if the project cannot accept writes.

    Raises:
        NotFoundError: project does not exist, or has been soft-deleted.
        AuthorizationError: project is a published baseline.
    """
    project = (
        db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    )
    if project is None:
        raise NotFoundError("The project could not be found.")

    deleted_at = getattr(project, "deleted_at", None)
    if deleted_at is not None:
        raise NotFoundError(
            "The project has been deleted and cannot be edited."
        )

    status = getattr(project, "status", None)
    is_version = getattr(project, "is_version", False)
    if status == "published" and not is_version:
        raise AuthorizationError(
            "This project is published and cannot be edited. "
            "Please create a new version to make changes."
        )
