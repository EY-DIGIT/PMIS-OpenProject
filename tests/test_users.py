"""Tests for user management endpoints."""
import pytest


class TestCreateUser:
    """POST /api/v3/users"""

    def test_create_user_success(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users/create", json={
            "login": "newuser",
            "email": "new@example.com",
            "password": "password123",
            "firstName": "New",
            "lastName": "User",
            "admin": False,
        }, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["login"] == "newuser"
        assert data["email"] == "new@example.com"
        assert data["_type"] == "User"
        assert "id" in data

    def test_create_user_duplicate_login(self, client, admin_user, admin_headers):
        client.post("/api/v3/users/create", json={
            "login": "dup", "email": "a@a.com", "password": "password123",
        }, headers=admin_headers)
        resp = client.post("/api/v3/users/create", json={
            "login": "dup", "email": "b@b.com", "password": "password123",
        }, headers=admin_headers)
        assert resp.status_code == 409

    def test_create_user_duplicate_email(self, client, admin_user, admin_headers):
        client.post("/api/v3/users/create", json={
            "login": "user1", "email": "same@example.com", "password": "password123",
        }, headers=admin_headers)
        resp = client.post("/api/v3/users/create", json={
            "login": "user2", "email": "same@example.com", "password": "password123",
        }, headers=admin_headers)
        assert resp.status_code == 409

    def test_create_user_invalid_email(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users/create", json={
            "login": "badmail", "email": "not-an-email", "password": "password123",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_user_short_password(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users/create", json={
            "login": "shortpw", "email": "s@s.com", "password": "short",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_user_short_login(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users/create", json={
            "login": "ab", "email": "ab@ab.com", "password": "password123",
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_user_missing_required(self, client, admin_user, admin_headers):
        resp = client.post("/api/v3/users/create", json={"login": "only"}, headers=admin_headers)
        assert resp.status_code == 422


class TestListUsers:
    """GET /api/v3/users"""

    def test_list_users(self, client, admin_user, admin_headers):
        resp = client.get("/api/v3/users?offset=1&pageSize=10", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["_type"] == "Collection"
        assert body["total"] >= 1
        assert "_embedded" in body
        assert "elements" in body["_embedded"]

    def test_list_users_pagination(self, client, admin_user, member_user, admin_headers):
        resp = client.get("/api/v3/users?offset=1&pageSize=1", headers=admin_headers)
        body = resp.json()["data"]
        assert body["count"] == 1
        assert body["pageSize"] == 1

    def test_list_users_forbidden_for_member(self, client, admin_user, member_user, member_headers):
        resp = client.get("/api/v3/users", headers=member_headers)
        assert resp.status_code == 403


class TestGetUser:
    """GET /api/v3/users/{id}"""

    def test_get_user_by_id(self, client, admin_user, admin_headers):
        resp = client.get(f"/api/v3/users/{admin_user.id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["login"] == "admin"

    def test_get_nonexistent_user(self, client, admin_user, admin_headers):
        resp = client.get("/api/v3/users/99999", headers=admin_headers)
        assert resp.status_code in [200, 404]  # may return 200 with error body


class TestUpdateUser:
    """PATCH /api/v3/users/{id}"""

    def test_update_user(self, client, admin_user, member_user, admin_headers):
        resp = client.patch(f"/api/v3/users/{member_user.id}", json={
            "firstName": "Updated",
            "lastName": "Name",
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["firstName"] == "Updated"

    def test_update_password(self, client, admin_user, member_user, admin_headers):
        resp = client.patch(f"/api/v3/users/{member_user.id}/password", json={
            "password": "newpassword123",
        }, headers=admin_headers)
        assert resp.status_code == 200


class TestDeleteUser:
    """DELETE /api/v3/users/{id}"""

    def test_delete_user(self, client, admin_user, member_user, admin_headers):
        resp = client.delete(f"/api/v3/users/{member_user.id}", headers=admin_headers)
        assert resp.status_code == 200

    def test_delete_nonexistent_user(self, client, admin_user, admin_headers):
        resp = client.delete("/api/v3/users/99999", headers=admin_headers)
        assert resp.status_code in [200, 404]


# ===========================================================================
# Logout (Option B — hard logout)
#
# Server-side revocation:
#   - Access token's jti added to RevokedTokenModel; subsequent requests
#     using the same access token are rejected by AuthenticationMiddleware.
#   - User row's refresh_token_jti is cleared so refresh-token flow fails.
# ===========================================================================

class TestLogout:
    def _login(self, client, login: str, password: str):
        """Helper: login and return (access_token, refresh_token, headers)."""
        resp = client.post(
            "/api/v3/users/login",
            json={"login": login, "password": password},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        return (
            data["access_token"],
            data["refresh_token"],
            {"Authorization": f"Bearer {data['access_token']}"},
        )

    def test_logout_success(self, client, admin_user, admin_headers):
        """POST /users/logout with a valid token → 200 + success message."""
        resp = client.post("/api/v3/users/logout", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"]["_type"] == "Success"
        assert "logged out" in body["data"]["message"].lower()

    def test_logout_blacklists_access_token(self, client, admin_user):
        """After logout, the SAME access token is rejected on subsequent
        protected calls (the jti is in the blacklist)."""
        access, _refresh, headers = self._login(client, "admin", "admin123")

        # Sanity: protected call works with the token.
        me = client.get("/api/v3/users/me", headers=headers)
        assert me.status_code == 200

        # Logout.
        out = client.post("/api/v3/users/logout", headers=headers)
        assert out.status_code == 200, out.text

        # Same token now rejected.
        me_after = client.get("/api/v3/users/me", headers=headers)
        assert me_after.status_code == 401, me_after.text

    def test_logout_clears_refresh_token(self, client, admin_user, db_session):
        """After logout, the user row's refresh_token_jti is NULL."""
        from app.infrastructure.db.models.user import UserModel
        access, _refresh, headers = self._login(client, "admin", "admin123")
        # Sanity: refresh metadata is set after login.
        db_session.expire_all()
        u_before = db_session.query(UserModel).filter_by(login="admin").one()
        assert u_before.refresh_token_jti is not None

        client.post("/api/v3/users/logout", headers=headers)

        db_session.expire_all()
        u_after = db_session.query(UserModel).filter_by(login="admin").one()
        assert u_after.refresh_token_jti is None
        assert u_after.refresh_token_expires_at is None

    def test_logout_invalidates_refresh_endpoint(self, client, admin_user):
        """After logout, the refresh token can no longer mint new access
        tokens via /users/introspect (refresh flow rejects it)."""
        _access, refresh, headers = self._login(client, "admin", "admin123")

        client.post("/api/v3/users/logout", headers=headers)

        # Try to refresh using the now-revoked refresh token.
        intro = client.post(
            "/api/v3/users/introspect",
            json={"refresh_token": refresh},
        )
        assert intro.status_code == 401, intro.text

    def test_logout_inserts_blacklist_row(self, client, admin_user, db_session):
        """A row appears in revoked_tokens with the access token's jti
        and a future expires_at."""
        from datetime import datetime, timezone
        from app.infrastructure.db.models.revoked_token import RevokedTokenModel
        access, _refresh, headers = self._login(client, "admin", "admin123")

        client.post("/api/v3/users/logout", headers=headers)
        db_session.expire_all()

        rows = db_session.query(RevokedTokenModel).filter_by(user_id=admin_user.id).all()
        assert len(rows) == 1
        row = rows[0]
        # SQLite returns naive datetimes; strip tz from "now" so the
        # comparison is naive on both sides. Using timezone-aware now() +
        # replace(tzinfo=None) avoids the deprecated datetime.utcnow().
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        assert row.expires_at > now_naive, \
            "blacklist row's expires_at must be in the future"

    def test_logout_idempotent(self, client, admin_user, admin_headers):
        """Calling logout twice with the same token: first succeeds, second
        rejected (token is already revoked)."""
        first = client.post("/api/v3/users/logout", headers=admin_headers)
        assert first.status_code == 200, first.text

        second = client.post("/api/v3/users/logout", headers=admin_headers)
        # The middleware now treats the token as revoked → 401.
        assert second.status_code == 401, second.text

    def test_logout_without_auth_rejected(self, client):
        """No Authorization header → 401."""
        resp = client.post("/api/v3/users/logout")
        assert resp.status_code == 401

    def test_logout_with_invalid_token_rejected(self, client):
        """Garbage token → 401 (handled by middleware/RBAC)."""
        resp = client.post(
            "/api/v3/users/logout",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401

    def test_logout_does_not_affect_other_users(self, client, admin_user):
        """Logging out as user A leaves user B's session fully working."""
        # Create a second user.
        admin_resp = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"},
        )
        admin_token = admin_resp.json()["data"]["access_token"]
        admin_h = {"Authorization": f"Bearer {admin_token}"}

        client.post(
            "/api/v3/users/create",
            json={
                "login": "userb", "email": "b@b.com",
                "password": "passwordB1",
            },
            headers=admin_h,
        )

        # Both log in.
        _a_access, _a_refresh, a_headers = self._login(client, "admin", "admin123")
        b_access, _b_refresh, b_headers = self._login(client, "userb", "passwordB1")

        # A logs out.
        out_a = client.post("/api/v3/users/logout", headers=a_headers)
        assert out_a.status_code == 200

        # B's token is unaffected.
        me_b = client.get("/api/v3/users/me", headers=b_headers)
        assert me_b.status_code == 200, me_b.text

    def test_login_after_logout_works(self, client, admin_user):
        """Logout doesn't lock the user out — they can log back in fresh."""
        _access, _refresh, headers = self._login(client, "admin", "admin123")
        client.post("/api/v3/users/logout", headers=headers)

        # Fresh login.
        resp = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200, resp.text
        new_token = resp.json()["data"]["access_token"]

        # New token works.
        me = client.get(
            "/api/v3/users/me",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert me.status_code == 200
