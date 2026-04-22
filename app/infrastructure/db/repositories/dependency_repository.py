"""Dependency repository.

Centralizes all reads/writes against the three association tables:
- activity_dependencies (source_activity, target_activity)
- task_dependencies     (source_task, target_task)
- subtask_dependencies  (source_subtask, target_subtask)

Design choices
--------------
- All ``set_*`` writers use replace-list semantics: pass the full desired list
  of target ids; the repo deletes anything not in the list and inserts what's
  missing. None ≠ []; the SERVICE layer is responsible for distinguishing
  "field omitted" from "set to empty".
- All writes ``flush`` but do NOT commit. Caller owns the transaction.
- Validation that targets exist + belong to the same project lives in the
  service layer; this repo only stores edges. The single exception is the
  ``existing_target_*_ids`` helpers that filter caller-supplied id lists down
  to those that actually exist + are not soft-deleted + belong to the
  expected project — used by service validators.
- Cycle detection is a service concern; the repo exposes ``would_create_cycle_*``
  helpers as plain DFS over the existing edges.
- Cascade on target deletion: ``cascade_remove_*_targets`` wipes every row
  that points at the deleted entity. Source rows survive, just with shorter
  ``dependsOn`` lists.
"""
from collections import deque
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from ..models.activity import ActivityModel
from ..models.activity_dependency import ActivityDependencyModel
from ..models.subtask import SubtaskModel
from ..models.subtask_dependency import SubtaskDependencyModel
from ..models.task import TaskModel
from ..models.task_dependency import TaskDependencyModel


class DependencyRepository:
    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------
    # Activity dependencies
    # -------------------------------------------------------------------

    def list_activity_dependencies(self, source_activity_id: str) -> List[str]:
        """Return target activity ids this source depends on (sorted)."""
        rows = (
            self.db.query(ActivityDependencyModel.target_activity_id)
            .filter(ActivityDependencyModel.source_activity_id == source_activity_id)
            .all()
        )
        return sorted(r[0] for r in rows)

    def set_activity_dependencies(
        self,
        source_activity_id: str,
        project_id: str,
        target_ids: Sequence[str],
    ) -> None:
        """Replace the source's dependency target list. Does NOT commit."""
        targets = list(dict.fromkeys(target_ids))  # de-dup, preserve order

        existing = set(
            r[0]
            for r in self.db.query(ActivityDependencyModel.target_activity_id)
            .filter(ActivityDependencyModel.source_activity_id == source_activity_id)
            .all()
        )
        desired = set(targets)

        to_remove = existing - desired
        if to_remove:
            self.db.query(ActivityDependencyModel).filter(
                ActivityDependencyModel.source_activity_id == source_activity_id,
                ActivityDependencyModel.target_activity_id.in_(to_remove),
            ).delete(synchronize_session=False)

        to_add = desired - existing
        for tid in to_add:
            self.db.add(
                ActivityDependencyModel(
                    source_activity_id=source_activity_id,
                    target_activity_id=tid,
                    project_id=project_id,
                )
            )
        self.db.flush()

    def existing_target_activity_ids(
        self, project_id: str, ids: Iterable[str]
    ) -> Set[str]:
        """Subset of ``ids`` that exist as live activities in ``project_id``."""
        ids = list({i for i in ids if i})
        if not ids:
            return set()
        rows = (
            self.db.query(ActivityModel.id)
            .filter(ActivityModel.id.in_(ids))
            .filter(ActivityModel.project_id == project_id)
            .filter(ActivityModel.deleted_at.is_(None))
            .all()
        )
        return {r[0] for r in rows}

    def would_create_cycle_activity(
        self, source_activity_id: str, new_target_ids: Sequence[str],
    ) -> Optional[str]:
        """If adding any of ``new_target_ids`` as a dependency of ``source``
        would create a cycle, return the offending target id. Else None.

        DFS from each candidate target — if we reach the source via existing
        edges, that means source→target→...→source closes a cycle.
        """
        # Build adjacency map of EXISTING edges across the project's deps so
        # we don't scan per-candidate. Cheaper for graphs of any size.
        all_edges = (
            self.db.query(
                ActivityDependencyModel.source_activity_id,
                ActivityDependencyModel.target_activity_id,
            )
            .all()
        )
        adj: dict = {}
        for s, t in all_edges:
            adj.setdefault(s, set()).add(t)

        for cand in new_target_ids:
            if cand == source_activity_id:
                return cand  # self-edge is a 1-cycle
            # DFS from cand: if we reach source, cycle.
            stack = deque([cand])
            seen = {cand}
            while stack:
                node = stack.pop()
                if node == source_activity_id:
                    return cand
                for nxt in adj.get(node, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
        return None

    def cascade_remove_activity_targets(self, target_activity_id: str) -> None:
        """Drop every dep edge pointing at this activity. Does NOT commit."""
        self.db.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.target_activity_id == target_activity_id
        ).delete(synchronize_session=False)
        # Also purge any edges whose source is this activity (it's being
        # soft-deleted; its outgoing deps are meaningless now).
        self.db.query(ActivityDependencyModel).filter(
            ActivityDependencyModel.source_activity_id == target_activity_id
        ).delete(synchronize_session=False)
        self.db.flush()

    # -------------------------------------------------------------------
    # Task dependencies
    # -------------------------------------------------------------------

    def list_task_dependencies(self, source_task_id: str) -> List[str]:
        rows = (
            self.db.query(TaskDependencyModel.target_task_id)
            .filter(TaskDependencyModel.source_task_id == source_task_id)
            .all()
        )
        return sorted(r[0] for r in rows)

    def set_task_dependencies(
        self,
        source_task_id: str,
        project_id: str,
        target_ids: Sequence[str],
    ) -> None:
        targets = list(dict.fromkeys(target_ids))
        existing = set(
            r[0]
            for r in self.db.query(TaskDependencyModel.target_task_id)
            .filter(TaskDependencyModel.source_task_id == source_task_id)
            .all()
        )
        desired = set(targets)

        to_remove = existing - desired
        if to_remove:
            self.db.query(TaskDependencyModel).filter(
                TaskDependencyModel.source_task_id == source_task_id,
                TaskDependencyModel.target_task_id.in_(to_remove),
            ).delete(synchronize_session=False)

        to_add = desired - existing
        for tid in to_add:
            self.db.add(
                TaskDependencyModel(
                    source_task_id=source_task_id,
                    target_task_id=tid,
                    project_id=project_id,
                )
            )
        self.db.flush()

    def existing_target_tasks(
        self, project_id: str, ids: Iterable[str]
    ) -> List[Tuple[str, str]]:
        """Return [(task_id, activity_id), ...] for ids that exist as live
        tasks in ``project_id``. The activity_id lets the service check the
        hierarchy rule (parent activity must already depend on target's
        parent activity)."""
        ids = list({i for i in ids if i})
        if not ids:
            return []
        rows = (
            self.db.query(TaskModel.id, TaskModel.activity_id)
            .filter(TaskModel.id.in_(ids))
            .filter(TaskModel.project_id == project_id)
            .filter(TaskModel.deleted_at.is_(None))
            .all()
        )
        return [(r[0], r[1]) for r in rows]

    def activity_pair_is_dependent(
        self, source_activity_id: str, target_activity_id: str
    ) -> bool:
        """True iff there is an activity_dependencies row
        (source_activity → target_activity). Used to enforce the hierarchy
        rule for task dependencies.
        """
        if source_activity_id == target_activity_id:
            # Same activity — tasks under the same activity may always
            # reference each other without any activity-level edge.
            return True
        return (
            self.db.query(ActivityDependencyModel.source_activity_id)
            .filter(
                ActivityDependencyModel.source_activity_id == source_activity_id,
                ActivityDependencyModel.target_activity_id == target_activity_id,
            )
            .first()
            is not None
        )

    def would_create_cycle_task(
        self, source_task_id: str, new_target_ids: Sequence[str],
    ) -> Optional[str]:
        all_edges = (
            self.db.query(
                TaskDependencyModel.source_task_id,
                TaskDependencyModel.target_task_id,
            )
            .all()
        )
        adj: dict = {}
        for s, t in all_edges:
            adj.setdefault(s, set()).add(t)

        for cand in new_target_ids:
            if cand == source_task_id:
                return cand
            stack = deque([cand])
            seen = {cand}
            while stack:
                node = stack.pop()
                if node == source_task_id:
                    return cand
                for nxt in adj.get(node, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
        return None

    def cascade_remove_task_targets(self, target_task_id: str) -> None:
        self.db.query(TaskDependencyModel).filter(
            TaskDependencyModel.target_task_id == target_task_id
        ).delete(synchronize_session=False)
        self.db.query(TaskDependencyModel).filter(
            TaskDependencyModel.source_task_id == target_task_id
        ).delete(synchronize_session=False)
        self.db.flush()

    # -------------------------------------------------------------------
    # Subtask dependencies
    # -------------------------------------------------------------------

    def list_subtask_dependencies(self, source_subtask_id: str) -> List[str]:
        rows = (
            self.db.query(SubtaskDependencyModel.target_subtask_id)
            .filter(SubtaskDependencyModel.source_subtask_id == source_subtask_id)
            .all()
        )
        return sorted(r[0] for r in rows)

    def set_subtask_dependencies(
        self,
        source_subtask_id: str,
        project_id: str,
        target_ids: Sequence[str],
    ) -> None:
        targets = list(dict.fromkeys(target_ids))
        existing = set(
            r[0]
            for r in self.db.query(SubtaskDependencyModel.target_subtask_id)
            .filter(SubtaskDependencyModel.source_subtask_id == source_subtask_id)
            .all()
        )
        desired = set(targets)

        to_remove = existing - desired
        if to_remove:
            self.db.query(SubtaskDependencyModel).filter(
                SubtaskDependencyModel.source_subtask_id == source_subtask_id,
                SubtaskDependencyModel.target_subtask_id.in_(to_remove),
            ).delete(synchronize_session=False)

        to_add = desired - existing
        for tid in to_add:
            self.db.add(
                SubtaskDependencyModel(
                    source_subtask_id=source_subtask_id,
                    target_subtask_id=tid,
                    project_id=project_id,
                )
            )
        self.db.flush()

    def existing_target_subtasks(
        self, project_id: str, ids: Iterable[str]
    ) -> List[Tuple[str, str]]:
        """Return [(subtask_id, task_id), ...] for ids that exist as live
        subtasks in ``project_id``."""
        ids = list({i for i in ids if i})
        if not ids:
            return []
        rows = (
            self.db.query(SubtaskModel.id, SubtaskModel.task_id)
            .filter(SubtaskModel.id.in_(ids))
            .filter(SubtaskModel.project_id == project_id)
            .filter(SubtaskModel.deleted_at.is_(None))
            .all()
        )
        return [(r[0], r[1]) for r in rows]

    def task_pair_is_dependent(
        self, source_task_id: str, target_task_id: str
    ) -> bool:
        """True iff source_task → target_task already exists in
        task_dependencies. Same-task is always allowed (subtasks under the
        same task may reference each other freely)."""
        if source_task_id == target_task_id:
            return True
        return (
            self.db.query(TaskDependencyModel.source_task_id)
            .filter(
                TaskDependencyModel.source_task_id == source_task_id,
                TaskDependencyModel.target_task_id == target_task_id,
            )
            .first()
            is not None
        )

    def would_create_cycle_subtask(
        self, source_subtask_id: str, new_target_ids: Sequence[str],
    ) -> Optional[str]:
        all_edges = (
            self.db.query(
                SubtaskDependencyModel.source_subtask_id,
                SubtaskDependencyModel.target_subtask_id,
            )
            .all()
        )
        adj: dict = {}
        for s, t in all_edges:
            adj.setdefault(s, set()).add(t)

        for cand in new_target_ids:
            if cand == source_subtask_id:
                return cand
            stack = deque([cand])
            seen = {cand}
            while stack:
                node = stack.pop()
                if node == source_subtask_id:
                    return cand
                for nxt in adj.get(node, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
        return None

    def cascade_remove_subtask_targets(self, target_subtask_id: str) -> None:
        self.db.query(SubtaskDependencyModel).filter(
            SubtaskDependencyModel.target_subtask_id == target_subtask_id
        ).delete(synchronize_session=False)
        self.db.query(SubtaskDependencyModel).filter(
            SubtaskDependencyModel.source_subtask_id == target_subtask_id
        ).delete(synchronize_session=False)
        self.db.flush()

    # -------------------------------------------------------------------
    # Bulk cascade on activity / task soft-delete
    # -------------------------------------------------------------------

    def cascade_remove_for_deleted_activity_subtree(
        self,
        activity_id: str,
        task_ids: Sequence[str],
        subtask_ids: Sequence[str],
    ) -> None:
        """Wipe all dependency edges (incoming + outgoing) for an activity
        and every task / subtask in its cascaded subtree.

        Called from delete_activity AFTER the rows have been soft-deleted.
        Doing it post-soft-delete keeps the ordering simple — the cascade in
        the activity repo is what defines the subtree.
        """
        # Activity edges (incoming + outgoing).
        self.cascade_remove_activity_targets(activity_id)

        # Task edges.
        if task_ids:
            tids = list(task_ids)
            self.db.query(TaskDependencyModel).filter(
                TaskDependencyModel.target_task_id.in_(tids)
            ).delete(synchronize_session=False)
            self.db.query(TaskDependencyModel).filter(
                TaskDependencyModel.source_task_id.in_(tids)
            ).delete(synchronize_session=False)

        # Subtask edges.
        if subtask_ids:
            sids = list(subtask_ids)
            self.db.query(SubtaskDependencyModel).filter(
                SubtaskDependencyModel.target_subtask_id.in_(sids)
            ).delete(synchronize_session=False)
            self.db.query(SubtaskDependencyModel).filter(
                SubtaskDependencyModel.source_subtask_id.in_(sids)
            ).delete(synchronize_session=False)
        self.db.flush()

    def cascade_remove_for_deleted_task_subtree(
        self, task_id: str, subtask_ids: Sequence[str],
    ) -> None:
        """Wipe edges for a task and its cascaded subtasks."""
        self.cascade_remove_task_targets(task_id)
        if subtask_ids:
            sids = list(subtask_ids)
            self.db.query(SubtaskDependencyModel).filter(
                SubtaskDependencyModel.target_subtask_id.in_(sids)
            ).delete(synchronize_session=False)
            self.db.query(SubtaskDependencyModel).filter(
                SubtaskDependencyModel.source_subtask_id.in_(sids)
            ).delete(synchronize_session=False)
        self.db.flush()

    # -------------------------------------------------------------------
    # Version cloning
    # -------------------------------------------------------------------

    def clone_activity_dependencies_for_version(
        self,
        source_project_id: str,
        target_project_id: str,
        activity_id_map: dict,
    ) -> int:
        """Copy activity_dependencies from a baseline into a new version,
        rewriting source/target ids using ``activity_id_map`` (baseline
        activity id → version-cloned activity id). Edges whose endpoints
        weren't cloned are silently skipped.

        Returns the number of edges inserted.

        Does NOT commit; the version-create transaction owns the commit.
        """
        if not activity_id_map:
            return 0

        src_edges = (
            self.db.query(
                ActivityDependencyModel.source_activity_id,
                ActivityDependencyModel.target_activity_id,
            )
            .filter(ActivityDependencyModel.project_id == source_project_id)
            .all()
        )
        inserted = 0
        for src, tgt in src_edges:
            new_src = activity_id_map.get(src)
            new_tgt = activity_id_map.get(tgt)
            if new_src is None or new_tgt is None:
                continue
            self.db.add(
                ActivityDependencyModel(
                    source_activity_id=new_src,
                    target_activity_id=new_tgt,
                    project_id=target_project_id,
                )
            )
            inserted += 1
        if inserted:
            self.db.flush()
        return inserted
