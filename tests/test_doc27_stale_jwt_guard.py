"""Doc 27 hotfix — pre-doc-26 stale JWT guard.

Reported: a JWT minted before doc 26 (when ``users.id`` was an
auto-incrementing integer) reached the auth middleware after the
Postgres deployment ran the doc 26 migration. The middleware
forwarded the int ``user_id=1`` claim straight into a query against
``user_roles.user_id`` (now ``varchar(36)``), and Postgres threw
``operator does not exist: character varying = integer`` → 500 in
the response.

Fix: the auth middleware (``app/core/middleware/auth.py``) now
validates that ``payload['user_id']`` is a UUID-shaped string. If
not, the request is treated as anonymous — every protected route
returns 401 (FE handles this as "session expired, re-login"), no DB
query fires, no 500.

These tests assert that:
  1. A JWT with an integer ``user_id`` claim → protected endpoint
     returns 401 (NOT 500) and no permissions are loaded.
  2. A JWT with a malformed string user_id (e.g. ``"abc"``) → also 401.
  3. A JWT with a missing ``user_id`` claim → also 401.
  4. A normal UUID-claim JWT continues to work unchanged.
"""
from datetime import timedelta

import pytest

from app.core.security import create_access_token


def _mint_token(**claims):
    """Build an access token with arbitrary user_id claim shape."""
    payload = {"sub": claims.get("sub", "stale-user")}
    if "user_id" in claims:
        payload["user_id"] = claims["user_id"]
    payload["email"] = claims.get("email", "stale@example.com")
    return create_access_token(payload, expires_delta=timedelta(minutes=10))


# ===========================================================================
# Stale int-claim token → 401, not 500
# ===========================================================================

class TestPreDoc26IntClaimToken:
    def test_int_user_id_returns_401_on_protected_endpoint(self, client):
        """The exact reported scenario: stale token with user_id=1
        hits a protected endpoint. Must NOT bubble up as a 500."""
        token = _mint_token(user_id=1)
        resp = client.get(
            "/api/v3/users", headers={"Authorization": f"Bearer {token}"},
        )
        # Pre-fix this returned 500 (Postgres) or crashed (SQLite).
        # Post-fix: 401 — anonymous request rejected by require_permission.
        assert resp.status_code == 401, (
            f"Expected 401 for stale int-claim token, got {resp.status_code}: {resp.text}"
        )

    def test_int_user_id_does_not_set_request_user_id(self, client):
        """Belt-and-braces: /users/me also fails with 401, proving the
        middleware never set request.state.user_id from the bad claim."""
        token = _mint_token(user_id=42)
        resp = client.get(
            "/api/v3/users/me", headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401, resp.text

    @pytest.mark.parametrize("bad_user_id", [
        "1",            # numeric string — looks like old int but isn't a UUID
        "abc",          # arbitrary string
        "",             # empty
        "not-a-uuid",   # close to UUID shape but invalid
        "12345678-1234-1234-1234-12345678",  # too short
    ])
    def test_malformed_user_id_returns_401(self, client, bad_user_id):
        token = _mint_token(user_id=bad_user_id)
        resp = client.get(
            "/api/v3/users/me", headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401, (
            f"user_id={bad_user_id!r} should yield 401, got {resp.status_code}: {resp.text}"
        )

    def test_missing_user_id_claim_returns_401(self, client):
        # Token with no user_id at all (e.g. some legacy minting code path).
        token = create_access_token({"sub": "noid"}, expires_delta=timedelta(minutes=10))
        resp = client.get(
            "/api/v3/users/me", headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401, resp.text


# ===========================================================================
# Sanity — UUID-claim token still works
# ===========================================================================

class TestUuidClaimTokenStillWorks:
    def test_normal_admin_token_works(self, client, admin_user, admin_headers):
        """Standard happy path — confirms the guard didn't accidentally
        block valid tokens. admin_user.id is a UUID (post-doc-26 fixture)."""
        resp = client.get("/api/v3/users/me", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["id"] == admin_user.id


# ===========================================================================
# Helper unit test — _is_valid_user_id_claim coverage
# ===========================================================================

class TestIsValidUserIdClaim:
    @pytest.mark.parametrize("value,expected", [
        ("8bd99f06-5f2a-424c-aaff-10ab163c3e42", True),   # canonical UUID
        ("00000000-0000-0000-0000-000000000000", True),   # nil UUID
        ("8BD99F06-5F2A-424C-AAFF-10AB163C3E42", True),   # uppercase hex
        (1, False),
        ("1", False),
        ("", False),
        (None, False),
        ("abc", False),
        ("not-a-uuid", False),
        (b"8bd99f06-5f2a-424c-aaff-10ab163c3e42", False),  # bytes, not str
        (12345, False),
    ])
    def test_validation(self, value, expected):
        from app.core.middleware.auth import _is_valid_user_id_claim
        assert _is_valid_user_id_claim(value) is expected, value
