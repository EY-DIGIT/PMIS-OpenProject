"""Doc 36 — DB-backed notification templates.

Coverage:
- Seeded built-in rows are present (autouse seed in conftest).
- CRUD over /api/v3/master/notification_templates.
- Built-in rows are editable on subject/body but protected from hard delete.
- Placeholder validation rejects unknown placeholders for the well-known kinds.
- Active uniqueness: at most one active row per (kind, channel) pair.
- Renderer lookup: ``_render_email`` / ``_render_sms`` substitute correctly
  and fall back to a generic body when no active row matches.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Seed sanity
# ---------------------------------------------------------------------------

class TestSeed:
    def test_six_seed_rows_present(self, client, admin_headers):
        resp = client.get(
            "/api/v3/master/notification_templates",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]["_embedded"]["elements"]
        # 3 kinds x 2 channels = 6 seed rows.
        kinds = {(r["templateKind"], r["channel"]) for r in rows}
        assert kinds == {
            ("otp_login", "email"),
            ("otp_login", "sms"),
            ("password_reset_link", "email"),
            ("password_reset_link", "sms"),
            ("password_reset_otp", "email"),
            ("password_reset_otp", "sms"),
        }
        for r in rows:
            assert r["isBuiltin"] is True
            assert r["active"] is True

    def test_email_seed_row_has_subject_sms_does_not(
        self, client, admin_headers,
    ):
        resp = client.get(
            "/api/v3/master/notification_templates",
            headers=admin_headers,
        )
        rows = resp.json()["data"]["_embedded"]["elements"]
        for r in rows:
            if r["channel"] == "email":
                assert r["subject"] is not None and r["subject"].strip()
            else:
                assert r["subject"] in (None, "")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class TestCreate:
    def test_admin_can_create_custom_template(self, client, admin_headers):
        resp = client.post(
            "/api/v3/master/notification_templates/create",
            headers=admin_headers,
            json={
                "templateKind": "custom_kind",
                "channel": "email",
                "subject": "Hello {name}",
                "body": "<p>Hi {name}, this is a test.</p>",
                "description": "Custom test template",
            },
        )
        assert resp.status_code == 201, resp.text
        d = resp.json()["data"]
        assert d["templateKind"] == "custom_kind"
        assert d["channel"] == "email"
        assert d["isBuiltin"] is False
        assert d["isHtml"] is True  # default for email

    def test_email_create_requires_subject(self, client, admin_headers):
        resp = client.post(
            "/api/v3/master/notification_templates/create",
            headers=admin_headers,
            json={
                "templateKind": "custom_kind",
                "channel": "email",
                "body": "<p>no subject!</p>",
            },
        )
        assert resp.status_code == 422, resp.text

    def test_sms_create_rejects_subject(self, client, admin_headers):
        resp = client.post(
            "/api/v3/master/notification_templates/create",
            headers=admin_headers,
            json={
                "templateKind": "custom_kind",
                "channel": "sms",
                "subject": "no subject for sms",
                "body": "hi",
            },
        )
        assert resp.status_code == 422, resp.text

    def test_unknown_placeholder_rejected_for_known_kind(
        self, client, admin_headers,
    ):
        # otp_login allows {code} {ttl_minutes}. Reject anything else.
        # First, deactivate the built-in (otp_login, email) row so the
        # active-uniqueness guard doesn't bite.
        list_resp = client.get(
            "/api/v3/master/notification_templates",
            headers=admin_headers,
        )
        tmpl_id = next(
            r["id"] for r in list_resp.json()["data"]["_embedded"]["elements"]
            if r["templateKind"] == "otp_login" and r["channel"] == "email"
        )
        client.delete(
            f"/api/v3/master/notification_templates/{tmpl_id}",
            headers=admin_headers,
        )

        resp = client.post(
            "/api/v3/master/notification_templates/create",
            headers=admin_headers,
            json={
                "templateKind": "otp_login",
                "channel": "email",
                "subject": "OTP {oops}",
                "body": "<p>{code}</p>",
            },
        )
        assert resp.status_code == 422, resp.text

    def test_unknown_kind_skips_placeholder_check(
        self, client, admin_headers,
    ):
        # Custom kind: any placeholders are allowed.
        resp = client.post(
            "/api/v3/master/notification_templates/create",
            headers=admin_headers,
            json={
                "templateKind": "my_custom_event",
                "channel": "email",
                "subject": "Subject {anything}",
                "body": "<p>{whatever} {goes} {here}</p>",
            },
        )
        assert resp.status_code == 201, resp.text

    def test_active_uniqueness_per_kind_channel(self, client, admin_headers):
        # The seeded (otp_login, email) row is already active. Trying
        # to create another active row for the same pair returns 409.
        resp = client.post(
            "/api/v3/master/notification_templates/create",
            headers=admin_headers,
            json={
                "templateKind": "otp_login",
                "channel": "email",
                "subject": "Duplicate",
                "body": "<p>{code} {ttl_minutes}</p>",
            },
        )
        assert resp.status_code == 409, resp.text

    def test_member_cannot_create(self, client, member_headers):
        resp = client.post(
            "/api/v3/master/notification_templates/create",
            headers=member_headers,
            json={
                "templateKind": "anything",
                "channel": "sms",
                "body": "test",
            },
        )
        assert resp.status_code == 403, resp.text


class TestUpdate:
    def _row_id(self, client, admin_headers, kind, channel):
        resp = client.get(
            "/api/v3/master/notification_templates",
            headers=admin_headers,
        )
        return next(
            r["id"] for r in resp.json()["data"]["_embedded"]["elements"]
            if r["templateKind"] == kind and r["channel"] == channel
        )

    def test_can_edit_builtin_subject_and_body(
        self, client, admin_headers,
    ):
        # The whole point of moving templates to DB: ops can edit copy
        # without a release. Built-ins ARE editable on subject/body.
        tmpl_id = self._row_id(client, admin_headers, "otp_login", "email")
        resp = client.patch(
            f"/api/v3/master/notification_templates/{tmpl_id}",
            headers=admin_headers,
            json={
                "subject": "PMIS — login code",
                "body": "<p>Your code: {code} (expires in {ttl_minutes} min).</p>",
            },
        )
        assert resp.status_code == 200, resp.text
        d = resp.json()["data"]
        assert d["subject"] == "PMIS — login code"
        assert "{code}" in d["body"]

    def test_patch_with_unknown_placeholder_rejected(
        self, client, admin_headers,
    ):
        tmpl_id = self._row_id(client, admin_headers, "otp_login", "email")
        resp = client.patch(
            f"/api/v3/master/notification_templates/{tmpl_id}",
            headers=admin_headers,
            json={"body": "<p>Hello {nonsense}</p>"},
        )
        assert resp.status_code == 422, resp.text


class TestDelete:
    def _row_id(self, client, admin_headers, kind, channel):
        resp = client.get(
            "/api/v3/master/notification_templates",
            headers=admin_headers,
        )
        return next(
            r["id"] for r in resp.json()["data"]["_embedded"]["elements"]
            if r["templateKind"] == kind and r["channel"] == channel
        )

    def test_delete_soft_deactivates(self, client, admin_headers):
        tmpl_id = self._row_id(client, admin_headers, "otp_login", "sms")
        resp = client.delete(
            f"/api/v3/master/notification_templates/{tmpl_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["active"] is False

    def test_restore_brings_row_back(self, client, admin_headers):
        tmpl_id = self._row_id(client, admin_headers, "otp_login", "sms")
        client.delete(
            f"/api/v3/master/notification_templates/{tmpl_id}",
            headers=admin_headers,
        )
        resp = client.post(
            f"/api/v3/master/notification_templates/{tmpl_id}/restore",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["active"] is True

    def test_restore_blocked_when_other_active_row_covers_pair(
        self, client, admin_headers,
    ):
        # Deactivate (otp_login, sms), create a new active row for the
        # same pair, then try to restore the original — should 409.
        original_id = self._row_id(client, admin_headers, "otp_login", "sms")
        client.delete(
            f"/api/v3/master/notification_templates/{original_id}",
            headers=admin_headers,
        )
        replacement = client.post(
            "/api/v3/master/notification_templates/create",
            headers=admin_headers,
            json={
                "templateKind": "otp_login",
                "channel": "sms",
                "body": "Replacement: {code} (expires in {ttl_minutes} min).",
            },
        )
        assert replacement.status_code == 201
        resp = client.post(
            f"/api/v3/master/notification_templates/{original_id}/restore",
            headers=admin_headers,
        )
        assert resp.status_code == 409, resp.text


# ---------------------------------------------------------------------------
# Renderer integration
# ---------------------------------------------------------------------------

class TestRendererLookup:
    def test_email_renderer_substitutes_seeded_template(
        self, db_session,
    ):
        from app.shared.notifications import _render_email
        subject, body = _render_email(
            db_session,
            "otp_login",
            {"code": "987654", "ttl_seconds": 300},
        )
        assert "987654" in body
        assert "5 minutes" in body
        assert subject

    def test_sms_renderer_substitutes_seeded_template(self, db_session):
        from app.shared.notifications import _render_sms
        msg = _render_sms(
            db_session,
            "otp_login",
            {"code": "112233", "ttl_seconds": 300},
        )
        assert "112233" in msg
        assert "5 min" in msg

    def test_renderer_falls_back_when_no_active_row(
        self, db_session,
    ):
        from app.infrastructure.db.models.notification_template import (
            NotificationTemplateModel,
        )
        from app.shared.notifications import _render_email

        # Deactivate every email row for otp_login.
        rows = (
            db_session.query(NotificationTemplateModel)
            .filter_by(template_kind="otp_login", channel="email", active=True)
            .all()
        )
        for r in rows:
            r.active = False
        db_session.commit()

        subject, body = _render_email(
            db_session,
            "otp_login",
            {"code": "000000", "ttl_seconds": 300},
        )
        # Fallback subject + body — no substitution.
        assert subject == "PMIS notification"
        assert "000000" not in body
        assert "Sign in to your account" in body
