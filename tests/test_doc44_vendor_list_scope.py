"""Doc 44 round 4 — GET /api/v3/vendors filtered by caller scope.

  - admin / super_admin → see every live vendor (full access)
  - everyone else      → see only the single vendor they belong to
                         (users.vendor_id), or empty list when not
                         mapped to a vendor

The same logic powers GET /api/v3/master/vendors via the delegate.
"""
from uuid import uuid4

from app.infrastructure.db.models.user_permission import UserPermissionModel
from app.infrastructure.db.models.vendor import VendorModel


def _make_vendor(db_session, name=None):
    v = VendorModel(
        id=str(uuid4()),
        name=name or f"Vendor-{uuid4().hex[:6]}",
        description="-",
        active=True,
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    return v


def _ids(resp_json):
    return {e["id"] for e in resp_json["data"]["_embedded"]["elements"]}


def _grant_vendors_read(db_session, user_id):
    """The default member_user fixture doesn't include vendors:read or
    master_data:view in its direct permission grants. The filter we're
    testing only kicks in once the route's permission gate passes —
    grant the read codes here so we exercise the scope logic, not the
    require_permission gate."""
    for code in ("vendors:read", "master_data:view"):
        existing = (
            db_session.query(UserPermissionModel)
            .filter(
                UserPermissionModel.user_id == user_id,
                UserPermissionModel.permission_code == code,
            ).first()
        )
        if existing is None:
            db_session.add(UserPermissionModel(
                user_id=user_id, permission_code=code,
            ))
    db_session.commit()


class TestVendorListScope:
    def test_admin_sees_every_vendor(
        self, client, admin_user, admin_headers, db_session,
    ):
        v1 = _make_vendor(db_session)
        v2 = _make_vendor(db_session)
        resp = client.get("/api/v3/vendors", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        ids = _ids(resp.json())
        assert v1.id in ids and v2.id in ids

    def test_member_sees_only_their_vendor(
        self, client, admin_user, admin_headers, member_user, member_headers,
        db_session,
    ):
        _grant_vendors_read(db_session, member_user.id)
        # Two vendors: one we'll attach to member_user, one we won't.
        attached = _make_vendor(db_session, name="Member-Vendor")
        other = _make_vendor(db_session, name="Other-Vendor")
        # Wire member_user to `attached`.
        member_user.vendor_id = attached.id
        db_session.commit()

        resp = client.get("/api/v3/vendors", headers=member_headers)
        assert resp.status_code == 200, resp.text
        ids = _ids(resp.json())
        assert ids == {attached.id}, (
            f"member should only see their own vendor; got {ids}"
        )
        assert other.id not in ids

    def test_member_with_no_vendor_sees_empty(
        self, client, admin_user, admin_headers, member_user, member_headers,
        db_session,
    ):
        _grant_vendors_read(db_session, member_user.id)
        # Don't attach member_user to any vendor.
        _make_vendor(db_session, name="Lonely-Vendor")
        member_user.vendor_id = None
        db_session.commit()
        resp = client.get("/api/v3/vendors", headers=member_headers)
        assert resp.status_code == 200, resp.text
        elements = resp.json()["data"]["_embedded"]["elements"]
        # Member with no vendor mapping sees no vendors.
        assert elements == []

    def test_master_vendors_endpoint_inherits_filter(
        self, client, admin_user, admin_headers, member_user, member_headers,
        db_session,
    ):
        _grant_vendors_read(db_session, member_user.id)
        attached = _make_vendor(db_session, name="Master-Filter-Vendor")
        _make_vendor(db_session, name="Other-Master-Filter")
        member_user.vendor_id = attached.id
        db_session.commit()

        resp = client.get("/api/v3/master/vendors", headers=member_headers)
        assert resp.status_code == 200, resp.text
        ids = _ids(resp.json())
        assert ids == {attached.id}
