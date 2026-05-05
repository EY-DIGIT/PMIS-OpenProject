"""Notification client (doc 33 change 3).

Two backends behind one ``NotificationClient`` interface:

- ``MockNotificationClient`` — writes to the ``notification_log`` table
  and returns. The terminal sink during dev/tests; never makes a real
  HTTP call. Inspecting the table reveals every notification that
  would have been sent, with the recipient, channel, and template kind.

- ``HttpNotificationClient`` — POSTs to the real notification
  microservice (https://github.com/EY-DIGIT/PMIS-notification-service).
  Stub implementation today: writes the same audit row first, then
  returns ``status="sent"`` without making the actual call (the real
  service isn't reachable yet). When the integration team wires the
  POST, replace the body with ``httpx.post(...)``.

Selection happens via the ``NOTIFICATION_CLIENT`` env var:
  - ``mock`` (default in dev/tests)
  - ``http`` (production once the service is reachable)

Construct via the factory ``get_notification_client(db)`` — it picks
the backend based on settings and hands back an instance bound to the
provided session. Callers don't need to know which backend won.

The audit row is the source of truth for "did the system attempt to
notify?" — both backends write one before any external call. If the
HTTP call fails, the row is updated to ``status="failed"`` with the
error message so investigations can see exactly what was tried.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..core.config import settings
from ..infrastructure.db.models.notification_log import NotificationLogModel


# Channel constants (kept as strings — short list, no enum overhead).
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"

# Template kinds.
TEMPLATE_OTP_LOGIN = "otp_login"
TEMPLATE_PASSWORD_RESET_LINK = "password_reset_link"
TEMPLATE_PASSWORD_RESET_OTP = "password_reset_otp"


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


class HttpNotificationClient(NotificationClient):
    """Production backend (stub).

    Writes the audit row as ``queued`` first, then would POST to the
    real microservice. Today the POST is a no-op — the service is not
    yet reachable. When integration goes live, replace the no-op block
    with the actual HTTP call and update ``status`` based on the
    response.
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

        # TODO(integration): when NOTIFICATION_SERVICE_URL is reachable,
        # POST {channel, recipient, template_kind, payload} to the
        # microservice and flip ``status`` to ``sent`` or ``failed``
        # based on the response. Today the row stays as ``queued`` —
        # so a deployed env with NOTIFICATION_CLIENT='http' but no
        # microservice still has a usable audit trail of what was meant
        # to be sent.

        return row


def get_notification_client(db: Session) -> NotificationClient:
    """Factory: pick the backend based on ``settings.NOTIFICATION_CLIENT``."""
    backend = (settings.NOTIFICATION_CLIENT or "mock").lower()
    if backend == "http":
        return HttpNotificationClient(db)
    # ``mock`` and any unknown value fall back to the mock — safer
    # default than crashing on misconfig.
    return MockNotificationClient(db)
