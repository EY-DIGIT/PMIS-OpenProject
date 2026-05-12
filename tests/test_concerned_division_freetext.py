"""Activity ``concernedDivision`` — accept free-text values.

Regression coverage for the FE picker's "Other" branch: when the user
selects "Other" the FE reveals a text input and the typed value is sent
inline as a list element alongside catalog codes (project-vendors
multi-add idiom). Example wire body from FE:

    {"concernedDivision": ["tmd1", "other admin"], ...}

Tests cover:
  - free-text + catalog code mixed on POST create (the curl shape)
  - free-text replace on PATCH update
  - case-insensitive dedup preserves first occurrence
  - blank / whitespace-only entries rejected
  - per-entry length cap (64) enforced
  - per-list size cap (20) enforced
  - ``ownerDivision`` stays strict (regression — only concerned was relaxed)
"""
from uuid import uuid4


def _iso(y, m, d):
    return f"{y:04d}-{m:02d}-{d:02d}T00:00:00+05:30"


def _setup(client, admin_headers):
    proj = client.post(
        "/api/v3/projects/create",
        headers=admin_headers,
        json={
            "name": f"CD P {uuid4().hex[:4]}", "owner": "tmd1",
            "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 12, 31),
        },
    ).json()["data"]
    pid = proj["id"]
    v = client.post(
        "/api/v3/master/vendors/create",
        headers=admin_headers,
        json={"name": f"CD V {uuid4().hex[:4]}", "phoneNumber": "+919999999999"},
    ).json()["data"]
    vid = v["id"]
    client.patch(
        f"/api/v3/projects/{pid}", headers=admin_headers,
        json={"vendorIds": [vid]},
    )
    m = client.post(
        f"/api/v3/projects/{pid}/milestones/create",
        headers=admin_headers,
        json={"name": "M1", "startDate": _iso(2026, 7, 1), "endDate": _iso(2026, 8, 30), "priority": "p1"},
    ).json()["data"]
    return pid, vid, m


def _activity_body(vid, *, concerned, owner="tmd1"):
    return {
        "name": "A1",
        "startDate": _iso(2026, 7, 1),
        "endDate": _iso(2026, 7, 20),
        "ownerDivision": owner,
        "vendorId": vid,
        "concernedDivision": concerned,
        "priority": "p2",
    }


class TestConcernedFreeTextOnCreate:
    def test_mixed_code_and_freetext_accepted(
        self, client, admin_user, admin_headers,
    ):
        """Mirrors the FE curl: ['tmd1', 'other admin']."""
        _pid, vid, m = _setup(client, admin_headers)
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=["tmd1", "other admin"]),
        )
        assert r.status_code == 201, r.text
        a = r.json()["data"]
        assert a["concernedDivision"] == ["tmd1", "other admin"]

    def test_pure_freetext_accepted(self, client, admin_user, admin_headers):
        _pid, vid, m = _setup(client, admin_headers)
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=["Some Custom Division"]),
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["concernedDivision"] == ["Some Custom Division"]

    def test_known_codes_normalize_to_lowercase(
        self, client, admin_user, admin_headers,
    ):
        _pid, vid, m = _setup(client, admin_headers)
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=["TMD1", "Others"]),
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["concernedDivision"] == ["tmd1", "others"]

    def test_freetext_preserves_user_casing(
        self, client, admin_user, admin_headers,
    ):
        _pid, vid, m = _setup(client, admin_headers)
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=["Treasury Branch"]),
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["concernedDivision"] == ["Treasury Branch"]

    def test_dedup_case_insensitive(self, client, admin_user, admin_headers):
        _pid, vid, m = _setup(client, admin_headers)
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(
                vid, concerned=["tmd1", "TMD1", "Other Admin", "other admin"],
            ),
        )
        assert r.status_code == 201, r.text
        # first occurrence wins for both casing decisions.
        assert r.json()["data"]["concernedDivision"] == ["tmd1", "Other Admin"]

    def test_blank_entry_rejected(self, client, admin_user, admin_headers):
        _pid, vid, m = _setup(client, admin_headers)
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=["tmd1", "   "]),
        )
        assert r.status_code == 422
        assert "blank" in r.text.lower()

    def test_per_entry_length_cap(self, client, admin_user, admin_headers):
        _pid, vid, m = _setup(client, admin_headers)
        too_long = "x" * 65
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=[too_long]),
        )
        assert r.status_code == 422
        assert "64" in r.text

    def test_list_size_cap(self, client, admin_user, admin_headers):
        _pid, vid, m = _setup(client, admin_headers)
        twenty_one = [f"div-{i}" for i in range(21)]
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=twenty_one),
        )
        assert r.status_code == 422
        assert "20" in r.text


class TestConcernedFreeTextOnUpdate:
    def test_patch_replaces_with_freetext(self, client, admin_user, admin_headers):
        _pid, vid, m = _setup(client, admin_headers)
        a = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=["tmd1"]),
        ).json()["data"]
        r = client.patch(
            f"/api/v3/activities/{a['id']}",
            headers=admin_headers,
            json={"concernedDivision": ["tmd2", "other admin"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["concernedDivision"] == ["tmd2", "other admin"]

    def test_patch_blank_entry_rejected(self, client, admin_user, admin_headers):
        _pid, vid, m = _setup(client, admin_headers)
        a = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(vid, concerned=["tmd1"]),
        ).json()["data"]
        r = client.patch(
            f"/api/v3/activities/{a['id']}",
            headers=admin_headers,
            json={"concernedDivision": ["", "tmd1"]},
        )
        assert r.status_code == 422


class TestOwnerDivisionMasterTable:
    """Doc 49: ``ownerDivision`` is validated against the live
    ``divisions`` master table (not a hardcoded set). Built-in codes
    (tmd1 / tmd2 / others) pass because init_db seeds them; arbitrary
    free-text values fail because they're not in the table."""

    def test_owner_freetext_rejected(self, client, admin_user, admin_headers):
        _pid, vid, m = _setup(client, admin_headers)
        r = client.post(
            f"/api/v3/milestones/{m['id']}/activities/create",
            headers=admin_headers,
            json=_activity_body(
                vid, concerned=["tmd1"], owner="custom division",
            ),
        )
        assert r.status_code == 422
        # New wording from doc 49 — error names the bad code and points
        # to the master-data endpoint, not the hardcoded set.
        body = r.text.lower()
        assert "ownerdivision" in body
        assert "custom division" in body
        assert "/api/v3/master/divisions" in body
