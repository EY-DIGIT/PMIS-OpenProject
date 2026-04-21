"""
Project soft-delete service.
"""
from typing import Optional

from sqlalchemy.orm import Session

from .....api.v3.milestones.services.cascade import cascade_soft_delete_project
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....shared.service_result import ServiceResult

from .audit import ACTION_SOFT_DELETE, project_snapshot, record_audit


def delete_project(
    db: Session,
    project_id: int,
    *,
    actor_id: Optional[int],
) -> ServiceResult[None]:
    """
    Soft-delete a project: stamp ``deleted_at`` / ``deleted_by`` and cascade
    the delete through the M/A/T/S subtree. One transaction — no partial state.

    Per decision: admin-only permission is the gate; we do NOT call
    ``assert_project_editable`` — deletion is available even on published
    baselines.
    """
    repo = ProjectRepository(db)
    project = repo.get_by_id(project_id)
    if project is None:
        return ServiceResult.fail(
            error=f"Project with ID {project_id} not found",
            error_type="not_found",
        )

    before = project_snapshot(project)

    try:
        repo.soft_delete(project_id, actor_id=actor_id)

        # Cascade into the M/A/T/S subtree (stub until upstream lands).
        cascade_soft_delete_project(db, project_id, actor_id)

        record_audit(
            db,
            project_id=project_id,
            actor_id=actor_id,
            action=ACTION_SOFT_DELETE,
            before=before,
            after=None,
        )

        db.commit()
        return ServiceResult.ok(None)

    except Exception as e:
        db.rollback()
        return ServiceResult.fail(
            error=f"Failed to delete project: {str(e)}",
            error_type="internal_error",
        )
