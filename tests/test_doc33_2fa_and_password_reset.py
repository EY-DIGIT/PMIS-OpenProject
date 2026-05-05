"""Doc 33 (change 3) — 2FA OTP + forgot-password + notification log.

Coverage:
- ``MockNotificationClient`` writes to ``notification_log`` (no real
  HTTP). Inspecting the table reveals every notification dispatched.
- 2FA login flow: ``/login`` → ``/login/send-otp`` → ``/login/verify-otp``.
  Cooldown, max attempts, expiry, single-use semantics, channel selection.
- Forgot-password flow: ``/users/forgot-password`` (anti-enumeration)
  + ``/users/reset-password`` (URL token via email or OTP via SMS).
- Per-user 2FA opt-out (``users.two_factor_enabled=False``) skips OTP.

Tests use a dedicated ``2fa_user`` fixture that has ``two_factor_enabled=True``
so the OTP flow fires; the standard ``admin_user`` / ``member_user``
fixtures stay 2FA-off so the rest of the suite keeps working.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.security import hash_password
from app.infrastructure.db.models.notification_log import NotificationLogModel
from app.infrastructure.db.models.otp_code import OtpCodeModel
from app.infrastructure.db.models.password_reset_token import (
    PasswordResetTokenModel,
)
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.repositories.rbac_repository import RbacRepository
from app.shared.otp import hash_secret


@pytest.fixture
def two_fa_user(db_session):
    """User with 2FA explicitly enabled. Phone number on file so SMS
    channel is also available."""
    RbacRepository(db_session).sync_builtin_permissions()
    db_session.commit()
    u = UserModel(
        login="otp_user",
        email="otp@example.com",
        hashed_password=hash_password("password123"),
        first_name="Otp",
        last_name="User",
        status="active",
        phone_number="+919999999999",
        two_factor_enabled=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _login(client, login: str, password: str):
    return client.post(
        "/api/v3/users/login",
        json={"login": login, "password": password},
    )


# ===========================================================================
# 2FA — login stage 1 (password verify → ephemeral token)
# ===========================================================================

class TestLoginStage1:
    def test_2fa_user_gets_ephemeral_token(self, client, two_fa_user):
        r = _login(client, "otp_user", "password123")
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["_type"] == "LoginOtpRequired"
        assert body["requires_otp"] is True
        assert isinstance(body["ephemeral_token"], str)
        assert len(body["ephemeral_token"]) > 16
        assert "access_token" not in body  # NOT minted yet
        # Channel list includes both since user has phone number.
        assert "email" in body["channels_available"]
        assert "sms" in body["channels_available"]

    def test_user_without_phone_only_has_email_channel(
        self, client, db_session, two_fa_user,
    ):
        # Strip the phone number.
        two_fa_user.phone_number = None
        db_session.commit()
        r = _login(client, "otp_user", "password123")
        body = r.json()["data"]
        assert body["channels_available"] == ["email"]

    def test_2fa_off_user_gets_access_token_directly(
        self, client, admin_user,
    ):
        """admin_user fixture has two_factor_enabled=False — single-stage
        login still works for 2FA-disabled users."""
        r = _login(client, "admin", "admin123")
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert "access_token" in body
        assert body["_type"] == "Login"

    def test_wrong_password_rejected(self, client, two_fa_user):
        r = _login(client, "otp_user", "wrong")
        assert r.status_code == 401


# ===========================================================================
# 2FA — send OTP
# ===========================================================================

class TestSendOtp:
    def _start_session(self, client, two_fa_user):
        r = _login(client, "otp_user", "password123")
        return r.json()["data"]["ephemeral_token"]

    def test_send_otp_email_channel(
        self, client, two_fa_user, db_session,
    ):
        ephemeral = self._start_session(client, two_fa_user)
        r = client.post(
            "/api/v3/users/login/send-otp",
            json={"ephemeral_token": ephemeral, "channel": "email"},
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["channel"] == "email"
        assert data["expires_in_seconds"] == settings.OTP_TTL_SECONDS
        # Notification row exists.
        rows = (
            db_session.query(NotificationLogModel)
            .filter(NotificationLogModel.user_id == two_fa_user.id)
            .filter(NotificationLogModel.template_kind == "otp_login")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].channel == "email"
        assert rows[0].recipient == "otp@example.com"
        assert rows[0].status == "sent"
        # The actual code is in the payload (mock client surfaces it).
        assert "code" in rows[0].payload
        assert len(rows[0].payload["code"]) == settings.OTP_CODE_LENGTH

    def test_send_otp_sms_channel(
        self, client, two_fa_user, db_session,
    ):
        ephemeral = self._start_session(client, two_fa_user)
        r = client.post(
            "/api/v3/users/login/send-otp",
            json={"ephemeral_token": ephemeral, "channel": "sms"},
        )
        assert r.status_code == 200, r.text
        rows = (
            db_session.query(NotificationLogModel)
            .filter(NotificationLogModel.template_kind == "otp_login")
            .all()
        )
        assert rows[0].channel == "sms"
        assert rows[0].recipient == "+919999999999"

    def test_send_otp_invalid_channel(self, client, two_fa_user):
        ephemeral = self._start_session(client, two_fa_user)
        r = client.post(
            "/api/v3/users/login/send-otp",
            json={"ephemeral_token": ephemeral, "channel": "carrier_pigeon"},
        )
        assert r.status_code == 422

    def test_send_otp_sms_rejected_when_no_phone(
        self, client, db_session, two_fa_user,
    ):
        two_fa_user.phone_number = None
        db_session.commit()
        ephemeral = self._start_session(client, two_fa_user)
        r = client.post(
            "/api/v3/users/login/send-otp",
            json={"ephemeral_token": ephemeral, "channel": "sms"},
        )
        assert r.status_code == 422

    def test_resend_within_cooldown_rejected(
        self, client, two_fa_user,
    ):
        ephemeral = self._start_session(client, two_fa_user)
        r1 = client.post(
            "/api/v3/users/login/send-otp",
            json={"ephemeral_token": ephemeral, "channel": "email"},
        )
        assert r1.status_code == 200
        r2 = client.post(
            "/api/v3/users/login/send-otp",
            json={"ephemeral_token": ephemeral, "channel": "email"},
        )
        assert r2.status_code == 429, r2.text
        body = r2.json()["error"]
        assert body["errorIdentifier"] == "cooldown"

    def test_invalid_ephemeral_token_rejected(self, client, two_fa_user):
        r = client.post(
            "/api/v3/users/login/send-otp",
            json={"ephemeral_token": "totally-fake-token", "channel": "email"},
        )
        assert r.status_code == 401


# ===========================================================================
# 2FA — verify OTP
# ===========================================================================

class TestVerifyOtp:
    def _full_setup(self, client, two_fa_user, db_session):
        ephemeral = _login(client, "otp_user", "password123").json()["data"]["ephemeral_token"]
        client.post(
            "/api/v3/users/login/send-otp",
            json={"ephemeral_token": ephemeral, "channel": "email"},
        )
        # Pull the actual code from the notification log (mock surfaces it).
        row = (
            db_session.query(NotificationLogModel)
            .filter(NotificationLogModel.template_kind == "otp_login")
            .order_by(NotificationLogModel.id.desc())
            .first()
        )
        return ephemeral, row.payload["code"]

    def test_correct_code_mints_access_token(
        self, client, two_fa_user, db_session,
    ):
        ephemeral, code = self._full_setup(client, two_fa_user, db_session)
        r = client.post(
            "/api/v3/users/login/verify-otp",
            json={"ephemeral_token": ephemeral, "code": code},
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["_type"] == "Login"
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["user"]["login"] == "otp_user"

    def test_wrong_code_rejected_and_consumes_attempt(
        self, client, two_fa_user, db_session,
    ):
        ephemeral, _ = self._full_setup(client, two_fa_user, db_session)
        r = client.post(
            "/api/v3/users/login/verify-otp",
            json={"ephemeral_token": ephemeral, "code": "000000"},
        )
        assert r.status_code == 401
        body = r.json()["error"]
        assert "attempt" in body["message"].lower() or "Wrong code" in body["message"]

    def test_max_attempts_invalidates_otp(
        self, client, two_fa_user, db_session,
    ):
        ephemeral, _ = self._full_setup(client, two_fa_user, db_session)
        # Fire OTP_MAX_ATTEMPTS wrong codes.
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            client.post(
                "/api/v3/users/login/verify-otp",
                json={"ephemeral_token": ephemeral, "code": "000000"},
            )
        # The row should now be consumed.
        row = (
            db_session.query(OtpCodeModel)
            .filter(OtpCodeModel.code_hash != "")  # skip sentinel
            .order_by(OtpCodeModel.id.desc())
            .first()
        )
        assert row.consumed_at is not None

    def test_consumed_otp_cannot_verify_again(
        self, client, two_fa_user, db_session,
    ):
        ephemeral, code = self._full_setup(client, two_fa_user, db_session)
        # First verify succeeds.
        r1 = client.post(
            "/api/v3/users/login/verify-otp",
            json={"ephemeral_token": ephemeral, "code": code},
        )
        assert r1.status_code == 200
        # Second attempt with same token fails.
        r2 = client.post(
            "/api/v3/users/login/verify-otp",
            json={"ephemeral_token": ephemeral, "code": code},
        )
        assert r2.status_code == 401

    def test_expired_otp_rejected(
        self, client, two_fa_user, db_session,
    ):
        ephemeral, code = self._full_setup(client, two_fa_user, db_session)
        # Force expiry by editing the row.
        row = (
            db_session.query(OtpCodeModel)
            .filter(OtpCodeModel.ephemeral_token_hash == hash_secret(ephemeral))
            .filter(OtpCodeModel.code_hash != "")
            .first()
        )
        row.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).replace(tzinfo=None)
        db_session.commit()
        r = client.post(
            "/api/v3/users/login/verify-otp",
            json={"ephemeral_token": ephemeral, "code": code},
        )
        assert r.status_code == 401
        assert "expired" in r.json()["error"]["message"].lower()


# ===========================================================================
# Forgot-password — anti-enumeration + reset flows
# ===========================================================================

class TestForgotPassword:
    def test_unknown_user_returns_200_with_generic_message(self, client):
        r = client.post(
            "/api/v3/users/forgot-password",
            json={
                "login_or_email": "nobody@nowhere.com",
                "channel": "email",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["_type"] == "PasswordResetRequestAck"
        assert "if an account" in body["message"].lower()

    def test_known_user_email_channel_dispatches_link(
        self, client, two_fa_user, db_session,
    ):
        r = client.post(
            "/api/v3/users/forgot-password",
            json={
                "login_or_email": "otp_user",
                "channel": "email",
            },
        )
        assert r.status_code == 200
        # Notification log row + reset token row both exist.
        notif = (
            db_session.query(NotificationLogModel)
            .filter(NotificationLogModel.template_kind == "password_reset_link")
            .first()
        )
        assert notif is not None
        assert notif.channel == "email"
        assert "reset_token" in notif.payload
        token_row = (
            db_session.query(PasswordResetTokenModel)
            .filter(PasswordResetTokenModel.user_id == two_fa_user.id)
            .first()
        )
        assert token_row is not None
        assert token_row.channel == "email"

    def test_known_user_sms_channel_dispatches_otp(
        self, client, two_fa_user, db_session,
    ):
        r = client.post(
            "/api/v3/users/forgot-password",
            json={
                "login_or_email": "otp_user",
                "channel": "sms",
            },
        )
        assert r.status_code == 200
        notif = (
            db_session.query(NotificationLogModel)
            .filter(NotificationLogModel.template_kind == "password_reset_otp")
            .first()
        )
        assert notif is not None
        assert notif.channel == "sms"
        assert "code" in notif.payload
        assert len(notif.payload["code"]) == settings.OTP_CODE_LENGTH

    def test_invalid_channel_rejected(self, client):
        r = client.post(
            "/api/v3/users/forgot-password",
            json={
                "login_or_email": "anyone@anywhere.com",
                "channel": "carrier_pigeon",
            },
        )
        assert r.status_code == 422


# ===========================================================================
# Reset-password (token verification + password update)
# ===========================================================================

class TestResetPassword:
    def _request_reset_email(self, client, two_fa_user, db_session):
        client.post(
            "/api/v3/users/forgot-password",
            json={"login_or_email": "otp_user", "channel": "email"},
        )
        notif = (
            db_session.query(NotificationLogModel)
            .filter(NotificationLogModel.template_kind == "password_reset_link")
            .order_by(NotificationLogModel.id.desc())
            .first()
        )
        return notif.payload["reset_token"]

    def test_correct_token_resets_password(
        self, client, two_fa_user, db_session,
    ):
        token = self._request_reset_email(client, two_fa_user, db_session)
        r = client.post(
            "/api/v3/users/reset-password",
            json={
                "token_or_code": token,
                "new_password": "newSecurePass1",
            },
        )
        assert r.status_code == 200, r.text
        # New password works for login.
        login = _login(client, "otp_user", "newSecurePass1")
        assert login.status_code == 200, login.text
        # Old password no longer works.
        old = _login(client, "otp_user", "password123")
        assert old.status_code == 401

    def test_token_single_use(
        self, client, two_fa_user, db_session,
    ):
        token = self._request_reset_email(client, two_fa_user, db_session)
        r1 = client.post(
            "/api/v3/users/reset-password",
            json={"token_or_code": token, "new_password": "first_change_pass"},
        )
        assert r1.status_code == 200
        r2 = client.post(
            "/api/v3/users/reset-password",
            json={"token_or_code": token, "new_password": "another_one_passw"},
        )
        assert r2.status_code == 401

    def test_invalid_token_rejected(self, client):
        r = client.post(
            "/api/v3/users/reset-password",
            json={"token_or_code": "totally-fake", "new_password": "newSecure1"},
        )
        assert r.status_code == 401

    def test_short_password_rejected(
        self, client, two_fa_user, db_session,
    ):
        token = self._request_reset_email(client, two_fa_user, db_session)
        r = client.post(
            "/api/v3/users/reset-password",
            json={"token_or_code": token, "new_password": "short"},
        )
        assert r.status_code == 422

    def test_expired_token_rejected(
        self, client, two_fa_user, db_session,
    ):
        token = self._request_reset_email(client, two_fa_user, db_session)
        # Force expiry.
        row = (
            db_session.query(PasswordResetTokenModel)
            .filter(PasswordResetTokenModel.token_hash == hash_secret(token))
            .first()
        )
        row.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).replace(tzinfo=None)
        db_session.commit()
        r = client.post(
            "/api/v3/users/reset-password",
            json={"token_or_code": token, "new_password": "newSecurePass1"},
        )
        assert r.status_code == 401


# ===========================================================================
# NotificationClient infrastructure
# ===========================================================================

class TestNotificationClient:
    def test_mock_client_writes_to_log(self, db_session):
        from app.shared.notifications import (
            CHANNEL_EMAIL,
            TEMPLATE_OTP_LOGIN,
            MockNotificationClient,
        )
        client = MockNotificationClient(db_session)
        client.send(
            user_id=None,
            channel=CHANNEL_EMAIL,
            recipient="someone@example.com",
            template_kind=TEMPLATE_OTP_LOGIN,
            payload={"code": "123456"},
        )
        row = (
            db_session.query(NotificationLogModel)
            .filter(NotificationLogModel.recipient == "someone@example.com")
            .one()
        )
        assert row.status == "sent"
        assert row.channel == "email"
        assert row.template_kind == "otp_login"

    def test_factory_returns_mock_by_default(self, db_session):
        from app.shared.notifications import (
            MockNotificationClient,
            get_notification_client,
        )
        c = get_notification_client(db_session)
        assert isinstance(c, MockNotificationClient)
