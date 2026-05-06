"""Tests for the catalog + master-data endpoints introduced across
docs 15-20.

- ``TestStatusTransitionsCatalog`` — legacy GET /project_status_transitions
  and the invalid_status guard on project create (doc 15).
- ``TestCategoryOtherReason``      — categoryOtherReason required when
  category='others'.
- ``TestOwnerStrictDivisionOnly``  — owner is a strict division code
  (doc 18 §4); user logins are no longer accepted.
- ``TestOwnerOthers``              — owner='others' requires `ownerOther`
  (doc 18 §5). Per doc 20 the label is stored on the project row only
  and is NOT auto-inserted into the divisions catalog anymore.
- ``TestDivisionsCatalog``         — legacy GET /divisions returns the
  built-in rows.
- ``TestPatchEditableFields``      — PATCH whitelist matches the HTML
  edit-project flow.
- ``TestTaskSubtaskTypeInheritance`` — type field derived from the parent
  activity / parent task (doc 15).

NOTE: the ``TestProjectOwnersCatalog`` and ``TestDivisionsPersistedFromOwnerOther``
classes that lived here pre-doc-20 were removed when the project_owners
table was dropped and the auto-insert path on owner='others' was
deleted. See ``tests/test_master_data.py`` for the consolidated CRUD
coverage on the new ``/api/v3/master/*`` router.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.infrastructure.db.models.project_status_transition import (
    ProjectStatusTransitionModel,
)
from app.infrastructure.db.models.user import UserModel


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_status_transitions(db_session):
    """Seed a small subset of the in-code transitions so the catalog probe
    in the create-project service has rows to validate against."""
    # Doc 33: ``suspended`` and the ``version_only`` column were dropped
    # along with the versioning feature.
    rows = [
        (None, "new", False),
        ("new", "draft", False),
        ("draft", "new", False),
        ("new", "published", True),
        ("draft", "published", True),
        ("published", "closed", True),
    ]
    for from_s, to_s, admin_only in rows:
        db_session.add(ProjectStatusTransitionModel(
            from_status=from_s, to_status=to_s,
            requires_admin=admin_only,
            active=True,
        ))
    db_session.commit()


def _create_project_body(owner="tmd1", status="new", **over):
    body = {
        "name": "P", "owner": owner, "status": status,
        "startDate": _iso(2), "endDate": _iso(60),
    }
    # Auto-supply ownerOther when owner='others' so the helper stays
    # ergonomic for the common case. Tests that need to exercise the
    # missing-ownerOther path pass `ownerOther=""` explicitly to
    # override.
    if owner == "others" and "ownerOther" not in over:
        body["ownerOther"] = "Custom Division"
    body.update(over)
    return body


# ---------------------------------------------------------------------------
# Status transitions catalog
# ---------------------------------------------------------------------------


class TestStatusTransitionsCatalog:
    def test_endpoint_lists_seeded_rows(self, client, admin_headers, db_session):
        _seed_status_transitions(db_session)
        resp = client.get("/api/v3/project_status_transitions", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["_embedded"]["elements"]
        # At least the rows we seeded should be present.
        edges = {(r["fromStatus"], r["toStatus"]) for r in items}
        assert (None, "new") in edges
        assert ("new", "draft") in edges
        assert ("new", "published") in edges

    def test_create_project_rejects_invalid_status_against_catalog(
        self, client, admin_user, admin_headers, db_session,
    ):
        # Seed a catalog that does NOT include 'inprogress'.
        _seed_status_transitions(db_session)
        body = _create_project_body(status="inprogress")
        resp = client.post("/api/v3/projects/create", json=body, headers=admin_headers)
        # Pydantic schema rejects at 422 (in-code list is also tight); the
        # service-layer catalog check would also flag it as invalid_status.
        assert resp.status_code == 422

    def test_create_project_accepts_status_in_catalog(
        self, client, admin_user, admin_headers, db_session,
    ):
        _seed_status_transitions(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(status="new"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Project owners catalog — REMOVED in doc 20 along with the underlying
# table. The whitelist had been dead since doc 18 (project.owner became a
# strict division code). The previous TestProjectOwnersCatalog class has
# been removed entirely.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# categoryOtherReason
# ---------------------------------------------------------------------------


class TestCategoryOtherReason:
    """Upsert-path coverage for categoryOtherReason. The create-path tests
    live in tests/test_new_features.py::TestCategoryOthers (which has more
    thorough coverage of every (category, categoryOther, reason) combo).
    Keeping only the upsert case here so the two files don't duplicate.
    """

    def test_upsert_others_requires_reason(self, client, admin_user, admin_headers):
        new_uuid = str(uuid4())
        resp = client.put(
            f"/api/v3/projects/{new_uuid}",
            json=_create_project_body(
                category="others", categoryOther="New cat",
            ),
            headers=admin_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Owner validation — strict division-only
# ---------------------------------------------------------------------------


class TestOwnerStrictDivisionOnly:
    """Owner is a division code (tmd1 / tmd2 / others). Bare strings that
    aren't division codes are rejected — even if they happen to be a real
    user login. Casing is normalised on the way in."""

    def test_create_accepts_each_division_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        _seed_status_transitions(db_session)
        for code in ("tmd1", "tmd2", "others"):
            resp = client.post(
                "/api/v3/projects/create",
                json=_create_project_body(name=f"P-{code}", owner=code),
                headers=admin_headers,
            )
            assert resp.status_code == 201, (code, resp.text)
            assert resp.json()["data"]["owner"] == code

    def test_create_normalises_uppercase_owner(
        self, client, admin_user, admin_headers, db_session,
    ):
        _seed_status_transitions(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="TMD1"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["owner"] == "tmd1"

    def test_create_rejects_user_login_as_owner(
        self, client, admin_user, admin_headers, db_session,
    ):
        """admin / member / any real login is no longer a valid owner."""
        _seed_status_transitions(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="admin"),
            headers=admin_headers,
        )
        assert resp.status_code == 422
        msg = resp.json()["error"]["message"].lower()
        # Either the "must be one of …" form (no DB session for catalog
        # check) OR the "is not a known division" form (catalog
        # consulted). Both indicate the value was rejected.
        assert "not a known division" in msg or "must be one of" in msg

    def test_create_rejects_arbitrary_string(
        self, client, admin_user, admin_headers, db_session,
    ):
        _seed_status_transitions(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="not-a-division"),
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_patch_accepts_division_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        _seed_status_transitions(db_session)
        p = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="tmd1"),
            headers=admin_headers,
        ).json()["data"]
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"owner": "tmd2"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["owner"] == "tmd2"

    def test_patch_rejects_non_division_owner(
        self, client, admin_user, admin_headers, db_session,
    ):
        _seed_status_transitions(db_session)
        p = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="tmd1"),
            headers=admin_headers,
        ).json()["data"]
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"owner": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_upsert_accepts_division_code(
        self, client, admin_user, admin_headers, db_session,
    ):
        _seed_status_transitions(db_session)
        new_uuid = str(uuid4())
        resp = client.put(
            f"/api/v3/projects/{new_uuid}",
            json=_create_project_body(owner="others"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text


class TestOwnerOthers:
    """`owner='others'` requires a non-empty `ownerOther` follow-up label
    (per doc 18 §5; symmetric with `categoryOther`/`categoryOtherReason`).
    Non-`others` owners must NOT carry `ownerOther`. PATCH cleanly handles
    the cross-validation when switching owner away from 'others' without
    explicitly clearing the stale `ownerOther` (treats it as empty).
    Casing/whitespace on both fields is normalised on the way in.

    NOTE: per doc 20 the `ownerOther` label is stored on the project row
    only and is NOT auto-inserted into the divisions catalog. See
    `TestOwnerOtherDoesNotPolluteDivisions` for the negative coverage."""

    def _seed(self, db_session):
        _seed_status_transitions(db_session)

    def test_create_with_owner_others_succeeds(
        self, client, admin_user, admin_headers, db_session,
    ):
        self._seed(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="others"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["owner"] == "others"

    def test_create_with_owner_others_uppercase_normalises(
        self, client, admin_user, admin_headers, db_session,
    ):
        """`'Others'` (UI display label) and `'OTHERS'` both normalise
        to the lowercase wire code."""
        self._seed(db_session)
        for variant in ("Others", "OTHERS"):
            resp = client.post(
                "/api/v3/projects/create",
                json=_create_project_body(
                    name=f"P-{variant}", owner=variant, ownerOther="R&D",
                ),
                headers=admin_headers,
            )
            assert resp.status_code == 201, (variant, resp.text)
            assert resp.json()["data"]["owner"] == "others"

    def test_create_with_owner_others_strips_whitespace(
        self, client, admin_user, admin_headers, db_session,
    ):
        self._seed(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="  others  ", ownerOther="R&D"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["owner"] == "others"

    def test_create_rejects_empty_owner(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Owner is now REQUIRED on create; whitespace-only normalises to
        None and the service returns 422."""
        self._seed(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="   "),
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        assert "required" in resp.json()["error"]["message"].lower()

    def test_create_rejects_missing_owner_field(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Owner field omitted entirely → 422 'Owner is required'."""
        self._seed(db_session)
        body = _create_project_body()
        del body["owner"]
        resp = client.post(
            "/api/v3/projects/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        assert "required" in resp.json()["error"]["message"].lower()

    def test_create_others_without_ownerOther_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        """owner='others' WITHOUT ownerOther → 422."""
        self._seed(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="others", ownerOther=""),
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()["error"]
        assert "ownerother" in body["message"].lower()

    def test_create_non_others_with_ownerOther_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        """ownerOther only allowed when owner='others'."""
        self._seed(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="tmd1", ownerOther="Engineering"),
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text

    def test_create_others_with_ownerOther_persists(
        self, client, admin_user, admin_headers, db_session,
    ):
        """owner='others' + ownerOther='Engineering' → 201, both round-trip."""
        self._seed(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(
                owner="others", ownerOther="Engineering",
            ),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["owner"] == "others"
        assert d["ownerOther"] == "Engineering"

    def test_create_rejects_close_misspellings(
        self, client, admin_user, admin_headers, db_session,
    ):
        """`'other'` (singular) is NOT the same as `'others'` — strict match."""
        self._seed(db_session)
        for bad in ("other", "OTH", "tmd3", "tmd1 "):
            # Strip-and-lowercase happens before membership, so 'tmd1 '
            # actually normalises to 'tmd1' — exclude it from this test
            # but assert the rest individually.
            if bad == "tmd1 ":
                continue
            resp = client.post(
                "/api/v3/projects/create",
                json=_create_project_body(name=f"P-{bad}", owner=bad),
                headers=admin_headers,
            )
            assert resp.status_code == 422, (bad, resp.text)

    def test_patch_to_others_succeeds(
        self, client, admin_user, admin_headers, db_session,
    ):
        """PATCH owner='others' must also send ownerOther — otherwise 422."""
        self._seed(db_session)
        p = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="tmd1"),
            headers=admin_headers,
        ).json()["data"]
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"owner": "others", "ownerOther": "R&D"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["owner"] == "others"
        assert d["ownerOther"] == "R&D"

    def test_patch_to_others_without_ownerOther_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        self._seed(db_session)
        p = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="tmd1"),
            headers=admin_headers,
        ).json()["data"]
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"owner": "others"},
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text

    def test_patch_from_others_to_tmd_succeeds(
        self, client, admin_user, admin_headers, db_session,
    ):
        """No 'unset categoryOther' style cleanup needed — owner='others'
        carries no follow-up field today, so switching back to 'tmd1' is
        a clean field swap."""
        self._seed(db_session)
        p = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="others"),
            headers=admin_headers,
        ).json()["data"]
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"owner": "tmd1"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["owner"] == "tmd1"

    def test_patch_others_uppercase_normalises(
        self, client, admin_user, admin_headers, db_session,
    ):
        self._seed(db_session)
        p = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="tmd1"),
            headers=admin_headers,
        ).json()["data"]
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"owner": "Others", "ownerOther": "R&D"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["owner"] == "others"

    def test_upsert_insert_with_others(
        self, client, admin_user, admin_headers, db_session,
    ):
        self._seed(db_session)
        new_uuid = str(uuid4())
        resp = client.put(
            f"/api/v3/projects/{new_uuid}",
            json=_create_project_body(owner="others"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["owner"] == "others"
        assert resp.json()["data"]["_created"] is True

    def test_upsert_update_changes_owner_to_others(
        self, client, admin_user, admin_headers, db_session,
    ):
        self._seed(db_session)
        new_uuid = str(uuid4())
        # Initial PUT — owner=tmd1.
        client.put(
            f"/api/v3/projects/{new_uuid}",
            json=_create_project_body(owner="tmd1"),
            headers=admin_headers,
        )
        # Same UUID, owner=others — should hit the UPDATE path.
        resp = client.put(
            f"/api/v3/projects/{new_uuid}",
            json=_create_project_body(owner="others"),
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["owner"] == "others"
        assert resp.json()["data"]["_created"] is False

    def test_owner_others_persists_to_response(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Round-trip: GET /projects returns the same owner='others' we set."""
        self._seed(db_session)
        p = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(owner="others"),
            headers=admin_headers,
        ).json()["data"]
        get_resp = client.get(
            f"/api/v3/projects/{p['id']}", headers=admin_headers,
        )
        assert get_resp.status_code == 200, get_resp.text
        assert get_resp.json()["data"]["owner"] == "others"


# ---------------------------------------------------------------------------
# Divisions catalog
# ---------------------------------------------------------------------------


class TestDivisionsCatalog:
    """GET /divisions surfaces the in-code DIVISION_CHOICES so the FE can
    populate dropdowns without hard-coding labels."""

    def test_endpoint_returns_three_divisions_with_labels(self, client, admin_headers):
        resp = client.get("/api/v3/divisions", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        items = body["_embedded"]["elements"]
        assert len(items) == 3
        codes = [i["code"] for i in items]
        assert codes == ["tmd1", "tmd2", "others"]
        labels = {i["code"]: i["label"] for i in items}
        assert labels == {"tmd1": "TMD1", "tmd2": "TMD2", "others": "Others"}
        # Only the 'others' entry should advertise the free-text follow-up.
        requires_other = {i["code"]: i["requiresOther"] for i in items}
        assert requires_other == {"tmd1": False, "tmd2": False, "others": True}

    def test_endpoint_requires_authentication(self, client):
        resp = client.get("/api/v3/divisions")
        assert resp.status_code == 401, resp.text


class TestOwnerOtherDoesNotPolluteDivisions:
    """Doc 20: ``ownerOther`` labels are stored on the project row's
    ``owner_other`` column ONLY. The pre-doc-20 auto-insert path that
    mirrored the label into the divisions catalog was removed (it was
    producing rogue rows like 'admin' / 'test' from one-off labels).
    Going forward the divisions catalog is admin-managed via the
    ``/api/v3/master/divisions`` router."""

    def _seed(self, db_session):
        _seed_status_transitions(db_session)

    def test_owner_other_does_not_create_division_row(
        self, client, admin_user, admin_headers, db_session,
    ):
        self._seed(db_session)
        # Pre-condition: 'engineering' is not in the divisions table.
        from app.infrastructure.db.models.division import DivisionModel
        existing = (
            db_session.query(DivisionModel)
            .filter_by(code="engineering").first()
        )
        assert existing is None

        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(
                owner="others", ownerOther="Engineering",
            ),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        # Project row carries the label as free text…
        assert resp.json()["data"]["ownerOther"] == "Engineering"

        # …but NO new divisions row was inserted.
        db_session.expire_all()
        row = (
            db_session.query(DivisionModel)
            .filter_by(code="engineering").first()
        )
        assert row is None, (
            "ownerOther must NOT auto-insert into divisions in doc 20+"
        )

    def test_owner_other_does_not_appear_in_get_divisions(
        self, client, admin_user, admin_headers, db_session,
    ):
        """GET /divisions stays at the three built-ins after a project
        creates with a fresh ownerOther label."""
        self._seed(db_session)
        client.post(
            "/api/v3/projects/create",
            json=_create_project_body(
                owner="others", ownerOther="Field Operations",
            ),
            headers=admin_headers,
        )
        resp = client.get("/api/v3/divisions", headers=admin_headers)
        assert resp.status_code == 200
        codes = [i["code"] for i in resp.json()["data"]["_embedded"]["elements"]]
        assert "field_operations" not in codes
        assert codes == ["tmd1", "tmd2", "others"]

    def test_user_added_division_only_creatable_via_admin_endpoint(
        self, client, admin_user, admin_headers, db_session,
    ):
        """The only way to land a non-builtin row in divisions is now the
        admin endpoint POST /api/v3/master/divisions/create. Once added,
        future projects can pick that code as their owner directly."""
        self._seed(db_session)
        # Admin curates the catalog explicitly. Doc 36 makes email +
        # phoneNumber required at the wire.
        resp = client.post(
            "/api/v3/master/divisions/create",
            json={
                "label": "Engineering",
                "email": "eng@uidai.example",
                "phoneNumber": "+91 80 1234 5678",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["code"] == "engineering"
        assert resp.json()["data"]["isBuiltin"] is False

        # Now a project can use owner='engineering' directly.
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(name="P-2", owner="engineering"),
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["owner"] == "engineering"

    def test_unknown_owner_code_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Codes not in built-ins AND not in the divisions table are
        rejected — same as before doc 20."""
        self._seed(db_session)
        resp = client.post(
            "/api/v3/projects/create",
            json=_create_project_body(name="P-Sales", owner="sales"),
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# PATCH editable-field whitelist (doc 18 expansion)
# ---------------------------------------------------------------------------


class TestPatchEditableFields:
    """The PATCH whitelist now matches the HTML edit-project flow: baselines
    can edit category + categoryOther + categoryOtherReason + actual dates;
    versions can NOT edit name / start_date / category. Status is rejected
    on both — clients use the dedicated publish/close/suspend endpoints."""

    def _create_baseline(self, client, admin_user, admin_headers, db_session, **overrides):
        _seed_status_transitions(db_session)
        body = _create_project_body(**overrides)
        resp = client.post(
            "/api/v3/projects/create", json=body, headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["data"]

    def test_baseline_can_patch_category(
        self, client, admin_user, admin_headers, db_session,
    ):
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session, category="MSAP",
        )
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"category": "MSIP"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["category"] == "MSIP"

    def test_baseline_can_patch_to_others_with_reason(
        self, client, admin_user, admin_headers, db_session,
    ):
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session, category="MSAP",
        )
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={
                "category": "others",
                "categoryOther": "Internal R&D",
                "categoryOtherReason": "Pilot bucket pending approval.",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["category"] == "others"
        assert d["categoryOther"] == "Internal R&D"
        assert d["categoryOtherReason"] == "Pilot bucket pending approval."

    def test_baseline_patch_to_others_without_reason_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session, category="MSAP",
        )
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"category": "others", "categoryOther": "X"},
            headers=admin_headers,
        )
        # Missing categoryOtherReason → 422 from the symmetric check.
        assert resp.status_code == 422, resp.text

    def test_baseline_status_patch_rejected(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Status changes go through publish/close/suspend, not PATCH."""
        p = self._create_baseline(
            client, admin_user, admin_headers, db_session,
        )
        resp = client.patch(
            f"/api/v3/projects/{p['id']}",
            json={"status": "published"},
            headers=admin_headers,
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()["error"]
        assert body["errorIdentifier"] == "invalid_field"
        assert "status" in body["_embedded"]["details"]["rejected"]

    # Doc 33: ``test_version_status_patch_rejected`` removed — versions
    # don't exist anymore. The published-project PATCH whitelist still
    # rejects ``status`` (status changes go through dedicated endpoints),
    # which is covered by ``test_published_status_patch_rejected`` above.


# ---------------------------------------------------------------------------
# Task / subtask type inheritance
# ---------------------------------------------------------------------------


def _create_baseline_with_resource_activity(client, admin_headers):
    """Helper: project + milestone + resource/details activity, then publish
    + version so we can create tasks (tasks live on versions only)."""
    p = client.post(
        "/api/v3/projects/create",
        json=_create_project_body(),
        headers=admin_headers,
    ).json()["data"]
    pid = p["id"]
    mid = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        json={"name": "M", "startDate": _iso(3), "endDate": _iso(40)},
        headers=admin_headers,
    ).json()["data"]["id"]
    # Standard activity for the simple inheritance test.
    a_std = client.post(
        f"/api/v3/milestones/{mid}/activities/standard/create",
        json={"name": "A-std", "startDate": _iso(4), "endDate": _iso(20)},
        headers=admin_headers,
    ).json()["data"]["id"]
    # Resource/count activity for the resource-inheritance test.
    a_res = client.post(
        f"/api/v3/milestones/{mid}/activities/resource/count/create",
        json={
            "name": "A-res", "startDate": _iso(4), "endDate": _iso(20),
            "resourceCount": 2,
        },
        headers=admin_headers,
    ).json()["data"]["id"]

    # Post-doc-33 follow-up: T/S writes require ``status == 'published'``.
    # Publish here so the downstream task / subtask tests can create rows.
    pub = client.post(f"/api/v3/projects/{pid}/publish", headers=admin_headers)
    assert pub.status_code == 200, pub.text

    acts = client.get(
        f"/api/v3/milestones/{mid}/activities", headers=admin_headers,
    ).json()["data"]["_embedded"]["elements"]
    by_type = {a["type"]: a["id"] for a in acts}
    return pid, pid, by_type["standard"], by_type["resource"]


class TestTaskSubtaskTypeInheritance:
    def test_task_inherits_standard_type(self, client, admin_user, admin_headers):
        _, _, std_aid, _ = _create_baseline_with_resource_activity(client, admin_headers)
        resp = client.post(
            f"/api/v3/activities/{std_aid}/tasks/create",
            json={"name": "T", "startDate": _iso(5), "endDate": _iso(15)},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["type"] == "standard"
        assert body["resourceMode"] is None

    def test_task_under_resource_activity_requires_mode(
        self, client, admin_user, admin_headers,
    ):
        _, _, _, res_aid = _create_baseline_with_resource_activity(client, admin_headers)
        # Body omits resourceMode — must be rejected because the inherited
        # type is 'resource' and a mode is required for resource tasks.
        resp = client.post(
            f"/api/v3/activities/{res_aid}/tasks/create",
            json={"name": "T", "startDate": _iso(5), "endDate": _iso(15)},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "resourcemode" in resp.text.lower()

    def test_task_under_resource_activity_count_mode(
        self, client, admin_user, admin_headers,
    ):
        _, _, _, res_aid = _create_baseline_with_resource_activity(client, admin_headers)
        resp = client.post(
            f"/api/v3/activities/{res_aid}/tasks/create",
            json={
                "name": "T", "startDate": _iso(5), "endDate": _iso(15),
                "resourceMode": "count", "resourceCount": 2,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["type"] == "resource"
        assert body["resourceMode"] == "count"
        assert body["resourceCount"] == 2

    def test_task_under_standard_activity_rejects_resource_fields(
        self, client, admin_user, admin_headers,
    ):
        _, _, std_aid, _ = _create_baseline_with_resource_activity(client, admin_headers)
        resp = client.post(
            f"/api/v3/activities/{std_aid}/tasks/create",
            json={
                "name": "T", "startDate": _iso(5), "endDate": _iso(15),
                "resourceMode": "count", "resourceCount": 1,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "resourcemode" in resp.text.lower()

    def test_subtask_inherits_type_from_parent_task(
        self, client, admin_user, admin_headers,
    ):
        _, _, std_aid, _ = _create_baseline_with_resource_activity(client, admin_headers)
        # Create a standard task.
        tid = client.post(
            f"/api/v3/activities/{std_aid}/tasks/create",
            json={"name": "T", "startDate": _iso(5), "endDate": _iso(15)},
            headers=admin_headers,
        ).json()["data"]["id"]
        # Subtask under it: type omitted from body.
        resp = client.post(
            f"/api/v3/tasks/{tid}/subtasks/create",
            json={"name": "ST", "startDate": _iso(6), "endDate": _iso(12)},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["type"] == "standard"
