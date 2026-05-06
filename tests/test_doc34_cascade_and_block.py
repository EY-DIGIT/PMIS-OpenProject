"""Doc 34: cascade comments + attachments on M/A/T/S delete.

Subsequent commits in the same doc 34 series add:
  - external-dep block on delete (next commit)
  - restore cascade (commit after that)

Each cascade-method on the M/A/T/S repos was extended in this commit
to also stamp ``deleted_at`` on every comment + attachment whose
target lives anywhere in the about-to-be-deleted subtree, plus every
attachment that's bound (via ``comment_id``) to a comment we're
soft-deleting.

The tests build a small M → A → T → S tree, attach a comment + an
attachment at every level, soft-delete the entity at one level, and
assert the cascade reaches every descendant comment + attachment.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.models.activity import ActivityModel
from app.infrastructure.db.models.attachment import AttachmentModel
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


def _make_activity(db, *, milestone, name="A") -> ActivityModel:
    a = ActivityModel(
        id=str(uuid4()),
        project_id=milestone.project_id,
        milestone_id=milestone.id,
        name=name,
        type="standard",
        start_date=datetime(2026, 2, 1),
        end_date=datetime(2026, 6, 30),
        position=1,
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
) -> AttachmentModel:
    a = AttachmentModel(
        id=str(uuid4()),
        comment_id=comment_id,
        target_kind=target_kind,
        target_id=target_id,
        original_filename="x.pdf",
        storage_key=f"k/{uuid4()}",
        mime_type="application/pdf",
        size_bytes=1,
        uploaded_by_user_id=author_user_id,
    )
    db.add(a)
    db.flush()
    return a


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
                db_session, AttachmentModel,
                cascade_tree["target_attachments"][kind].id,
            ), f"target {kind} attachment should be soft-deleted"
        # Sibling milestone attachment stays live.
        assert _is_live(
            db_session, AttachmentModel,
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
            db_session, AttachmentModel,
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
        att = db_session.query(AttachmentModel).filter_by(
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
            db_session, AttachmentModel,
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
            db_session, AttachmentModel,
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
            db_session, AttachmentModel,
            cascade_tree["target_comment_bound_attachment"].id,
        )


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
