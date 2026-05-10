"""Doc 44 round 9 — tester-feedback BE fixes.

Two BE fixes covered here:

  1. ``PATCH /vendors/{id}`` body-shape gate widened (bug #8). The
     round-8 carve-out was ``user_assignments``-only for non-
     ``vendors:manage`` callers; round 9 expands it per spec:
       - org_admin: ``email`` / ``contact_person`` / ``phone_number`` /
         ``project_ids`` / ``user_assignments`` (Contact/Email/Mobile/
         Project Mapping per spec).
       - project_admin: only ``user_assignments`` (Project Mapping →
         project members per spec).
     ``name`` / ``description`` / ``active`` still require
     ``vendors:manage`` for everyone below admin tier.

The hierarchy-read gate for bug #5 lives in user-mgmt; see
``test_doc44_round9_pa_users_read.py`` over there.
"""
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.project_vendor import ProjectVendorModel
from app.infrastructure.db.models.role import RoleModel
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.models.user_role_assignment import (
    UserRoleAssignmentModel,
)
from app.infrastructure.db.models.vendor import VendorModel


def _make_user(db, login, vendor_id=None):
    u = UserModel(
        login=f"{login}-{uuid4().hex[:6]}",
        email=f"{login}-{uuid4().hex[:6]}@example.com",
        hashed_password=hash_password("Pmis@1234"),
        first_name="T", last_name="User",
        status="active", two_factor_enabled=False,
        vendor_id=vendor_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_vendor(db, name=None):
    v = VendorModel(
        id=str(uuid4()),
        name=name or f"V-{uuid4().hex[:5]}",
        description="-", active=True,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _make_project(db, name=None, status="published"):
    p = ProjectModel(
        id=str(uuid4()),
        project_code=f"UIDAI-PR{uuid4().hex[:14].upper()}",
        name=name or f"P-{uuid4().hex[:5]}",
        description="-", active=True, public=False, status=status,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _link_vendor_project(db, vendor, project):
    db.add(ProjectVendorModel(project_id=project.id, vendor_id=vendor.id))
    db.commit()


def _grant(db, user, role_name, project_id=None, organization_id=None):
    role_id = (
        db.query(RoleModel).filter(RoleModel.name == role_name).one().id
    )
    db.add(UserRoleAssignmentModel(
        user_id=user.id, role_id=role_id,
        project_id=project_id, organization_id=organization_id,
    ))
    db.commit()


def _headers(user):
    return {
        "Authorization": "Bearer " + create_access_token({
            "sub": user.login, "user_id": user.id, "email": user.email,
        })
    }


# ---------------------------------------------------------------------------
# Bug #8 — OA can edit Contact / Email / Mobile / Project Mapping
# ---------------------------------------------------------------------------

class TestOrgAdminCanEditAllowedVendorFields:
    def test_oa_edit_contact_person(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "OA-Edit-Contact")
        oa = _make_user(db_session, "oa-contact", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"contact_person": "New Contact"},
            headers=_headers(oa),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["contactPerson"] == "New Contact"

    def test_oa_edit_email(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "OA-Edit-Email")
        oa = _make_user(db_session, "oa-email", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"email": "new@org.example"},
            headers=_headers(oa),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["email"] == "new@org.example"

    def test_oa_edit_phone_number(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "OA-Edit-Phone")
        oa = _make_user(db_session, "oa-phone", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"phone_number": "9876543210"},
            headers=_headers(oa),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["phoneNumber"] == "9876543210"

    def test_oa_edit_project_ids(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "OA-Edit-Projects")
        p1 = _make_project(db_session, "OA-edit-p1")
        p2 = _make_project(db_session, "OA-edit-p2")
        _link_vendor_project(db_session, v, p1)
        oa = _make_user(db_session, "oa-projids", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"project_ids": [p1.id, p2.id]},
            headers=_headers(oa),
        )
        assert resp.status_code == 200, resp.text
        ret_pids = {p["id"] for p in resp.json()["data"]["projects"]}
        assert {p1.id, p2.id}.issubset(ret_pids)

    def test_oa_blocked_on_name(
        self, client, admin_user, db_session,
    ):
        """name is NOT in OA's allowed list — still requires vendors:manage."""
        v = _make_vendor(db_session, "OA-NameBlock-2")
        oa = _make_user(db_session, "oa-name-2", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"name": "RenamedByOA"},
            headers=_headers(oa),
        )
        assert resp.status_code == 403, resp.text
        assert "vendors:manage" in resp.text.lower()

    def test_oa_blocked_on_active_flag(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "OA-ActiveBlock")
        oa = _make_user(db_session, "oa-active", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"active": False},
            headers=_headers(oa),
        )
        assert resp.status_code == 403, resp.text
        assert "vendors:manage" in resp.text.lower()

    def test_oa_mixed_body_excess_field_rejected(
        self, client, admin_user, db_session,
    ):
        """If the body mixes an allowed field (email) with a forbidden
        field (name) THAT DIFFERS FROM CURRENT, the whole request is
        rejected — name still requires vendors:manage."""
        v = _make_vendor(db_session, "OA-MixedBody")
        oa = _make_user(db_session, "oa-mixed", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"email": "ok@org.example", "name": "RenameAttempt"},
            headers=_headers(oa),
        )
        assert resp.status_code == 403, resp.text

    def test_oa_full_roundtrip_body_with_unchanged_name_passes(
        self, client, admin_user, db_session,
    ):
        """Doc 46 round 10b — the FE round-trips the entire vendor object
        on PATCH (typical edit-form behaviour). When the body includes
        ``name`` / ``description`` / ``active`` matching the current
        state, those fields are no-ops and must NOT trigger 403. Only
        actual mutations to forbidden fields are rejected."""
        v = _make_vendor(db_session, "OA-FullRoundtrip")
        # Anchor description to a known value so we can echo it.
        v.description = "Original description"
        v.active = True
        db_session.commit()
        db_session.refresh(v)

        oa = _make_user(db_session, "oa-roundtrip", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        # Body includes every vendor field. name/description/active
        # match current state (no-ops); contact_person / email /
        # phone_number are actual edits in OA's allowlist.
        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={
                "name": v.name,                       # no-op
                "description": v.description,        # no-op
                "active": v.active,                  # no-op
                "email": "updated@org.example",      # OA-allowed edit
                "contact_person": "Updated Person",  # OA-allowed edit
                "phone_number": "9999000099",        # OA-allowed edit
            },
            headers=_headers(oa),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["email"] == "updated@org.example"
        assert body["contactPerson"] == "Updated Person"
        # name unchanged
        assert body["name"] == v.name

    def test_pa_get_vendor_scopes_projects_and_user_assignments(
        self, client, admin_user, db_session,
    ):
        """Round 12 — when a project_admin reads their own vendor, the
        ``projects[]`` and ``user_assignments[]`` arrays are filtered
        down to the project(s) the PA is actually assigned to. The
        rest of the vendor's projects + cross-project assignments are
        hidden. Closes the tester complaint where a PA mapped to one
        project saw the full vendor view including out-of-scope
        projects + members."""
        v = _make_vendor(db_session, "PaScope")
        # Two projects in the vendor; PA only on one of them.
        p_assigned = _make_project(db_session, "pa-on", status="published")
        p_other = _make_project(db_session, "pa-off", status="published")
        for p in (p_assigned, p_other):
            _link_vendor_project(db_session, v, p)
        pa = _make_user(db_session, "pa-scope-caller", vendor_id=v.id)
        # Other-project member to make sure the user_assignments
        # response would NORMALLY surface them.
        bystander = _make_user(db_session, "pa-scope-bystander", vendor_id=v.id)
        _grant(db_session, pa, "project_admin", project_id=p_assigned.id)
        _grant(db_session, bystander, "project_admin", project_id=p_other.id)

        resp = client.get(
            f"/api/v3/vendors/{v.id}", headers=_headers(pa),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        # projects[] filtered to PA's assigned set.
        pids = {p["id"] for p in data["projects"]}
        assert pids == {p_assigned.id}, (
            f"PA saw out-of-scope projects: {pids}"
        )

        # user_assignments[] only references PA's projects.
        ua_pids = {u["project_id"] for u in data["user_assignments"]}
        assert ua_pids.issubset({p_assigned.id}), (
            f"PA saw cross-project user_assignments: {ua_pids - {p_assigned.id}}"
        )

    def test_oa_get_vendor_unaffected_by_pa_scope_filter(
        self, client, admin_user, db_session,
    ):
        """Sanity — OA still sees the full vendor view (all projects +
        all user_assignments). The round-12 PA scope only fires when
        the caller doesn't hold org_admin in this vendor."""
        v = _make_vendor(db_session, "OaUnchanged")
        p1 = _make_project(db_session, "oa-p1", status="published")
        p2 = _make_project(db_session, "oa-p2", status="published")
        for p in (p1, p2):
            _link_vendor_project(db_session, v, p)
        oa = _make_user(db_session, "oa-unchanged", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.get(f"/api/v3/vendors/{v.id}", headers=_headers(oa))
        assert resp.status_code == 200, resp.text
        pids = {p["id"] for p in resp.json()["data"]["projects"]}
        assert pids == {p1.id, p2.id}

    def test_user_assignments_always_emits_pa_pm_buckets_per_project(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Round 11d — every project owned by the vendor surfaces a
        Project Admin AND a Project Member row in user_assignments,
        even when no users hold that role yet. Closes the FE bug
        where the PA bucket visually 'disappeared' after a PATCH that
        only modified the PM row, because the response previously
        omitted empty buckets."""
        v = _make_vendor(db_session, "AlwaysEmit")
        p = _make_project(db_session, "AlwaysEmitP", status="published")
        _link_vendor_project(db_session, v, p)
        pa = _make_user(db_session, "ae-pa", vendor_id=v.id)
        _grant(db_session, pa, "project_admin", project_id=p.id)
        # PM has zero users — the bucket should still surface.

        resp = client.get(f"/api/v3/vendors/{v.id}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        ua = [
            u for u in resp.json()["data"]["user_assignments"]
            if u["project_id"] == p.id
        ]
        roles = {u["role"]: len(u["user_ids"]) for u in ua}
        assert "Project Admin" in roles
        assert "Project Member" in roles
        assert roles["Project Admin"] == 1
        assert roles["Project Member"] == 0  # empty bucket but present

    def test_user_vendor_id_set_when_newly_granted(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Round 11c — when a user is newly granted a project-tier
        role via PATCH /vendors/{id} user_assignments, their
        users.vendor_id is updated to the assigning vendor (if
        currently NULL or different). Ensures downstream vendor-
        scoped lookups (round-7 GET /users filter, Org Mgmt list)
        find the user under the right vendor."""
        v = _make_vendor(db_session, "BindV")
        p = _make_project(db_session, "BindP", status="published")
        _link_vendor_project(db_session, v, p)
        # User created with NO vendor_id — would otherwise be invisible
        # to OA's GET /users.
        u = _make_user(db_session, "bindee", vendor_id=None)
        assert u.vendor_id is None  # baseline

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={
                "user_assignments": [{
                    "project_id": p.id,
                    "role": "project_member",
                    "user_ids": [u.id],
                }],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text

        # vendor_id has been set on the user record.
        db_session.expire_all()
        refreshed = db_session.query(UserModel).filter_by(id=u.id).one()
        assert refreshed.vendor_id == v.id

    def test_user_assignments_response_includes_users_array(
        self, client, admin_user, admin_headers, db_session,
    ):
        """Doc 46 round 10c — the FE wants login + name alongside
        each user_id in the user_assignments response so it can render
        the picker without per-id /users lookups. The new ``users``
        array is parallel to ``user_ids`` (same order, same length).
        """
        v = _make_vendor(db_session, "VendorWithUsers")
        p = _make_project(db_session, "ProjForUsers", status="published")
        _link_vendor_project(db_session, v, p)
        u_a = _make_user(db_session, "ua-alpha", vendor_id=v.id)
        u_b = _make_user(db_session, "ua-beta", vendor_id=v.id)
        _grant(db_session, u_a, "project_admin", project_id=p.id)
        _grant(db_session, u_b, "project_admin", project_id=p.id)

        resp = client.get(f"/api/v3/vendors/{v.id}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        ua_rows = [
            ua for ua in resp.json()["data"]["user_assignments"]
            if ua["project_id"] == p.id and ua["role"] == "Project Admin"
        ]
        assert len(ua_rows) == 1
        row = ua_rows[0]

        # Backwards-compat: user_ids array still present.
        assert set(row["user_ids"]) == {u_a.id, u_b.id}

        # New: parallel users array with login + name + email.
        assert "users" in row
        assert len(row["users"]) == len(row["user_ids"])
        for entry, expected_id in zip(row["users"], row["user_ids"]):
            assert entry["id"] == expected_id
            assert "login" in entry
            assert "firstName" in entry
            assert "lastName" in entry
            assert "email" in entry
        # Sanity — logins match what we created.
        logins = {e["login"] for e in row["users"]}
        assert logins == {u_a.login, u_b.login}

    def test_oa_full_roundtrip_with_changed_name_still_rejected(
        self, client, admin_user, db_session,
    ):
        """Sanity — the no-op tolerance only fires when the value
        equals current. A genuine name change still 403s."""
        v = _make_vendor(db_session, "OA-FullRoundtripChange")
        oa = _make_user(db_session, "oa-roundtrip-2", vendor_id=v.id)
        _grant(db_session, oa, "org_admin", organization_id=v.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={
                "name": "DifferentName",  # genuine change
                "email": "ok@org.example",
            },
            headers=_headers(oa),
        )
        assert resp.status_code == 403, resp.text
        assert "name" in resp.text.lower()


# ---------------------------------------------------------------------------
# Bug #8/#13 — PA can edit ONLY user_assignments
# ---------------------------------------------------------------------------

class TestProjectAdminLimitedToUserAssignments:
    def test_pa_can_edit_user_assignments(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "PA-UA-Allow")
        p = _make_project(db_session, "PA-UA-proj")
        _link_vendor_project(db_session, v, p)
        pa = _make_user(db_session, "pa-ua", vendor_id=v.id)
        _grant(db_session, pa, "project_admin", project_id=p.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"user_assignments": []},
            headers=_headers(pa),
        )
        assert resp.status_code == 200, resp.text

    def test_pa_blocked_on_email(
        self, client, admin_user, db_session,
    ):
        v = _make_vendor(db_session, "PA-EmailBlock")
        p = _make_project(db_session, "PA-block-proj")
        _link_vendor_project(db_session, v, p)
        pa = _make_user(db_session, "pa-email", vendor_id=v.id)
        _grant(db_session, pa, "project_admin", project_id=p.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"email": "pa@example.com"},
            headers=_headers(pa),
        )
        assert resp.status_code == 403, resp.text

    def test_pa_blocked_on_project_ids(
        self, client, admin_user, db_session,
    ):
        """project_ids is OA-allowed but NOT PA-allowed — only the
        user_assignments matrix is in PA's surface."""
        v = _make_vendor(db_session, "PA-PidsBlock")
        p = _make_project(db_session, "PA-pids-proj")
        _link_vendor_project(db_session, v, p)
        pa = _make_user(db_session, "pa-pids", vendor_id=v.id)
        _grant(db_session, pa, "project_admin", project_id=p.id)

        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"project_ids": [p.id]},
            headers=_headers(pa),
        )
        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Sanity — admin tier still has no field restrictions
# ---------------------------------------------------------------------------

class TestAdminFullPatchUnchanged:
    def test_admin_can_edit_name(
        self, client, admin_headers, db_session,
    ):
        v = _make_vendor(db_session, "Admin-FullPatch-2")
        resp = client.patch(
            f"/api/v3/vendors/{v.id}",
            json={"name": "Renamed", "active": False},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["name"] == "Renamed"
