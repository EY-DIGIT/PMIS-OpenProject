"""Tests for ``GET /api/v3/projects/{project_uuid}/discussion-feed``.

Aggregates every comment row (body + attachments, both optional) tied
to the project itself OR any of its descendants
(milestone / activity / task / subtask) in one flat, newest-first,
paginated feed.

Coverage:
  * 404 on unknown project
  * Empty project tree → empty feed
  * Project-level attachments surface
  * M / A / T / S comments + attachments all collected together
  * targetKind / targetId / targetName resolved per row
  * Soft-deleted comments + soft-deleted targets filtered out
  * Pagination + ordering (newest-first)
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

import app.infrastructure.storage as storage_pkg
from app.infrastructure.storage import reset_file_client_for_tests
from app.infrastructure.storage.file_storage import FileStorage

from app.infrastructure.db.models.activity import ActivityModel
from app.infrastructure.db.models.milestone import MilestoneModel
from app.infrastructure.db.models.subtask import SubtaskModel
from app.infrastructure.db.models.task import TaskModel


PDF_HEADER = b"%PDF-1.4 test\n"


@pytest.fixture(scope="function")
def temp_storage(tmp_path, monkeypatch):
    tmp = FileStorage(
        base_path=str(tmp_path / "storage"),
        subdir_strategy="year_month",
    )
    tmp.ensure_ready()
    monkeypatch.setattr(storage_pkg.file_storage, "_storage", tmp)
    reset_file_client_for_tests()
    yield tmp
    reset_file_client_for_tests()


def _make_milestone(db, project_id, name="M1"):
    m = MilestoneModel(
        id=str(uuid4()),
        project_id=project_id,
        name=name,
        position=0,
        status="not_completed",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _make_activity(db, project_id, milestone_id, name="A1"):
    a = ActivityModel(
        id=str(uuid4()),
        project_id=project_id,
        milestone_id=milestone_id,
        name=name,
        position=0,
        status="not_completed",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 6, 30),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _make_task(db, project_id, activity_id, name="T1"):
    t = TaskModel(
        id=str(uuid4()),
        project_id=project_id,
        activity_id=activity_id,
        name=name,
        position=0,
        status="not_completed",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 6, 30),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _make_subtask(db, project_id, task_id, name="S1"):
    s = SubtaskModel(
        id=str(uuid4()),
        project_id=project_id,
        task_id=task_id,
        name=name,
        position=0,
        status="not_completed",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 6, 30),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ===========================================================================
# Tests
# ===========================================================================

class TestDiscussionFeedBasics:
    def test_404_on_unknown_project(self, client, admin_user, admin_headers):
        r = client.get(
            f"/api/v3/projects/{uuid4()}/discussion-feed",
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_empty_project_tree_empty_feed(
        self, client, admin_user, admin_headers, sample_project,
    ):
        r = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed",
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["total"] == 0
        assert data["_embedded"]["elements"] == []
        assert data["project"]["id"] == sample_project.id


class TestDiscussionFeedAggregation:
    def test_collects_across_project_tree(
        self, client, admin_user, admin_headers, sample_project,
        db_session, temp_storage,
    ):
        # Build a tree: project → milestone → activity → task → subtask.
        m = _make_milestone(db_session, sample_project.id, name="Milestone-A")
        a = _make_activity(
            db_session, sample_project.id, m.id, name="Activity-A",
        )
        t = _make_task(
            db_session, sample_project.id, a.id, name="Task-A",
        )
        s = _make_subtask(
            db_session, sample_project.id, t.id, name="Subtask-A",
        )

        # 1) Project-level attachment.
        client.post(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
            files=[("files", ("charter.pdf", PDF_HEADER, "application/pdf"))],
        )
        # 2) Milestone comment with body + file.
        client.post(
            f"/api/v3/milestones/{m.id}/comments",
            headers=admin_headers,
            data={"body": "Kicked off the milestone."},
            files=[("files", ("kickoff.pdf", PDF_HEADER, "application/pdf"))],
        )
        # 3) Activity comment body-only.
        client.post(
            f"/api/v3/activities/{a.id}/comments",
            headers=admin_headers,
            data={"body": "Stakeholder OK."},
        )
        # 4) Task standalone attachment (file-only, body=NULL).
        client.post(
            f"/api/v3/tasks/{t.id}/attachments",
            headers=admin_headers,
            files={"file": ("task-evidence.pdf", PDF_HEADER, "application/pdf")},
        )
        # 5) Subtask comment with body.
        client.post(
            f"/api/v3/subtasks/{s.id}/comments",
            headers=admin_headers,
            data={"body": "Subtask done."},
        )

        r = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed",
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["total"] == 5
        kinds = {e["targetKind"] for e in data["_embedded"]["elements"]}
        assert kinds == {"project", "milestone", "activity", "task", "subtask"}

    def test_target_names_resolved(
        self, client, admin_user, admin_headers, sample_project,
        db_session, temp_storage,
    ):
        m = _make_milestone(db_session, sample_project.id, name="Naming Test M")
        client.post(
            f"/api/v3/milestones/{m.id}/comments",
            headers=admin_headers,
            data={"body": "test"},
        )
        r = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed",
            headers=admin_headers,
        )
        row = r.json()["data"]["_embedded"]["elements"][0]
        assert row["targetKind"] == "milestone"
        assert row["targetName"] == "Naming Test M"
        assert row["body"] == "test"

    def test_each_row_carries_body_and_attachments_fields(
        self, client, admin_user, admin_headers, sample_project,
        db_session, temp_storage,
    ):
        # Project-level file → body=None, attachments has 1 entry.
        client.post(
            f"/api/v3/projects/{sample_project.id}/attachments",
            headers=admin_headers,
            files=[("files", ("a.pdf", PDF_HEADER, "application/pdf"))],
        )
        r = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed",
            headers=admin_headers,
        )
        row = r.json()["data"]["_embedded"]["elements"][0]
        assert (row.get("body") or "") == ""
        assert len(row["attachments"]) == 1
        assert row["attachments"][0]["filename"] == "a.pdf"

    def test_each_row_carries_created_by_login(
        self, client, admin_user, admin_headers, sample_project,
        db_session, temp_storage,
    ):
        """Each row should carry both ``createdBy`` (UUID) and
        ``createdByLogin`` (username) so the FE can render the
        author without a second /users lookup."""
        m = _make_milestone(db_session, sample_project.id, name="Author M")
        client.post(
            f"/api/v3/milestones/{m.id}/comments",
            headers=admin_headers,
            data={"body": "by admin"},
        )
        r = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed",
            headers=admin_headers,
        )
        rows = r.json()["data"]["_embedded"]["elements"]
        assert rows
        row = rows[0]
        assert row["createdBy"] == admin_user.id
        assert row["createdByLogin"] == admin_user.login


class TestDiscussionFeedFiltering:
    def test_soft_deleted_comment_excluded(
        self, client, admin_user, admin_headers, sample_project,
        db_session, temp_storage,
    ):
        m = _make_milestone(db_session, sample_project.id)
        # Create a comment, then DELETE it.
        up = client.post(
            f"/api/v3/milestones/{m.id}/comments",
            headers=admin_headers,
            data={"body": "soon to be deleted"},
        )
        cid = up.json()["data"]["id"]
        client.delete(f"/api/v3/comments/{cid}", headers=admin_headers)

        # Add another comment that stays.
        client.post(
            f"/api/v3/milestones/{m.id}/comments",
            headers=admin_headers,
            data={"body": "this one stays"},
        )

        r = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed",
            headers=admin_headers,
        )
        data = r.json()["data"]
        bodies = [e["body"] for e in data["_embedded"]["elements"]]
        assert bodies == ["this one stays"]

    def test_soft_deleted_target_excluded(
        self, client, admin_user, admin_headers, sample_project,
        db_session, temp_storage,
    ):
        """Comments tied to a soft-deleted milestone are excluded
        because the milestone-id walk filters ``deleted_at IS NULL``."""
        m = _make_milestone(db_session, sample_project.id, name="Doomed M")
        client.post(
            f"/api/v3/milestones/{m.id}/comments",
            headers=admin_headers,
            data={"body": "soon to be orphaned"},
        )
        # Soft-delete the milestone directly.
        m.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        r = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["total"] == 0


class TestDiscussionFeedOrderingAndPagination:
    def test_ordered_by_created_at_descending(
        self, client, admin_user, admin_headers, sample_project,
        db_session, temp_storage,
    ):
        """Newest-first ordering. We write three comment rows directly
        with explicit ``created_at`` values 10s apart so the test
        doesn't depend on insert-time clock resolution (the API path
        relies on ``datetime.now`` which can tie within the same
        second on fast systems)."""
        from app.infrastructure.db.models.comment import CommentModel
        m = _make_milestone(db_session, sample_project.id)
        # admin_user is required to satisfy the comments.author_user_id
        # NOT NULL constraint on the writes below.
        author_id = admin_user.id
        base = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
        for offset_secs, body in [(0, "first"), (10, "second"), (20, "third")]:
            db_session.add(CommentModel(
                id=str(uuid4()),
                target_kind="milestone",
                target_id=m.id,
                body=body,
                attachments=None,
                author_user_id=author_id,
                created_at=base.replace(second=offset_secs),
            ))
        db_session.commit()

        r = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed",
            headers=admin_headers,
        )
        elements = r.json()["data"]["_embedded"]["elements"]
        bodies = [e["body"] for e in elements]
        assert bodies == ["third", "second", "first"]
        timestamps = [e["createdAt"] for e in elements]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_pagination(
        self, client, admin_user, admin_headers, sample_project,
        db_session, temp_storage,
    ):
        m = _make_milestone(db_session, sample_project.id)
        for i in range(7):
            client.post(
                f"/api/v3/milestones/{m.id}/comments",
                headers=admin_headers,
                data={"body": f"c{i}"},
            )
        page1 = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed"
            f"?offset=1&pageSize=3",
            headers=admin_headers,
        ).json()["data"]
        page3 = client.get(
            f"/api/v3/projects/{sample_project.id}/discussion-feed"
            f"?offset=3&pageSize=3",
            headers=admin_headers,
        ).json()["data"]

        assert page1["total"] == 7
        assert len(page1["_embedded"]["elements"]) == 3
        # Last page has only the leftover row.
        assert len(page3["_embedded"]["elements"]) == 1
