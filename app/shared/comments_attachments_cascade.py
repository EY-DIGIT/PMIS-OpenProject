"""Cascade soft-delete + restore of comments + attachments.

Comments and attachments are polymorphic on ``(target_kind, target_id)``
— there's no FK from these tables to the M/A/T/S rows they decorate, so
SQL-level cascades aren't an option. When an M/A/T/S row is soft-deleted
the comments + attachments under it would otherwise dangle as orphan
rows pointing at a now-invisible target. Conversely on restore they
should come back together.

Two helpers, one for each direction:

  - ``cascade_soft_delete_comments_and_attachments`` — stamp ``deleted_at``
    on every (kind, id) pair plus any attachment bound (via ``comment_id``)
    to a comment we just stamped. Idempotent.

  - ``cascade_restore_comments_and_attachments`` — clear ``deleted_at``
    on every row whose ``deleted_at`` exactly matches the cascade
    timestamp. The timestamp predicate distinguishes "deleted with this
    parent" from "previously soft-deleted before the parent was deleted",
    so a restore brings back exactly the rows the matching cascade
    soft-deleted, no more.

Used by every M/A/T/S delete + restore service so a cascade and its
inverse stay symmetric.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Tuple, Union

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from ..infrastructure.db.models.attachment import AttachmentModel
from ..infrastructure.db.models.comment import CommentModel


# A target predicate: either a single id, a list of ids, or a SQLAlchemy
# Select sub-query that resolves to ids (used when the id set is derived
# from another table — e.g. "every activity under this milestone").
TargetIds = Union[str, List[str], Select]


def _id_match(column, ids: TargetIds):
    """Equality for a single id, IN for a list / subquery."""
    if isinstance(ids, str):
        return column == ids
    return column.in_(ids)


def cascade_soft_delete_comments_and_attachments(
    db: Session,
    *,
    targets: List[Tuple[str, TargetIds]],
    deleted_by: Optional[Any],
    now: datetime,
) -> None:
    """Soft-delete every comment + attachment anchored at any of the
    given ``(target_kind, target_id_or_clause)`` pairs, plus every
    attachment bound (via ``comment_id``) to a comment we just stamped.

    ``targets`` is a list like::

        [
            ("milestone", "abc-uuid"),
            ("activity", select(ActivityModel.id).where(...)),
            ("task", task_ids_subquery),
            ("subtask", subtask_ids_subquery),
        ]

    ``now`` and ``deleted_by`` are stamped uniformly across every row
    soft-deleted in this call. Using a single timestamp lets the
    matching restore helper identify exactly which rows to bring back
    when the parent is restored.

    Idempotent — already-soft-deleted rows are skipped.
    """
    if not targets:
        return

    # OR across every (kind, id) pair so a single UPDATE covers the
    # whole subtree per table.
    comment_filter = or_(*[
        (CommentModel.target_kind == kind) & _id_match(CommentModel.target_id, ids)
        for kind, ids in targets
    ])
    attachment_filter = or_(*[
        (AttachmentModel.target_kind == kind) & _id_match(AttachmentModel.target_id, ids)
        for kind, ids in targets
    ])

    # Snapshot the comment ids we're about to stamp — needed in step 3
    # to find their bound attachments.
    doomed_comment_ids = [
        r[0]
        for r in db.execute(
            select(CommentModel.id).where(
                comment_filter,
                CommentModel.deleted_at.is_(None),
            )
        ).all()
    ]

    # Step 1: comments anchored at any (kind, id) target.
    db.execute(
        update(CommentModel)
        .where(comment_filter, CommentModel.deleted_at.is_(None))
        .values(deleted_at=now, updated_at=now, deleted_by=deleted_by)
    )

    # Step 2: standalone attachments anchored at any (kind, id) target.
    # Standalone = comment_id IS NULL; the polymorphic target_kind +
    # target_id columns carry the M/A/T/S anchor. The OR clause already
    # filters by (target_kind, target_id) so the comment_id IS NULL
    # constraint isn't strictly needed, but adding it avoids accidentally
    # double-stamping rows that are also matched by the comment_id sweep
    # in step 3.
    db.execute(
        update(AttachmentModel)
        .where(
            attachment_filter,
            AttachmentModel.deleted_at.is_(None),
            AttachmentModel.comment_id.is_(None),
        )
        .values(deleted_at=now, deleted_by=deleted_by)
    )

    # Step 3: attachments bound to one of the comments we just stamped.
    # A comment-bound attachment's target lives via the parent comment,
    # not via target_kind/target_id, so it wouldn't be caught by step 2.
    if doomed_comment_ids:
        db.execute(
            update(AttachmentModel)
            .where(
                AttachmentModel.comment_id.in_(doomed_comment_ids),
                AttachmentModel.deleted_at.is_(None),
            )
            .values(deleted_at=now, deleted_by=deleted_by)
        )


def cascade_restore_comments_and_attachments(
    db: Session,
    *,
    targets: List[Tuple[str, TargetIds]],
    cascade_deleted_at: datetime,
) -> None:
    """Inverse of the soft-delete cascade.

    Brings back every comment + attachment whose ``deleted_at`` exactly
    matches ``cascade_deleted_at`` AND that's anchored at one of the
    given ``targets`` (or, for attachments, bound to a comment we're
    restoring in this same call).

    The timestamp match is the key — it distinguishes rows soft-deleted
    by THIS cascade from rows soft-deleted by an earlier independent
    action. A user who manually deleted a comment yesterday should NOT
    have it spring back to life because their parent milestone was
    deleted+restored today.

    Idempotent — already-live rows are skipped.
    """
    if not targets:
        return

    comment_filter = or_(*[
        (CommentModel.target_kind == kind) & _id_match(CommentModel.target_id, ids)
        for kind, ids in targets
    ])
    attachment_filter = or_(*[
        (AttachmentModel.target_kind == kind) & _id_match(AttachmentModel.target_id, ids)
        for kind, ids in targets
    ])

    # Snapshot the comment ids we're about to bring back so we can also
    # restore their bound attachments.
    revived_comment_ids = [
        r[0]
        for r in db.execute(
            select(CommentModel.id).where(
                comment_filter,
                CommentModel.deleted_at == cascade_deleted_at,
            )
        ).all()
    ]

    db.execute(
        update(CommentModel)
        .where(
            comment_filter,
            CommentModel.deleted_at == cascade_deleted_at,
        )
        .values(deleted_at=None, deleted_by=None)
    )
    db.execute(
        update(AttachmentModel)
        .where(
            attachment_filter,
            AttachmentModel.deleted_at == cascade_deleted_at,
            AttachmentModel.comment_id.is_(None),
        )
        .values(deleted_at=None, deleted_by=None)
    )
    if revived_comment_ids:
        db.execute(
            update(AttachmentModel)
            .where(
                AttachmentModel.comment_id.in_(revived_comment_ids),
                AttachmentModel.deleted_at == cascade_deleted_at,
            )
            .values(deleted_at=None, deleted_by=None)
        )
