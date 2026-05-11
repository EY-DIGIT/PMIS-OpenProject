"""
Project audit recording.

Callers invoke ``record_audit`` inside the transaction that made the change.
The audit row is flushed (so it's visible to later queries in the same tx)
but not committed — the caller owns the transaction boundary.
"""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .....domain.projects.project import Project
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.models.user import UserModel
from .....infrastructure.db.repositories.project_audit_log_repository import (
    ProjectAuditLogRepository,
)


# Well-known action names. Callers should use these rather than raw strings
# so downstream log viewers stay consistent.
#
# Doc 33: with versioning removed, ACTION_SUSPEND and ACTION_VERSION_CREATE
# are gone. Audit coverage was expanded to include the M/A/T/S subtree
# writes plus dependency, status, vendor-association and member-association
# changes — every state change to a project is captured here regardless of
# which subtree handler made it.
ACTION_CREATE = "project.create"
ACTION_UPDATE = "project.update"
ACTION_PUBLISH = "project.publish"
ACTION_CLOSE = "project.close"
ACTION_SOFT_DELETE = "project.soft_delete"
ACTION_DRAFT = "project.draft"
ACTION_STATUS_CHANGE = "project.status_change"

# Subtree write actions (doc 33 audit expansion).
ACTION_MILESTONE_CREATE = "milestone.create"
ACTION_MILESTONE_UPDATE = "milestone.update"
ACTION_MILESTONE_DELETE = "milestone.soft_delete"
ACTION_MILESTONE_DEP_CHANGE = "milestone.dep_change"
ACTION_ACTIVITY_CREATE = "activity.create"
ACTION_ACTIVITY_UPDATE = "activity.update"
ACTION_ACTIVITY_DELETE = "activity.soft_delete"
ACTION_ACTIVITY_DEP_CHANGE = "activity.dep_change"
ACTION_TASK_CREATE = "task.create"
ACTION_TASK_UPDATE = "task.update"
ACTION_TASK_DELETE = "task.soft_delete"
ACTION_TASK_DEP_CHANGE = "task.dep_change"
ACTION_SUBTASK_CREATE = "subtask.create"
ACTION_SUBTASK_UPDATE = "subtask.update"
ACTION_SUBTASK_DELETE = "subtask.soft_delete"
ACTION_SUBTASK_DEP_CHANGE = "subtask.dep_change"

# Project-association actions (doc 33 audit expansion).
ACTION_VENDOR_ASSOC_ADD = "project.vendor.assoc_add"
ACTION_VENDOR_ASSOC_REMOVE = "project.vendor.assoc_remove"
ACTION_MEMBER_ADD = "project.member.add"
ACTION_MEMBER_UPDATE = "project.member.update"
ACTION_MEMBER_REMOVE = "project.member.remove"


def project_snapshot(project: Project) -> Dict[str, Any]:
    """Project fields captured for the audit ``before`` / ``after`` payload."""
    return {
        "status": project.status,
        "name": project.name,
        "description": project.description,
        "owner": project.owner,
        "public": project.public,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
        "actual_start_date": (
            project.actual_start_date.isoformat() if project.actual_start_date else None
        ),
        "actual_end_date": (
            project.actual_end_date.isoformat() if project.actual_end_date else None
        ),
        "category": project.category,
    }


def _resolve_actor_login(db: Session, actor_id: Optional[str]) -> str:
    """Look up the user's login or fall back to 'system' for unauth actions."""
    if not actor_id:
        return "system"
    row = (
        db.query(UserModel.login)
        .filter(UserModel.id == actor_id)
        .first()
    )
    return row[0] if row else "system"


def _resolve_project_snapshot_fields(
    db: Session, project_id: str
) -> Dict[str, str]:
    """Snapshot name / status / owner from the project row at write time.

    These get persisted on the audit row so the log stays meaningful
    even if the project is later renamed, closed, or has its owner
    flipped. Returns '(unknown)' for missing values so the NOT NULL
    columns are always populated.
    """
    row = (
        db.query(
            ProjectModel.name,
            ProjectModel.status,
            ProjectModel.owner,
        )
        .filter(ProjectModel.id == project_id)
        .first()
    )
    if row is None:
        return {
            "project_name": "(unknown)",
            "project_status": "(unknown)",
            "owner": "(unknown)",
        }
    return {
        "project_name": row[0] or "(unknown)",
        "project_status": row[1] or "(unknown)",
        "owner": row[2] or "(unknown)",
    }


def record_audit(
    db: Session,
    project_id: str,
    actor_id: Optional[str],
    action: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    actor_role: Optional[str] = None,
) -> None:
    """Persist one audit log row.

    Doc 47: in addition to the original (project_id, actor_id, action,
    before, after) tuple, the row now carries denormalized snapshots
    of the project's name/status/owner and the actor's login —
    captured at write time so the log row stays correct even if those
    source rows mutate afterwards. All four are NOT NULL on the table;
    we resolve them here so call sites don't have to know.
    """
    proj_fields = _resolve_project_snapshot_fields(db, project_id)
    ProjectAuditLogRepository(db).add(
        project_id=project_id,
        actor_id=actor_id,
        action=action,
        before=before,
        after=after,
        actor_role=actor_role or "system",
        actor_login=_resolve_actor_login(db, actor_id),
        project_name=proj_fields["project_name"],
        project_status=proj_fields["project_status"],
        owner=proj_fields["owner"],
    )
