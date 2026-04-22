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
    project_id: str,
    *,
    actor_id: Optional[int],
) -> ServiceResult[None]:
    """
    Soft-delete a project: stamp ``deleted_at`` / ``deleted_by`` and cascade
    the delete through the M/A/T/S subtree. One transaction — no partial state.

    When the target is a **baseline** (``is_version=False``), the delete also
    cascades to every live version row that references this baseline via
    ``version_of``. Each version's M/A/T/S subtree is cascaded in turn. A
    separate ``project.soft_delete`` audit row is written per deleted project
    so the history is traceable. If the target is itself a version, only that
    version (and its subtree) is deleted — sibling versions and the baseline
    stay live.

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

    try:
        # If the target is a baseline, discover its live versions BEFORE we
        # stamp anything (so the query sees them as deleted_at IS NULL).
        version_ids = []
        if not project.is_version:
            version_ids = repo.list_live_version_ids(project_id)

        # Snapshot + delete each version first, then the baseline. Ordering
        # isn't strictly required (everything is in one transaction) but it
        # reads more naturally in the audit log.
        for vid in version_ids:
            version = repo.get_by_id(vid)
            if version is None:
                # Race: row disappeared between the list query and here.
                # Defensive — skip.
                continue
            version_before = project_snapshot(version)
            repo.soft_delete(vid, actor_id=actor_id)
            cascade_soft_delete_project(db, vid, actor_id)
            record_audit(
                db,
                project_id=vid,
                actor_id=actor_id,
                action=ACTION_SOFT_DELETE,
                before={
                    **version_before,
                    # Tag: this row was deleted because its baseline was
                    # deleted, not because someone asked for this one.
                    "cascaded_from_baseline_id": project_id,
                },
                after=None,
            )

        # Now the target itself.
        before = project_snapshot(project)
        repo.soft_delete(project_id, actor_id=actor_id)
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
