"""Tests for the project hierarchy: Milestone -> Activity -> Task (unlimited nesting)."""
import pytest
from datetime import datetime, timedelta, timezone


def _future(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _future_dt(days=30):
    return datetime.now(timezone.utc) + timedelta(days=days)


class TestMilestoneCreation:
    """Milestones are top-level work packages (no parent) with required dates."""

    def test_create_milestone_with_dates(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Phase 1",
            "startDate": _future(10),
            "endDate": _future(90),
        }, headers=admin_headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["subject"] == "Phase 1"
        assert data["startDate"] is not None
        assert data["endDate"] is not None

    def test_milestone_requires_dates(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        """Top-level WP without dates should fail (milestone needs dates)."""
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "No Dates Milestone",
        }, headers=admin_headers)
        assert resp.status_code == 400, resp.text

    def test_milestone_end_before_start_rejected(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Bad Dates",
            "startDate": _future(90),
            "endDate": _future(10),
        }, headers=admin_headers)
        assert resp.status_code in [400, 422], resp.text

    def test_wrong_type_at_depth_0_rejected(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        """Explicitly passing a 'task' type for a top-level WP should fail."""
        task_type = next(t for t in builtin_wp_types if t.internal_name == "task")
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Should fail",
            "typeId": task_type.id,
            "startDate": _future(10),
            "endDate": _future(90),
        }, headers=admin_headers)
        assert resp.status_code == 400, resp.text
        assert "milestone" in resp.json()["error"]["message"].lower()


class TestActivityCreation:
    """Activities are children of milestones, also with required dates."""

    def _create_milestone(self, client, project_uuid, headers):
        resp = client.post(f"/api/v3/projects/{project_uuid}/work_packages/create", json={
            "subject": "Milestone",
            "startDate": _future(10),
            "endDate": _future(90),
        }, headers=headers)
        assert resp.status_code == 201
        return resp.json()["data"]["id"]

    def test_create_activity_under_milestone(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        ms_id = self._create_milestone(client, sample_project.id, admin_headers)
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Design Phase",
            "parentId": ms_id,
            "startDate": _future(15),
            "endDate": _future(60),
        }, headers=admin_headers)
        assert resp.status_code == 201, resp.text

    def test_activity_requires_dates(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        ms_id = self._create_milestone(client, sample_project.id, admin_headers)
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "No Date Activity",
            "parentId": ms_id,
        }, headers=admin_headers)
        assert resp.status_code == 400, resp.text

    def test_activity_dates_must_fit_in_milestone(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        ms_id = self._create_milestone(client, sample_project.id, admin_headers)
        # Activity end_date exceeds milestone end_date
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Out of range",
            "parentId": ms_id,
            "startDate": _future(15),
            "endDate": _future(120),  # beyond milestone's 90-day end
        }, headers=admin_headers)
        assert resp.status_code == 400, resp.text
        assert "parent" in resp.json()["error"]["message"].lower()


class TestTaskCreation:
    """Tasks are children of activities or other tasks, unlimited nesting."""

    def _create_milestone_and_activity(self, client, project_uuid, headers):
        ms = client.post(f"/api/v3/projects/{project_uuid}/work_packages/create", json={
            "subject": "Milestone",
            "startDate": _future(10),
            "endDate": _future(90),
        }, headers=headers)
        ms_id = ms.json()["data"]["id"]

        act = client.post(f"/api/v3/projects/{project_uuid}/work_packages/create", json={
            "subject": "Activity",
            "parentId": ms_id,
            "startDate": _future(15),
            "endDate": _future(60),
        }, headers=headers)
        act_id = act.json()["data"]["id"]
        return ms_id, act_id

    def test_create_task_under_activity(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        _, act_id = self._create_milestone_and_activity(client, sample_project.id, admin_headers)
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Task 1",
            "parentId": act_id,
        }, headers=admin_headers)
        assert resp.status_code == 201, resp.text

    def test_task_does_not_require_dates(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        _, act_id = self._create_milestone_and_activity(client, sample_project.id, admin_headers)
        resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Task no dates",
            "parentId": act_id,
        }, headers=admin_headers)
        assert resp.status_code == 201

    def test_nested_tasks_unlimited(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        """Create 4 levels of nested tasks under an activity."""
        _, act_id = self._create_milestone_and_activity(client, sample_project.id, admin_headers)
        parent_id = act_id
        for i in range(4):
            resp = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
                "subject": f"Nested Task Level {i+1}",
                "parentId": parent_id,
            }, headers=admin_headers)
            assert resp.status_code == 201, f"Failed at level {i+1}: {resp.text}"
            parent_id = resp.json()["data"]["id"]


class TestChildrenEndpoint:
    """GET /work_packages/{id}/children returns nested tree."""

    def test_get_children_tree(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        # Build: Milestone -> Activity -> Task -> SubTask
        ms = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "MS", "startDate": _future(10), "endDate": _future(90),
        }, headers=admin_headers)
        ms_id = ms.json()["data"]["id"]

        act = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "ACT", "parentId": ms_id,
            "startDate": _future(15), "endDate": _future(60),
        }, headers=admin_headers)
        act_id = act.json()["data"]["id"]

        t1 = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Task1", "parentId": act_id,
        }, headers=admin_headers)
        t1_id = t1.json()["data"]["id"]

        client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "SubTask1", "parentId": t1_id,
        }, headers=admin_headers)

        # Get tree from milestone
        resp = client.get(f"/api/v3/work_packages/{ms_id}/children", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        tree = resp.json()["data"]
        assert tree["subject"] == "MS"
        assert len(tree["_embedded"]["children"]) == 1  # Activity

        activity_node = tree["_embedded"]["children"][0]
        assert activity_node["subject"] == "ACT"
        assert len(activity_node["_embedded"]["children"]) == 1  # Task1

        task_node = activity_node["_embedded"]["children"][0]
        assert task_node["subject"] == "Task1"
        assert len(task_node["_embedded"]["children"]) == 1  # SubTask1

        subtask_node = task_node["_embedded"]["children"][0]
        assert subtask_node["subject"] == "SubTask1"
        assert len(subtask_node["_embedded"]["children"]) == 0

    def test_get_children_empty(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        """A leaf node has no children."""
        ms = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "Leaf", "startDate": _future(10), "endDate": _future(90),
        }, headers=admin_headers)
        ms_id = ms.json()["data"]["id"]

        resp = client.get(f"/api/v3/work_packages/{ms_id}/children", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["_embedded"]["children"] == []

    def test_get_children_nonexistent(self, client, admin_user, admin_headers):
        resp = client.get("/api/v3/work_packages/99999/children", headers=admin_headers)
        assert resp.status_code == 404


class TestTypeFilter:
    """List endpoint with type filter."""

    def test_filter_milestones_only(self, client, admin_user, admin_headers, sample_project, builtin_wp_types):
        # Create milestone + activity
        ms = client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "MS Filter Test", "startDate": _future(10), "endDate": _future(90),
        }, headers=admin_headers)
        ms_id = ms.json()["data"]["id"]

        client.post(f"/api/v3/projects/{sample_project.id}/work_packages/create", json={
            "subject": "ACT Filter Test", "parentId": ms_id,
            "startDate": _future(15), "endDate": _future(60),
        }, headers=admin_headers)

        # Filter by milestone
        resp = client.get(
            f"/api/v3/projects/{sample_project.id}/work_packages?type=milestone",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        elements = resp.json()["data"]["_embedded"]["elements"]
        for el in elements:
            # All returned items should have milestone type
            assert el["subject"].startswith("MS")
