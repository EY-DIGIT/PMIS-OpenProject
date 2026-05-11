"""Doc 37 part 1 — static-data master endpoints.

Coverage:
- Seed-row visibility for each catalog (when the seeder ran).
- CRUD lifecycle per catalog: create / get / patch / delete (soft) / restore.
- Built-in protections: cannot be deactivated; structural flags
  (requires_other / is_terminal) cannot be patched on built-ins.
- Member is forbidden from writes (admin-only).
- Validator integration: project create rejects an unknown category;
  activity create rejects an unknown status; milestone create rejects
  an unknown status. Falls back to in-code tuple when the catalog is
  empty (covers tests that never ran the seed).
"""
from __future__ import annotations

import pytest

from app.infrastructure.db.models.activity_status import ActivityStatusModel
from app.infrastructure.db.models.activity_type import ActivityTypeModel
from app.infrastructure.db.models.milestone_status import MilestoneStatusModel
from app.infrastructure.db.models.project_category import ProjectCategoryModel


@pytest.fixture
def seed_doc37_catalogs(db_session):
    """Seed the four doc-37 catalogs the way init_db would."""
    cat_seed = (
        ("MSAP", "MSAP", False),
        ("MSIP", "MSIP", False),
        ("BSP", "BSP", False),
        ("others", "Others", True),
    )
    for code, label, requires_other in cat_seed:
        if (
            db_session.query(ProjectCategoryModel)
            .filter(ProjectCategoryModel.code == code)
            .first()
            is None
        ):
            db_session.add(ProjectCategoryModel(
                code=code, label=label, is_builtin=True,
                requires_other=requires_other, active=True,
            ))
    for code, label in (
        ("standard", "Standard"),
        ("resource", "Resource"),
        ("transactional", "Transactional"),
    ):
        if (
            db_session.query(ActivityTypeModel)
            .filter(ActivityTypeModel.code == code)
            .first()
            is None
        ):
            db_session.add(ActivityTypeModel(
                code=code, label=label, is_builtin=True, active=True,
            ))
    for model in (MilestoneStatusModel, ActivityStatusModel):
        for code, label, is_terminal in (
            ("not_completed", "Not completed", False),
            ("completed", "Completed", True),
        ):
            if (
                db_session.query(model)
                .filter(model.code == code)
                .first()
                is None
            ):
                db_session.add(model(
                    code=code, label=label, is_builtin=True,
                    is_terminal=is_terminal, active=True,
                ))
    db_session.commit()


# ---------------------------------------------------------------------------
# Project categories
# ---------------------------------------------------------------------------

class TestProjectCategoriesCRUD:
    def test_list_returns_seeded_rows(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.get(
            "/api/v3/master/project_categories", headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        codes = {
            r["code"] for r in resp.json()["data"]["_embedded"]["elements"]
        }
        assert codes == {"MSAP", "MSIP", "BSP", "others"}

    def test_create_then_get(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.post(
            "/api/v3/master/project_categories/create",
            headers=admin_headers,
            json={
                "code": "PILOT",
                "label": "Pilot",
                "description": "Internal pilots only.",
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["code"] == "PILOT"
        assert d["isBuiltin"] is False

        resp = client.get(
            "/api/v3/master/project_categories/PILOT", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["label"] == "Pilot"

    def test_member_cannot_create(
        self, client, member_headers, seed_doc37_catalogs,
    ):
        resp = client.post(
            "/api/v3/master/project_categories/create",
            headers=member_headers,
            json={"code": "X", "label": "X"},
        )
        assert resp.status_code == 403

    def test_builtin_delete_rejected(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.delete(
            "/api/v3/master/project_categories/MSAP", headers=admin_headers,
        )
        assert resp.status_code == 403, resp.text

    def test_builtin_requires_other_patch_rejected(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.patch(
            "/api/v3/master/project_categories/others",
            headers=admin_headers,
            json={"requiresOther": False},
        )
        assert resp.status_code == 403

    def test_builtin_label_patch_succeeds(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.patch(
            "/api/v3/master/project_categories/MSAP",
            headers=admin_headers,
            json={"label": "Renamed MSAP"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["label"] == "Renamed MSAP"

    def test_soft_deactivate_then_restore(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        client.post(
            "/api/v3/master/project_categories/create",
            headers=admin_headers,
            json={"code": "PILOT", "label": "Pilot"},
        )
        resp = client.delete(
            "/api/v3/master/project_categories/PILOT", headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["active"] is False

        resp = client.post(
            "/api/v3/master/project_categories/PILOT/restore",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["active"] is True


# ---------------------------------------------------------------------------
# Activity types / milestone statuses / activity statuses
# ---------------------------------------------------------------------------

class TestActivityTypesCRUD:
    def test_seeded_rows(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.get(
            "/api/v3/master/activity_types", headers=admin_headers,
        )
        assert resp.status_code == 200
        codes = {
            r["code"] for r in resp.json()["data"]["_embedded"]["elements"]
        }
        assert codes == {"standard", "resource", "transactional"}

    def test_builtin_protected(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.delete(
            "/api/v3/master/activity_types/standard", headers=admin_headers,
        )
        assert resp.status_code == 403


class TestStatusCatalogs:
    def test_milestone_statuses_seeded(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.get(
            "/api/v3/master/milestone_statuses", headers=admin_headers,
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]["_embedded"]["elements"]
        codes = {r["code"]: r for r in rows}
        assert codes["not_completed"]["isTerminal"] is False
        assert codes["completed"]["isTerminal"] is True

    def test_activity_statuses_seeded(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.get(
            "/api/v3/master/activity_statuses", headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_builtin_is_terminal_patch_rejected(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.patch(
            "/api/v3/master/milestone_statuses/completed",
            headers=admin_headers,
            json={"isTerminal": False},
        )
        assert resp.status_code == 403

    def test_create_custom_status(
        self, client, admin_headers, seed_doc37_catalogs,
    ):
        resp = client.post(
            "/api/v3/master/milestone_statuses/create",
            headers=admin_headers,
            json={
                "code": "in_progress",
                "label": "In progress",
                "isTerminal": False,
                "description": "Work has started.",
            },
        )
        assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Doc 38: ``category`` is no longer accepted on project create — the
# project_categories master table stays in place for legacy reads but the
# create-time validator integration is gone. The two tests in this section
# previously asserted Pydantic + service-layer category validation behaviour;
# they're removed because the validation path no longer exists.
# ---------------------------------------------------------------------------
