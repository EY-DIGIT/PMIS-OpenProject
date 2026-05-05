"""
Shared write-lock helpers for milestones / activities / tasks / subtasks.

Every write path in those modules calls one of these guards before mutating
anything, so the rule for "can this project accept this kind of write right
now?" lives in one place.

Doc 33 simplification
---------------------
The old baseline/version distinction is gone. There is only ONE project
per id, and it owns its milestones, activities, tasks, and subtasks
directly. The three guards below now collapse to a single check —
"project exists and is not soft-deleted" — kept as separate functions
so call sites stay self-documenting and so a future per-level rule
(e.g. "tasks not editable while project is closed") can be added in
one place.

Functions
---------
- ``assert_project_editable`` — project exists and is not soft-deleted.
- ``assert_milestone_activity_writable`` — same, kept distinct so the
  M/A code paths read clearly.
- ``assert_task_subtask_writable`` — same, kept distinct so the T/S
  code paths read clearly.
"""
from sqlalchemy.orm import Session

from ..infrastructure.db.models.project import ProjectModel
from .errors import NotFoundError


def _load_live_project(db: Session, project_id: str) -> ProjectModel:
    """Fetch a project and raise NotFoundError if missing or soft-deleted."""
    project = (
        db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    )
    if project is None:
        raise NotFoundError("The project could not be found.")
    if getattr(project, "deleted_at", None) is not None:
        raise NotFoundError(
            "The project has been deleted and cannot be edited."
        )
    return project


def assert_project_editable(db: Session, project_id: str) -> None:
    """Project exists and is not soft-deleted."""
    _load_live_project(db, project_id)


def assert_milestone_activity_writable(db: Session, project_id: str) -> None:
    """Project accepts milestone / activity writes (doc 33: same as
    ``assert_project_editable`` since the baseline/version split was
    removed)."""
    _load_live_project(db, project_id)


def assert_task_subtask_writable(db: Session, project_id: str) -> None:
    """Project accepts task / subtask writes (doc 33: same as
    ``assert_project_editable`` since T/S no longer require a version)."""
    _load_live_project(db, project_id)
