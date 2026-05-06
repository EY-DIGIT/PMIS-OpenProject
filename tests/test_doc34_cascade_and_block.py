"""Doc 34: cascade comments + attachments on M/A/T/S delete.

Subsequent commits in the same doc 34 series add:
  - external-dep block on delete (next commit)
  - restore cascade (commit after that)

Each cascade-method on the M/A/T/S repos was extended in this commit
to also stamp ``deleted_at`` on every comment whose target lives
anywhere in the about-to-be-deleted subtree.

Doc 35 update: the separate ``attachments`` table was collapsed onto
``comments.attachments`` (JSON column). What were "standalone
attachments" are now comment rows with NULL body. What were
"comment-bound attachments" are now JSON entries on the parent comment
row. The cascade walk only touches one table now (``comments``) — these
tests still cover the same lifecycle, but the assertions all read the
``CommentModel`` row (the JSON column rides along automatically).
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.models.activity import ActivityModel
# Doc 35: AttachmentModel removed (collapsed onto CommentModel.attachments JSON column).
from app.infrastructure.db.models.comment import CommentModel
from app.infrastructure.db.models.milestone import MilestoneModel
from app.infrastructure.db.models.subtask import SubtaskModel
from app.infrastructure.db.models.task import TaskModel


# ---------------------------------------------------------------------------
# Fixtures: build a project with one M/A/T/S branch, plus a sibling tree
# kept undeleted to make sure cascades stay scoped.
# ---------------------------------------------------------------------------


def _make_milestone(
    db, *, project_id, name="M", position=1,
) -> MilestoneModel:
    m = MilestoneModel(
        id=str(uuid4()),
        project_id=project_id,
        name=name,
        description="",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        position=position,
        status="not_completed",
    )
    db.add(m)
    db.flush()
    return m


def _make_activity(db, *, milestone, name="A", position=1) -> ActivityModel:
    a = ActivityModel(
        id=str(uuid4()),
        project_id=milestone.project_id,
        milestone_id=milestone.id,
        name=name,
        type="standard",
        start_date=datetime(2026, 2, 1),
        end_date=datetime(2026, 6, 30),
        position=position,
        status="not_completed",
    )
    db.add(a)
    db.flush()
    return a


def _make_task(db, *, activity, name="T") -> TaskModel:
    t = TaskModel(
        id=str(uuid4()),
        project_id=activity.project_id,
        activity_id=activity.id,
        name=name,
        type="standard",
        start_date=datetime(2026, 3, 1),
        end_date=datetime(2026, 6, 1),
        position=1,
    )
    db.add(t)
    db.flush()
    return t


def _make_subtask(db, *, task, name="S") -> SubtaskModel:
    s = SubtaskModel(
        id=str(uuid4()),
        project_id=task.project_id,
        task_id=task.id,
        name=name,
        type="standard",
        start_date=datetime(2026, 4, 1),
        end_date=datetime(2026, 5, 1),
        position=1,
    )
    db.add(s)
    db.flush()
    return s


def _add_comment(db, *, target_kind, target_id, author_user_id) -> CommentModel:
    c = CommentModel(
        id=str(uuid4()),
        target_kind=target_kind,
        target_id=target_id,
        body=f"comment on {target_kind}",
        author_user_id=author_user_id,
    )
    db.add(c)
    db.flush()
    return c


def _add_attachment(
    db, *,
    target_kind=None,
    target_id=None,
    comment_id=None,
    author_user_id,
) -> CommentModel:
    """Doc 35 shim — preserves the old test API while writing to the
    new single-table model.

    Two scenarios covered:
      * ``target_kind`` + ``target_id`` set, ``comment_id`` None
        → creates a new comment row with NULL body and one attachment
        in its JSON column. This is the doc-35 equivalent of a
        "standalone attachment".
      * ``comment_id`` set, ``target_kind`` / ``target_id`` None
        → appends one entry to the parent comment row's
        ``attachments`` JSON list. Returns the (mutated) parent comment
        so the test's ``_is_deleted(db, CommentModel, x.id)`` assertions
        check the parent — which is exactly the cascade target now.
    """
    file_entry = {
        "url": f"local/{uuid4()}",
        "filename": "x.pdf",
        "mimeType": "application/pdf",
        "sizeBytes": 1,
        "uploadedAt": None,
    }
    if comment_id is not None:
        # Comment-bound: append to the parent comment's JSON list and
        # return the parent so test assertions look it up by id.
        parent = db.query(CommentModel).filter_by(id=comment_id).one()
        existing = list(parent.attachments or [])
        existing.append(file_entry)
        parent.attachments = existing
        # SQLAlchemy doesn't auto-detect mutations to JSON column values;
        # poke the attribute so the change is flushed.
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(parent, "attachments")
        db.flush()
        return parent

    # Standalone: a body-NULL comment row carrying one attachment entry.
    c = CommentModel(
        id=str(uuid4()),
        target_kind=target_kind,
        target_id=target_id,
        body=None,
        attachments=[file_entry],
        author_user_id=author_user_id,
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def cascade_tree(db_session, sample_project, admin_user):
    """Build a project with two milestone subtrees:

      target_M ── target_A ── target_T ── target_S    (gets deleted)
      sibling_M ── sibling_A ── sibling_T ── sibling_S (stays alive)

    Each entity carries one direct comment + one standalone attachment.
    The target_T's comment carries a comment-bound attachment too — used
    to verify the comment_id sweep in the cascade.
    """
    pid = sample_project.id

    # Target subtree (will be deleted).
    target_M = _make_milestone(db_session, project_id=pid, name="target_M")
    target_A = _make_activity(db_session, milestone=target_M, name="target_A")
    target_T = _make_task(db_session, activity=target_A, name="target_T")
    target_S = _make_subtask(db_session, task=target_T, name="target_S")

    # Sibling subtree (must stay alive). position must differ from
    # target_M because milestone position is unique per-project among
    # live rows.
    sibling_M = _make_milestone(
        db_session, project_id=pid, name="sibling_M", position=2,
    )
    sibling_A = _make_activity(db_session, milestone=sibling_M, name="sibling_A")
    sibling_T = _make_task(db_session, activity=sibling_A, name="sibling_T")
    sibling_S = _make_subtask(db_session, task=sibling_T, name="sibling_S")

    aid = admin_user.id

    target_comments = {
        "milestone": _add_comment(
            db_session, target_kind="milestone",
            target_id=target_M.id, author_user_id=aid,
        ),
        "activity": _add_comment(
            db_session, target_kind="activity",
            target_id=target_A.id, author_user_id=aid,
        ),
        "task": _add_comment(
            db_session, target_kind="task",
            target_id=target_T.id, author_user_id=aid,
        ),
        "subtask": _add_comment(
            db_session, target_kind="subtask",
            target_id=target_S.id, author_user_id=aid,
        ),
    }
    target_attachments = {
        "milestone": _add_attachment(
            db_session, target_kind="milestone",
            target_id=target_M.id, author_user_id=aid,
        ),
        "activity": _add_attachment(
            db_session, target_kind="activity",
            target_id=target_A.id, author_user_id=aid,
        ),
        "task": _add_attachment(
            db_session, target_kind="task",
            target_id=target_T.id, author_user_id=aid,
        ),
        "subtask": _add_attachment(
            db_session, target_kind="subtask",
            target_id=target_S.id, author_user_id=aid,
        ),
    }
    # Comment-bound attachment under the target_T comment.
    target_comment_bound = _add_attachment(
        db_session, comment_id=target_comments["task"].id, author_user_id=aid,
    )

    sibling_comments = {
        "milestone": _add_comment(
            db_session, target_kind="milestone",
            target_id=sibling_M.id, author_user_id=aid,
        ),
        "activity": _add_comment(
            db_session, target_kind="activity",
            target_id=sibling_A.id, author_user_id=aid,
        ),
        "task": _add_comment(
            db_session, target_kind="task",
            target_id=sibling_T.id, author_user_id=aid,
        ),
        "subtask": _add_comment(
            db_session, target_kind="subtask",
            target_id=sibling_S.id, author_user_id=aid,
        ),
    }
    sibling_attachments = {
        "milestone": _add_attachment(
            db_session, target_kind="milestone",
            target_id=sibling_M.id, author_user_id=aid,
        ),
    }

    db_session.commit()

    return {
        "project_id": pid,
        "admin_id": aid,
        "target_M": target_M,
        "target_A": target_A,
        "target_T": target_T,
        "target_S": target_S,
        "target_comments": target_comments,
        "target_attachments": target_attachments,
        "target_comment_bound_attachment": target_comment_bound,
        "sibling_M": sibling_M,
        "sibling_A": sibling_A,
        "sibling_T": sibling_T,
        "sibling_S": sibling_S,
        "sibling_comments": sibling_comments,
        "sibling_attachments": sibling_attachments,
    }


def _is_deleted(db, model_cls, row_id) -> bool:
    row = db.query(model_cls).filter_by(id=row_id).one()
    return row.deleted_at is not None


def _is_live(db, model_cls, row_id) -> bool:
    return not _is_deleted(db, model_cls, row_id)


# ---------------------------------------------------------------------------
# Cascade tests
# ---------------------------------------------------------------------------


class TestMilestoneDeleteCascadesCommentsAttachments:
    def test_milestone_delete_soft_deletes_comments_at_every_level(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.milestone_repository import (
            MilestoneRepository,
        )
        repo = MilestoneRepository(db_session)
        repo.soft_delete_with_cascade(
            cascade_tree["target_M"].id, deleted_by=admin_user.id,
        )

        # Every target-side comment is soft-deleted.
        for kind in ("milestone", "activity", "task", "subtask"):
            assert _is_deleted(
                db_session, CommentModel,
                cascade_tree["target_comments"][kind].id,
            ), f"target {kind} comment should be soft-deleted"

        # Every sibling-side comment stays live.
        for kind in ("milestone", "activity", "task", "subtask"):
            assert _is_live(
                db_session, CommentModel,
                cascade_tree["sibling_comments"][kind].id,
            ), f"sibling {kind} comment must NOT be touched"

    def test_milestone_delete_soft_deletes_standalone_attachments(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.milestone_repository import (
            MilestoneRepository,
        )
        MilestoneRepository(db_session).soft_delete_with_cascade(
            cascade_tree["target_M"].id, deleted_by=admin_user.id,
        )
        for kind in ("milestone", "activity", "task", "subtask"):
            assert _is_deleted(
                db_session, CommentModel,
                cascade_tree["target_attachments"][kind].id,
            ), f"target {kind} attachment should be soft-deleted"
        # Sibling milestone attachment stays live.
        assert _is_live(
            db_session, CommentModel,
            cascade_tree["sibling_attachments"]["milestone"].id,
        )

    def test_milestone_delete_soft_deletes_comment_bound_attachments(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.milestone_repository import (
            MilestoneRepository,
        )
        MilestoneRepository(db_session).soft_delete_with_cascade(
            cascade_tree["target_M"].id, deleted_by=admin_user.id,
        )
        # The comment-bound attachment under target_T's comment should
        # follow the comment, not via target_kind/target_id.
        assert _is_deleted(
            db_session, CommentModel,
            cascade_tree["target_comment_bound_attachment"].id,
        )

    def test_cascade_uses_uniform_timestamp(
        self, db_session, cascade_tree, admin_user,
    ):
        """Every row stamped by a single cascade shares one ``deleted_at``
        instant — needed by the matching restore cascade in step 3."""
        from app.infrastructure.db.repositories.milestone_repository import (
            MilestoneRepository,
        )
        MilestoneRepository(db_session).soft_delete_with_cascade(
            cascade_tree["target_M"].id, deleted_by=admin_user.id,
        )
        m = db_session.query(MilestoneModel).filter_by(
            id=cascade_tree["target_M"].id,
        ).one()
        ts = m.deleted_at
        assert ts is not None
        # Every deleted descendant + comment + attachment carries the
        # same timestamp.
        a = db_session.query(ActivityModel).filter_by(
            id=cascade_tree["target_A"].id,
        ).one()
        c = db_session.query(CommentModel).filter_by(
            id=cascade_tree["target_comments"]["activity"].id,
        ).one()
        att = db_session.query(CommentModel).filter_by(
            id=cascade_tree["target_attachments"]["task"].id,
        ).one()
        assert a.deleted_at == ts
        assert c.deleted_at == ts
        assert att.deleted_at == ts


class TestActivityDeleteCascadesCommentsAttachments:
    def test_activity_delete_soft_deletes_comments_below(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.activity_repository import (
            ActivityRepository,
        )
        ActivityRepository(db_session).soft_delete_with_cascade(
            cascade_tree["target_A"].id, deleted_by=admin_user.id,
        )
        # A/T/S comments deleted; M comment stays live.
        for kind in ("activity", "task", "subtask"):
            assert _is_deleted(
                db_session, CommentModel,
                cascade_tree["target_comments"][kind].id,
            )
        assert _is_live(
            db_session, CommentModel,
            cascade_tree["target_comments"]["milestone"].id,
        )


class TestTaskDeleteCascadesCommentsAttachments:
    def test_task_delete_soft_deletes_t_and_s(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.task_repository import (
            TaskRepository,
        )
        TaskRepository(db_session).soft_delete_with_cascade(
            cascade_tree["target_T"].id, deleted_by=admin_user.id,
        )
        # T + S comments deleted; M + A stay live.
        for kind in ("task", "subtask"):
            assert _is_deleted(
                db_session, CommentModel,
                cascade_tree["target_comments"][kind].id,
            )
        for kind in ("milestone", "activity"):
            assert _is_live(
                db_session, CommentModel,
                cascade_tree["target_comments"][kind].id,
            )

    def test_task_delete_cascades_comment_bound_attachment(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.task_repository import (
            TaskRepository,
        )
        TaskRepository(db_session).soft_delete_with_cascade(
            cascade_tree["target_T"].id, deleted_by=admin_user.id,
        )
        assert _is_deleted(
            db_session, CommentModel,
            cascade_tree["target_comment_bound_attachment"].id,
        )


class TestSubtaskDeleteCascadesCommentsAttachments:
    def test_subtask_delete_soft_deletes_s_only(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.subtask_repository import (
            SubtaskRepository,
        )
        SubtaskRepository(db_session).soft_delete(
            cascade_tree["target_S"].id, deleted_by=admin_user.id,
        )
        assert _is_deleted(
            db_session, CommentModel,
            cascade_tree["target_comments"]["subtask"].id,
        )
        assert _is_deleted(
            db_session, CommentModel,
            cascade_tree["target_attachments"]["subtask"].id,
        )
        # M / A / T comments + attachments stay live.
        for kind in ("milestone", "activity", "task"):
            assert _is_live(
                db_session, CommentModel,
                cascade_tree["target_comments"][kind].id,
            )


class TestProjectDeleteCascadesEverything:
    def test_project_cascade_wipes_all_comments_and_attachments(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.api.v3.milestones.services.cascade import (
            cascade_soft_delete_project,
        )
        cascade_soft_delete_project(
            db_session, cascade_tree["project_id"],
            deleted_by=admin_user.id,
        )
        db_session.commit()
        # Every comment + attachment under the project is gone, on
        # both subtrees.
        for kind in ("milestone", "activity", "task", "subtask"):
            assert _is_deleted(
                db_session, CommentModel,
                cascade_tree["target_comments"][kind].id,
            )
            assert _is_deleted(
                db_session, CommentModel,
                cascade_tree["sibling_comments"][kind].id,
            )
        # The comment-bound attachment is also gone.
        assert _is_deleted(
            db_session, CommentModel,
            cascade_tree["target_comment_bound_attachment"].id,
        )


class TestExternalDepBlock:
    """Doc 34 (2/3): refuse delete when an external entity depends on
    something inside the subtree."""

    def _make_milestone_dep(
        self, db, *, source_milestone, target_milestone,
    ):
        from app.infrastructure.db.models.milestone_dependency import (
            MilestoneDependencyModel,
        )
        edge = MilestoneDependencyModel(
            id=str(uuid4()),
            source_milestone_id=source_milestone.id,
            target_milestone_id=target_milestone.id,
            project_id=source_milestone.project_id,
        )
        db.add(edge)
        db.commit()
        return edge

    def _make_activity_dep(self, db, *, source_activity, target_activity):
        from app.infrastructure.db.models.activity_dependency import (
            ActivityDependencyModel,
        )
        edge = ActivityDependencyModel(
            id=str(uuid4()),
            source_activity_id=source_activity.id,
            target_activity_id=target_activity.id,
            project_id=source_activity.project_id,
        )
        db.add(edge)
        db.commit()
        return edge

    def _make_task_dep(self, db, *, source_task, target_task):
        from app.infrastructure.db.models.task_dependency import (
            TaskDependencyModel,
        )
        edge = TaskDependencyModel(
            id=str(uuid4()),
            source_task_id=source_task.id,
            target_task_id=target_task.id,
            project_id=source_task.project_id,
        )
        db.add(edge)
        db.commit()
        return edge

    def _make_subtask_dep(self, db, *, source_subtask, target_subtask):
        from app.infrastructure.db.models.subtask_dependency import (
            SubtaskDependencyModel,
        )
        edge = SubtaskDependencyModel(
            id=str(uuid4()),
            source_subtask_id=source_subtask.id,
            target_subtask_id=target_subtask.id,
            project_id=source_subtask.project_id,
        )
        db.add(edge)
        db.commit()
        return edge

    def test_milestone_dep_blocks_milestone_delete(
        self, db_session, cascade_tree, admin_user,
    ):
        """sibling_M depends on target_M ⇒ deleting target_M is refused."""
        from app.api.v3.milestones.services.delete import delete_milestone
        from app.core.errors import ValidationError

        self._make_milestone_dep(
            db_session,
            source_milestone=cascade_tree["sibling_M"],
            target_milestone=cascade_tree["target_M"],
        )

        with pytest.raises(ValidationError) as exc_info:
            delete_milestone(
                db_session,
                milestone_id=cascade_tree["target_M"].id,
                current_user_id=admin_user.id,
            )
        details = exc_info.value.details
        assert details["errorIdentifier"] == "dependency_block"
        assert details["rootKind"] == "milestone"
        # Exactly one blocker, sibling_M → target_M.
        blockers = details["blockers"]
        assert len(blockers) == 1
        assert blockers[0]["sourceKind"] == "milestone"
        assert blockers[0]["targetKind"] == "milestone"
        # target_M was not soft-deleted.
        m = db_session.query(MilestoneModel).filter_by(
            id=cascade_tree["target_M"].id,
        ).one()
        assert m.deleted_at is None

    def test_external_activity_dep_on_child_blocks_milestone_delete(
        self, db_session, cascade_tree, admin_user,
    ):
        """sibling_A depends on target_A ⇒ deleting target_M (which
        contains target_A) is refused. The blocker names target_A's
        label, not target_M's."""
        from app.api.v3.milestones.services.delete import delete_milestone
        from app.core.errors import ValidationError

        self._make_activity_dep(
            db_session,
            source_activity=cascade_tree["sibling_A"],
            target_activity=cascade_tree["target_A"],
        )

        with pytest.raises(ValidationError) as exc_info:
            delete_milestone(
                db_session,
                milestone_id=cascade_tree["target_M"].id,
                current_user_id=admin_user.id,
            )
        blockers = exc_info.value.details["blockers"]
        assert len(blockers) == 1
        assert blockers[0]["sourceKind"] == "activity"
        assert blockers[0]["targetKind"] == "activity"

    def test_external_task_dep_blocks_activity_delete(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.api.v3.activities.services.delete import delete_activity
        from app.core.errors import ValidationError

        self._make_task_dep(
            db_session,
            source_task=cascade_tree["sibling_T"],
            target_task=cascade_tree["target_T"],
        )

        with pytest.raises(ValidationError) as exc_info:
            delete_activity(
                db_session,
                activity_id=cascade_tree["target_A"].id,
                current_user_id=admin_user.id,
            )
        blockers = exc_info.value.details["blockers"]
        assert len(blockers) == 1
        assert blockers[0]["sourceKind"] == "task"

    def test_external_subtask_dep_blocks_task_delete(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.api.v3.tasks.services.delete import delete_task
        from app.core.errors import ValidationError

        self._make_subtask_dep(
            db_session,
            source_subtask=cascade_tree["sibling_S"],
            target_subtask=cascade_tree["target_S"],
        )

        with pytest.raises(ValidationError) as exc_info:
            delete_task(
                db_session,
                task_id=cascade_tree["target_T"].id,
                current_user_id=admin_user.id,
            )
        blockers = exc_info.value.details["blockers"]
        assert len(blockers) == 1
        assert blockers[0]["sourceKind"] == "subtask"

    def test_external_subtask_dep_blocks_subtask_delete(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.api.v3.subtasks.services.delete import delete_subtask
        from app.core.errors import ValidationError

        self._make_subtask_dep(
            db_session,
            source_subtask=cascade_tree["sibling_S"],
            target_subtask=cascade_tree["target_S"],
        )
        with pytest.raises(ValidationError) as exc_info:
            delete_subtask(
                db_session,
                subtask_id=cascade_tree["target_S"].id,
                current_user_id=admin_user.id,
            )
        assert exc_info.value.details["errorIdentifier"] == "dependency_block"

    def test_self_contained_dep_does_not_block(
        self, db_session, cascade_tree, admin_user,
    ):
        """target_T → target_S (both inside the about-to-be-deleted M
        subtree) should NOT block. Cascade soft-deletes both edges +
        entities consistently."""
        from app.api.v3.milestones.services.delete import delete_milestone

        # target_S depends on target_T, both in M's subtree
        # (subtask deps reference subtasks; cross-kind deps don't exist
        # in this codebase — fake one entirely inside the target M's
        # subtree by giving the target_T a "self subtree" dep where
        # source==target on a different test row).
        # Cleanest: M-level self-contained — make target_M depend on
        # itself? Self-edges aren't allowed at insert time but we can
        # bypass by going at the model layer (test-only).
        # Simpler & more honest: build a SECOND milestone *inside the
        # same project's target subtree* — but milestones have no
        # parent — so we use activity-level: target_A2 depends on
        # target_A. Both inside target_M. Deleting target_M cascades
        # them together.
        target_A2 = _make_activity(
            db_session,
            milestone=cascade_tree["target_M"],
            name="target_A2",
            position=2,
        )
        db_session.commit()
        self._make_activity_dep(
            db_session,
            source_activity=target_A2,
            target_activity=cascade_tree["target_A"],
        )

        # No exception expected.
        delete_milestone(
            db_session,
            milestone_id=cascade_tree["target_M"].id,
            current_user_id=admin_user.id,
        )
        m = db_session.query(MilestoneModel).filter_by(
            id=cascade_tree["target_M"].id,
        ).one()
        assert m.deleted_at is not None

    def test_soft_deleted_dep_does_not_block(
        self, db_session, cascade_tree, admin_user,
    ):
        """A dep edge that's already soft-deleted is ignored — only
        live edges block."""
        from datetime import datetime, timezone
        from app.api.v3.milestones.services.delete import delete_milestone

        edge = self._make_milestone_dep(
            db_session,
            source_milestone=cascade_tree["sibling_M"],
            target_milestone=cascade_tree["target_M"],
        )
        edge.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # No exception — dead edges don't block.
        delete_milestone(
            db_session,
            milestone_id=cascade_tree["target_M"].id,
            current_user_id=admin_user.id,
        )

    def test_blocker_message_carries_labels(
        self, db_session, cascade_tree, admin_user,
    ):
        """Blocker labels resolve to display codes (M1, M2…) when
        available, falling back to UUIDs otherwise."""
        from app.api.v3.milestones.services.delete import delete_milestone
        from app.core.errors import ValidationError

        self._make_milestone_dep(
            db_session,
            source_milestone=cascade_tree["sibling_M"],
            target_milestone=cascade_tree["target_M"],
        )
        with pytest.raises(ValidationError) as exc_info:
            delete_milestone(
                db_session,
                milestone_id=cascade_tree["target_M"].id,
                current_user_id=admin_user.id,
            )
        # Source label should be the display code or name. Either way
        # it must NOT be the raw UUID (length 36 with dashes).
        src = exc_info.value.details["blockers"][0]["source"]
        # Reasonable label — short or matches a known display-code shape.
        assert len(src) < 36 or src in (
            cascade_tree["sibling_M"].name,
        )


class TestRestoreCascade:
    """Doc 34 (3/3): restoring an M/A/T/S also restores the rows that
    were cascade-soft-deleted with it (matched by deleted_at
    timestamp). Dep edges are NOT auto-restored."""

    def test_milestone_restore_revives_atss_subtree(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.milestone_repository import (
            MilestoneRepository,
        )
        repo = MilestoneRepository(db_session)
        repo.soft_delete_with_cascade(
            cascade_tree["target_M"].id, deleted_by=admin_user.id,
        )
        # Sanity: subtree is dead.
        assert _is_deleted(db_session, MilestoneModel, cascade_tree["target_M"].id)
        assert _is_deleted(db_session, ActivityModel, cascade_tree["target_A"].id)
        assert _is_deleted(db_session, TaskModel, cascade_tree["target_T"].id)
        assert _is_deleted(db_session, SubtaskModel, cascade_tree["target_S"].id)

        repo.restore(cascade_tree["target_M"].id, restored_by=admin_user.id)

        # All four levels alive again.
        assert _is_live(db_session, MilestoneModel, cascade_tree["target_M"].id)
        assert _is_live(db_session, ActivityModel, cascade_tree["target_A"].id)
        assert _is_live(db_session, TaskModel, cascade_tree["target_T"].id)
        assert _is_live(db_session, SubtaskModel, cascade_tree["target_S"].id)

    def test_milestone_restore_revives_comments_and_attachments(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.milestone_repository import (
            MilestoneRepository,
        )
        repo = MilestoneRepository(db_session)
        repo.soft_delete_with_cascade(
            cascade_tree["target_M"].id, deleted_by=admin_user.id,
        )
        repo.restore(cascade_tree["target_M"].id, restored_by=admin_user.id)

        for kind in ("milestone", "activity", "task", "subtask"):
            assert _is_live(
                db_session, CommentModel,
                cascade_tree["target_comments"][kind].id,
            ), f"{kind} comment should be revived"
            assert _is_live(
                db_session, CommentModel,
                cascade_tree["target_attachments"][kind].id,
            ), f"{kind} attachment-row should be revived"
        # Comment-bound attachment also revived.
        assert _is_live(
            db_session, CommentModel,
            cascade_tree["target_comment_bound_attachment"].id,
        )

    def test_restore_does_not_revive_independently_deleted_rows(
        self, db_session, cascade_tree, admin_user,
    ):
        """A comment soft-deleted independently before the milestone
        cascade should stay dead after the milestone is restored."""
        independent_ts = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
        c = cascade_tree["target_comments"]["activity"]
        c.deleted_at = independent_ts
        db_session.commit()

        from app.infrastructure.db.repositories.milestone_repository import (
            MilestoneRepository,
        )
        repo = MilestoneRepository(db_session)
        repo.soft_delete_with_cascade(
            cascade_tree["target_M"].id, deleted_by=admin_user.id,
        )
        repo.restore(cascade_tree["target_M"].id, restored_by=admin_user.id)

        # The activity-level comment should NOT be revived because its
        # deleted_at predates the cascade.
        c_after = db_session.query(CommentModel).filter_by(id=c.id).one()
        assert c_after.deleted_at is not None, (
            "comment soft-deleted independently must not be revived by "
            "the parent's cascade restore"
        )

    def test_activity_restore_revives_t_and_s_only(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.activity_repository import (
            ActivityRepository,
        )
        repo = ActivityRepository(db_session)
        repo.soft_delete_with_cascade(
            cascade_tree["target_A"].id, deleted_by=admin_user.id,
        )
        # Milestone untouched — only A/T/S go dead.
        assert _is_live(db_session, MilestoneModel, cascade_tree["target_M"].id)
        assert _is_deleted(db_session, ActivityModel, cascade_tree["target_A"].id)

        repo.restore(cascade_tree["target_A"].id, restored_by=admin_user.id)
        assert _is_live(db_session, ActivityModel, cascade_tree["target_A"].id)
        assert _is_live(db_session, TaskModel, cascade_tree["target_T"].id)
        assert _is_live(db_session, SubtaskModel, cascade_tree["target_S"].id)

    def test_task_restore_revives_subtasks(
        self, db_session, cascade_tree, admin_user,
    ):
        from app.infrastructure.db.repositories.task_repository import (
            TaskRepository,
        )
        repo = TaskRepository(db_session)
        repo.soft_delete_with_cascade(
            cascade_tree["target_T"].id, deleted_by=admin_user.id,
        )
        repo.restore(cascade_tree["target_T"].id, restored_by=admin_user.id)
        assert _is_live(db_session, TaskModel, cascade_tree["target_T"].id)
        assert _is_live(db_session, SubtaskModel, cascade_tree["target_S"].id)

    def test_subtask_restore_revives_nested_descendants(
        self, db_session, cascade_tree, admin_user,
    ):
        # Add a nested subtask under target_S.
        nested = SubtaskModel(
            id=str(uuid4()),
            project_id=cascade_tree["target_S"].project_id,
            task_id=cascade_tree["target_S"].task_id,
            parent_subtask_id=cascade_tree["target_S"].id,
            name="nested",
            type="standard",
            start_date=datetime(2026, 4, 5),
            end_date=datetime(2026, 4, 25),
            position=1,
        )
        db_session.add(nested)
        db_session.commit()

        from app.infrastructure.db.repositories.subtask_repository import (
            SubtaskRepository,
        )
        repo = SubtaskRepository(db_session)
        repo.soft_delete(
            cascade_tree["target_S"].id, deleted_by=admin_user.id,
        )
        assert _is_deleted(db_session, SubtaskModel, cascade_tree["target_S"].id)
        assert _is_deleted(db_session, SubtaskModel, nested.id)

        repo.restore(cascade_tree["target_S"].id, restored_by=admin_user.id)
        assert _is_live(db_session, SubtaskModel, cascade_tree["target_S"].id)
        assert _is_live(db_session, SubtaskModel, nested.id)


class TestPreExistingSoftDeletesNotReStamped:
    def test_already_deleted_comment_is_not_re_touched(
        self, db_session, cascade_tree, admin_user,
    ):
        """A comment that was soft-deleted yesterday should keep its
        original ``deleted_at`` even after a parent cascade runs today.
        Cascade is idempotent; it must not overwrite earlier timestamps."""
        existing_ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        c = cascade_tree["target_comments"]["activity"]
        c.deleted_at = existing_ts
        db_session.flush()
        db_session.commit()

        from app.infrastructure.db.repositories.milestone_repository import (
            MilestoneRepository,
        )
        MilestoneRepository(db_session).soft_delete_with_cascade(
            cascade_tree["target_M"].id, deleted_by=admin_user.id,
        )

        # Re-read; deleted_at should still be the original timestamp,
        # not the cascade timestamp.
        c_re = db_session.query(CommentModel).filter_by(id=c.id).one()
        # Compare as timestamps regardless of tz form
        c_re_ts = c_re.deleted_at
        if c_re_ts.tzinfo is None:
            c_re_ts = c_re_ts.replace(tzinfo=timezone.utc)
        assert c_re_ts == existing_ts
