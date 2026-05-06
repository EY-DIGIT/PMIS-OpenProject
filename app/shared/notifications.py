"""Notification client (doc 33 change 3 + doc 33 follow-up integration).

Two backends behind one ``NotificationClient`` interface:

- ``MockNotificationClient`` — writes to the ``notification_log`` table
  and returns. The terminal sink during dev/tests; never makes a real
  HTTP call. Inspecting the table reveals every notification that
  would have been sent, with the recipient, channel, and template kind.

- ``HttpNotificationClient`` — POSTs to the live notification
  microservice (https://github.com/EY-DIGIT/PMIS-notification-service).
  Calls ``POST {NOTIFICATION_SERVICE_URL}/api/v1/notifications/email/send``
  for ``email`` channel and ``POST .../sms/send`` for ``sms``. The audit
  row is written first as ``queued``, then patched to ``sent`` (or
  ``failed`` with the error message) once the call returns.

Selection happens via the ``NOTIFICATION_CLIENT`` env var:
  - ``mock`` (default in dev/tests)
  - ``http`` (production / staging — needs ``NOTIFICATION_SERVICE_URL``)

Construct via the factory ``get_notification_client(db)`` — it picks
the backend based on settings and hands back an instance bound to the
provided session. Callers don't need to know which backend won.

The audit row is the source of truth for "did the system attempt to
notify?" — both backends write one before any external call. If the
HTTP call fails, the row is updated to ``status="failed"`` with the
error message so investigations can see exactly what was tried.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..infrastructure.db.models.notification_log import NotificationLogModel


logger = logging.getLogger(__name__)


# Channel constants (kept as strings — short list, no enum overhead).
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"

# Template kinds.
TEMPLATE_OTP_LOGIN = "otp_login"
TEMPLATE_PASSWORD_RESET_LINK = "password_reset_link"
TEMPLATE_PASSWORD_RESET_OTP = "password_reset_otp"


# HTTP timeouts when calling the live notification microservice. Short
# connect timeout so a stuck DNS / unreachable host fails fast and
# doesn't block the auth flow; longer read timeout for legitimate slow
# email-provider hops (SendGrid / SMTP relays).
_HTTP_CONNECT_TIMEOUT = 5.0
_HTTP_READ_TIMEOUT = 15.0


class NotificationClient(ABC):
    """Contract every backend implements."""

    def __init__(self, db: Session):
        self.db = db

    @abstractmethod
    def send(
        self,
        *,
        user_id: Optional[str],
        channel: str,
        recipient: str,
        template_kind: str,
        payload: Dict[str, Any],
    ) -> NotificationLogModel:
        """Dispatch a notification + persist the audit row.

        Returns the persisted row so callers can correlate (e.g. for
        tests asserting the dispatch happened). The row is committed
        before this returns — callers don't need to commit separately.
        """
        raise NotImplementedError


class MockNotificationClient(NotificationClient):
    """Dev / test backend — terminal sink in the ``notification_log``."""

    def send(
        self,
        *,
        user_id: Optional[str],
        channel: str,
        recipient: str,
        template_kind: str,
        payload: Dict[str, Any],
    ) -> NotificationLogModel:
        row = NotificationLogModel(
            user_id=user_id,
            channel=channel,
            recipient=recipient,
            template_kind=template_kind,
            payload=payload,
            status="sent",  # mock pretends it sent
            error=None,
        )
        self.db.add(row)
        self.db.flush()
        self.db.commit()
        return row


# ---------------------------------------------------------------------------
# Email + SMS template renderers — turn (template_kind, payload, recipient)
# into the body the live notification service expects.
#
# Kept dead-simple. No Jinja, no on-disk templates. Three template kinds,
# three branches. Email bodies are minimal HTML for readability in modern
# clients while still rendering plain in old ones.
# ---------------------------------------------------------------------------


def _render_email(
    template_kind: str, payload: Dict[str, Any]
) -> Tuple[str, str]:
    """Return ``(subject, html_body)`` for the email channel."""
    if template_kind == TEMPLATE_OTP_LOGIN:
        code = payload.get("code", "")
        ttl_seconds = int(payload.get("ttl_seconds", 300))
        ttl_minutes = max(1, ttl_seconds // 60)
        subject = "Your PMIS login verification code"
        body = (
            "<p>Your PMIS login verification code is:</p>"
            f"<p style='font-size:22px;font-weight:600;letter-spacing:3px'>{code}</p>"
            f"<p>This code expires in {ttl_minutes} minutes. If you didn't try "
            "to log in, you can ignore this email.</p>"
        )
        return subject, body

    if template_kind == TEMPLATE_PASSWORD_RESET_LINK:
        # The password_reset service writes the token under the
        # ``reset_token`` key. ``token`` is accepted as a fallback so
        # earlier callers don't break, but the canonical key is
        # ``reset_token``.
        token = (
            payload.get("reset_token")
            or payload.get("token", "")
        )
        ttl_seconds = int(payload.get("ttl_seconds", 3600))
        ttl_minutes = max(1, ttl_seconds // 60)

        # When FRONTEND_BASE_URL is set, build a clickable reset link
        # the user can click straight from the email. Otherwise fall
        # back to the bare-token rendering (still functional — the user
        # copies the token and pastes it into the FE's reset-password
        # form, or hits POST /reset-password directly).
        fe_base = (settings.FRONTEND_BASE_URL or "").rstrip("/")
        subject = "PMIS password reset"
        if fe_base and token:
            reset_url = f"{fe_base}/reset-password?token={token}"
            body = (
                "<p>You (or someone) requested a password reset for your "
                "PMIS account. Click the link below to set a new "
                "password:</p>"
                f"<p><a href='{reset_url}'>Reset your PMIS password</a></p>"
                "<p>If the link doesn't work, paste this URL into your "
                "browser:</p>"
                f"<p style='font-family:monospace;word-break:break-all'>{reset_url}</p>"
                f"<p>The link expires in {ttl_minutes} minutes. If you "
                "didn't request a reset, you can ignore this email.</p>"
            )
        else:
            body = (
                "<p>You (or someone) requested a password reset for your "
                "PMIS account. Use this single-use token to reset your "
                "password:</p>"
                f"<p style='font-family:monospace;word-break:break-all'>{token}</p>"
                f"<p>This token expires in {ttl_minutes} minutes. If you "
                "didn't request a reset, you can ignore this email.</p>"
            )
        return subject, body

    if template_kind == TEMPLATE_PASSWORD_RESET_OTP:
        # Email channel sending the OTP form (rare — usually OTP is SMS,
        # link is email — but supported for completeness).
        # password_reset service writes the SMS-channel value under
        # ``code``; ``token`` / ``reset_token`` are accepted as
        # fallbacks for caller variability.
        code = (
            payload.get("code")
            or payload.get("reset_token")
            or payload.get("token", "")
        )
        ttl_seconds = int(payload.get("ttl_seconds", 3600))
        ttl_minutes = max(1, ttl_seconds // 60)
        subject = "PMIS password reset code"
        body = (
            "<p>Your PMIS password reset code is:</p>"
            f"<p style='font-size:22px;font-weight:600;letter-spacing:3px'>{code}</p>"
            f"<p>This code expires in {ttl_minutes} minutes. If you didn't "
            "request a reset, you can ignore this email.</p>"
        )
        return subject, body

    # Unknown template kind — defensive fallback. Surfacing an error
    # to the user is worse than sending a generic notification.
    logger.warning(
        "Unknown notification template_kind=%r; sending generic body.",
        template_kind,
    )
    subject = "PMIS notification"
    body = (
        "<p>You have a notification from PMIS. Sign in to your account "
        "for details.</p>"
    )
    return subject, body


def _render_sms(template_kind: str, payload: Dict[str, Any]) -> str:
    """Return the SMS body for the sms channel."""
    if template_kind == TEMPLATE_OTP_LOGIN:
        code = payload.get("code", "")
        ttl_seconds = int(payload.get("ttl_seconds", 300))
        ttl_minutes = max(1, ttl_seconds // 60)
        return (
            f"PMIS login code: {code}. Expires in {ttl_minutes} min. "
            f"Don't share this code."
        )

    if template_kind == TEMPLATE_PASSWORD_RESET_OTP:
        code = (
            payload.get("code")
            or payload.get("reset_token")
            or payload.get("token", "")
        )
        ttl_seconds = int(payload.get("ttl_seconds", 3600))
        ttl_minutes = max(1, ttl_seconds // 60)
        return (
            f"PMIS password reset code: {code}. Expires in {ttl_minutes} "
            f"min. Don't share this code."
        )

    if template_kind == TEMPLATE_PASSWORD_RESET_LINK:
        # Reset-link via SMS isn't a sensible flow (the link is too
        # long), but keep a degraded fallback so the dispatch doesn't
        # crash if mis-configured.
        token = (
            payload.get("reset_token")
            or payload.get("token", "")
        )
        return f"PMIS password reset token: {token[:24]}..."

    logger.warning(
        "Unknown notification template_kind=%r; sending generic SMS.",
        template_kind,
    )
    return "You have a PMIS notification. Sign in for details."


class HttpNotificationClient(NotificationClient):
    """Production backend — talks to the PMIS-notification-service.

    Wire format (from service repo, dev branch):

      POST {NOTIFICATION_SERVICE_URL}/api/v1/notifications/email/send
      body: {"to":["x@y"], "subject":"...", "body":"...", "is_html": true}

      POST {NOTIFICATION_SERVICE_URL}/api/v1/notifications/sms/send
      body: {"to":"+91...", "message":"..."}

    The audit row is committed as ``queued`` first so we always have a
    record of what was attempted, even if the network call hangs or
    crashes. After the response we patch ``status`` to ``sent`` /
    ``failed`` and stash the provider + message_id (when returned) on
    the payload for later correlation.
    """

    def send(
        self,
        *,
        user_id: Optional[str],
        channel: str,
        recipient: str,
        template_kind: str,
        payload: Dict[str, Any],
    ) -> NotificationLogModel:
        row = NotificationLogModel(
            user_id=user_id,
            channel=channel,
            recipient=recipient,
            template_kind=template_kind,
            payload=payload,
            status="queued",
            error=None,
        )
        self.db.add(row)
        self.db.flush()
        self.db.commit()

        base_url = (settings.NOTIFICATION_SERVICE_URL or "").rstrip("/")
        if not base_url:
            # Misconfigured deploy: NOTIFICATION_CLIENT=http but no URL.
            # Don't crash the auth flow — log loud, leave the row
            # ``queued`` so ops can see the attempt, and return.
            err = (
                "NOTIFICATION_SERVICE_URL is not set; cannot dispatch "
                "via http backend."
            )
            logger.error(err)
            row.status = "failed"
            row.error = err
            self.db.flush()
            self.db.commit()
            return row

        try:
            if channel == CHANNEL_EMAIL:
                subject, body = _render_email(template_kind, payload)
                url = f"{base_url}/api/v1/notifications/email/send"
                req_body = {
                    "to": [recipient],
                    "subject": subject,
                    "body": body,
                    "is_html": True,
                }
            elif channel == CHANNEL_SMS:
                message = _render_sms(template_kind, payload)
                url = f"{base_url}/api/v1/notifications/sms/send"
                req_body = {"to": recipient, "message": message}
            else:
                err = f"Unsupported channel {channel!r}."
                logger.error(err)
                row.status = "failed"
                row.error = err
                self.db.flush()
                self.db.commit()
                return row

            with httpx.Client(
                timeout=httpx.Timeout(
                    connect=_HTTP_CONNECT_TIMEOUT,
                    read=_HTTP_READ_TIMEOUT,
                    write=_HTTP_READ_TIMEOUT,
                    pool=_HTTP_READ_TIMEOUT,
                )
            ) as client:
                resp = client.post(url, json=req_body)
        except httpx.HTTPError as e:
            err = f"notification HTTP error: {type(e).__name__}: {e}"
            logger.error(err)
            row.status = "failed"
            row.error = err
            self.db.flush()
            self.db.commit()
            return row
        except Exception as e:  # noqa: BLE001 — defensive
            err = f"notification dispatch crashed: {type(e).__name__}: {e}"
            logger.exception(err)
            row.status = "failed"
            row.error = err
            self.db.flush()
            self.db.commit()
            return row

        # Parse the response. The service returns
        #   {"success": bool, "message": str, "provider": str, "message_id": str?}
        # On non-2xx we still record what came back so investigators
        # can read the body.
        try:
            data = resp.json()
        except ValueError:
            data = {"success": False, "message": resp.text or "<no body>"}

        if 200 <= resp.status_code < 300 and data.get("success"):
            row.status = "sent"
            row.error = None
            # Stash provider + message_id on the audit payload for
            # correlation. Don't overwrite the original template
            # payload — merge under ``_dispatch``.
            new_payload = dict(payload)
            new_payload["_dispatch"] = {
                "provider": data.get("provider"),
                "message_id": data.get("message_id"),
                "service_message": data.get("message"),
            }
            row.payload = new_payload
        else:
            row.status = "failed"
            row.error = (
                f"http {resp.status_code} | "
                f"{data.get('message') or '<no message>'}"
            )
            new_payload = dict(payload)
            new_payload["_dispatch"] = {
                "http_status": resp.status_code,
                "service_response": data,
            }
            row.payload = new_payload

        self.db.flush()
        self.db.commit()
        return row


def get_notification_client(db: Session) -> NotificationClient:
    """Factory: pick the backend based on settings.

    Selection rules (first match wins):

      1. ``NOTIFICATION_CLIENT=mock`` — explicit opt-out → always mock.
         Used by the test suite via the ``mock_notification_client``
         autouse fixture so unit tests never hit a real service.
      2. ``NOTIFICATION_CLIENT=http`` — explicit opt-in → http.
      3. Empty / unset ``NOTIFICATION_CLIENT`` AND
         ``NOTIFICATION_SERVICE_URL`` is set → http (auto-detect).
         The presence of a service URL is a strong signal of intent —
         ops configured it, they want real dispatch. This is the
         common deployment path: the only env var operators have to
         set is the URL itself, which they need anyway.
      4. Otherwise → mock (safe default for fresh local dev).

    The auto-detect rule (#3) was added because ops kept setting
    ``NOTIFICATION_SERVICE_URL`` but forgetting ``NOTIFICATION_CLIENT``;
    OTPs would silently sink into ``notification_log`` instead of
    dispatching. With auto-detect, configuring the URL is enough.
    """
    backend = (settings.NOTIFICATION_CLIENT or "").strip().lower()
    has_url = bool((settings.NOTIFICATION_SERVICE_URL or "").strip())

    if backend == "mock":
        return MockNotificationClient(db)
    if backend == "http":
        return HttpNotificationClient(db)
    # No explicit setting — auto-detect by URL presence.
    if has_url:
        return HttpNotificationClient(db)
    return MockNotificationClient(db)
