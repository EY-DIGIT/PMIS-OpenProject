"""doc 36: notification_templates table + divisions.email/phone NOT NULL

Revision ID: c2d4e7f9a1b3
Revises: b8c9d0e1f2a3
Create Date: 2026-05-06

Two coordinated changes:

1. **DB-backed notification templates**
   - Create ``notification_templates`` table — id, template_kind,
     channel, subject, body, is_html, is_builtin, active,
     description, created_at, updated_at.
   - Insert the six seed rows (3 kinds × 2 channels) with the same
     copy the pre-doc-36 hardcoded renderer used to produce, marked
     ``is_builtin=True``.
   - Composite index ``(template_kind, channel, active)`` for the
     hot lookup. Postgres also gets a partial unique index on
     ``(template_kind, channel) WHERE active`` so the at-most-one-
     active-row-per-pair invariant the renderer relies on is enforced
     at the DB level. SQLite skips the partial unique (use the
     service-layer guard in the routes — SQLite-3 only got partial
     unique support in 3.8.0 and the syntax is awkward via alembic).

2. **Divisions contact details required**
   - Backfill any NULL ``divisions.email`` / ``divisions.phone_number``
     rows with env-driven defaults (``DIVISION_DEFAULT_EMAIL`` /
     ``DIVISION_DEFAULT_PHONE``, fallback to ``ops@pmis.example`` /
     ``+910000000000`` when the env vars aren't set on the migration
     runner).
   - Flip both columns to NOT NULL.

Idempotent — every step checks current state before acting so
re-running against an already-migrated DB is a no-op.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d4e7f9a1b3"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, name: str) -> bool:
    return name in set(inspector.get_table_names())


def _has_column(inspector, table: str, column: str) -> bool:
    if not _has_table(inspector, table):
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _column_is_nullable(inspector, table: str, column: str) -> bool:
    for c in inspector.get_columns(table):
        if c["name"] == column:
            return bool(c.get("nullable", True))
    return True


# Seed rows — same copy as the pre-doc-36 hardcoded renderer in
# app/shared/notifications.py. Kept in sync with the init_db seed loop;
# the migration handles fresh-install case (initial deploy of doc 36),
# init_db handles subsequent boots (idempotent fill of missing rows).
_SEED_ROWS = (
    {
        "template_kind": "otp_login",
        "channel": "email",
        "subject": "Your PMIS login verification code",
        "body": (
            "<p>Your PMIS login verification code is:</p>"
            "<p style='font-size:22px;font-weight:600;letter-spacing:3px'>{code}</p>"
            "<p>This code expires in {ttl_minutes} minutes. If you didn't try "
            "to log in, you can ignore this email.</p>"
        ),
        "is_html": True,
        "description": "Sent on every successful 2FA login attempt (email channel).",
    },
    {
        "template_kind": "otp_login",
        "channel": "sms",
        "subject": None,
        "body": (
            "PMIS login code: {code}. Expires in {ttl_minutes} min. "
            "Don't share this code."
        ),
        "is_html": False,
        "description": "Sent on every successful 2FA login attempt (SMS channel).",
    },
    {
        "template_kind": "password_reset_link",
        "channel": "email",
        "subject": "PMIS password reset",
        "body": (
            "<p>You (or someone) requested a password reset for your "
            "PMIS account. Click the link below to set a new "
            "password:</p>"
            "<p><a href='{reset_url}'>Reset your PMIS password</a></p>"
            "<p>If the link doesn't work, paste this URL into your "
            "browser:</p>"
            "<p style='font-family:monospace;word-break:break-all'>{reset_url}</p>"
            "<p>Or use this single-use token directly:</p>"
            "<p style='font-family:monospace;word-break:break-all'>{token}</p>"
            "<p>The link expires in {ttl_minutes} minutes. If you "
            "didn't request a reset, you can ignore this email.</p>"
        ),
        "is_html": True,
        "description": (
            "Sent on POST /users/forgot-password with channel=email. "
            "{reset_url} is computed from FRONTEND_BASE_URL + token; "
            "{token} is always available as a fallback when "
            "FRONTEND_BASE_URL is unset."
        ),
    },
    {
        "template_kind": "password_reset_link",
        "channel": "sms",
        "subject": None,
        "body": "PMIS password reset token: {token}. Expires in {ttl_minutes} min.",
        "is_html": False,
        "description": (
            "Degraded SMS fallback for the link channel — URLs render "
            "poorly in SMS, so the token is sent as text. The "
            "password_reset_otp template is the preferred SMS flow."
        ),
    },
    {
        "template_kind": "password_reset_otp",
        "channel": "email",
        "subject": "PMIS password reset code",
        "body": (
            "<p>Your PMIS password reset code is:</p>"
            "<p style='font-size:22px;font-weight:600;letter-spacing:3px'>{code}</p>"
            "<p>This code expires in {ttl_minutes} minutes. If you didn't "
            "request a reset, you can ignore this email.</p>"
        ),
        "is_html": True,
        "description": "Email variant of the OTP-style password reset.",
    },
    {
        "template_kind": "password_reset_otp",
        "channel": "sms",
        "subject": None,
        "body": (
            "PMIS password reset code: {code}. Expires in {ttl_minutes} "
            "min. Don't share this code."
        ),
        "is_html": False,
        "description": "Sent on POST /users/forgot-password with channel=sms.",
    },
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    # ----------------------------------------------------------------
    # 1. notification_templates table
    # ----------------------------------------------------------------
    if not _has_table(inspector, "notification_templates"):
        op.create_table(
            "notification_templates",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("template_kind", sa.String(length=64), nullable=False, index=True),
            sa.Column("channel", sa.String(length=16), nullable=False, index=True),
            sa.Column("subject", sa.String(length=500), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_html", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
            sa.Column("description", sa.String(length=1024), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        # Composite index for the renderer's hot lookup.
        op.create_index(
            "idx_notification_templates_kind_channel_active",
            "notification_templates",
            ["template_kind", "channel", "active"],
            unique=False,
        )
        # Postgres-only partial unique index — at most one active row
        # per (kind, channel). The service layer enforces the same
        # invariant on SQLite.
        if dialect == "postgresql":
            op.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_notification_templates_kind_channel_active "
                "ON notification_templates (template_kind, channel) "
                "WHERE active = TRUE"
            )

    # Seed rows (idempotent — only inserts what's missing, matched by
    # the (template_kind, channel) pair).
    for spec in _SEED_ROWS:
        existing = bind.execute(
            sa.text(
                "SELECT id FROM notification_templates "
                "WHERE template_kind = :kind AND channel = :channel"
            ),
            {"kind": spec["template_kind"], "channel": spec["channel"]},
        ).fetchone()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO notification_templates "
                    "(template_kind, channel, subject, body, is_html, "
                    " is_builtin, active, description, created_at, updated_at) "
                    "VALUES (:kind, :channel, :subject, :body, :is_html, "
                    " TRUE, TRUE, :description, "
                    f" {('CURRENT_TIMESTAMP' if dialect != 'sqlite' else 'CURRENT_TIMESTAMP')}, "
                    f" {('CURRENT_TIMESTAMP' if dialect != 'sqlite' else 'CURRENT_TIMESTAMP')})"
                ),
                {
                    "kind": spec["template_kind"],
                    "channel": spec["channel"],
                    "subject": spec["subject"],
                    "body": spec["body"],
                    "is_html": spec["is_html"],
                    "description": spec["description"],
                },
            )

    # ----------------------------------------------------------------
    # 2. Divisions: backfill NULL contact details, then flip NOT NULL.
    # ----------------------------------------------------------------
    if _has_table(inspector, "divisions"):
        # Pull defaults from settings if importable; fall back to
        # hardcoded placeholders so the migration runs in CI / fresh
        # environments where the env vars aren't set.
        try:
            from app.core.config import settings  # type: ignore
            div_email = (settings.DIVISION_DEFAULT_EMAIL or "ops@pmis.example").strip()
            div_phone = (settings.DIVISION_DEFAULT_PHONE or "+910000000000").strip()
        except Exception:
            div_email = "ops@pmis.example"
            div_phone = "+910000000000"

        # Backfill NULL/empty values.
        bind.execute(
            sa.text(
                "UPDATE divisions SET email = :email "
                "WHERE email IS NULL OR TRIM(email) = ''"
            ),
            {"email": div_email},
        )
        bind.execute(
            sa.text(
                "UPDATE divisions SET phone_number = :phone "
                "WHERE phone_number IS NULL OR TRIM(phone_number) = ''"
            ),
            {"phone": div_phone},
        )

        # Flip both columns to NOT NULL. Use batch_alter_table for SQLite
        # (which doesn't support ALTER COLUMN in-place); native ALTER on
        # Postgres.
        if dialect == "postgresql":
            if _column_is_nullable(inspector, "divisions", "email"):
                op.alter_column("divisions", "email", nullable=False)
            if _column_is_nullable(inspector, "divisions", "phone_number"):
                op.alter_column("divisions", "phone_number", nullable=False)
        else:
            # SQLite path. batch_alter_table rebuilds the table.
            with op.batch_alter_table("divisions") as batch_op:
                if _column_is_nullable(inspector, "divisions", "email"):
                    batch_op.alter_column(
                        "email",
                        existing_type=sa.String(length=255),
                        nullable=False,
                    )
                if _column_is_nullable(inspector, "divisions", "phone_number"):
                    batch_op.alter_column(
                        "phone_number",
                        existing_type=sa.String(length=50),
                        nullable=False,
                    )


def downgrade() -> None:
    """Reverse both halves.

    1. Drop the notification_templates table (and its indexes).
    2. Flip divisions.email / phone_number back to nullable. Existing
       row values are preserved — they're still usable, just not
       enforced on new inserts.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    # 2. Flip divisions back to nullable.
    if _has_table(inspector, "divisions"):
        if dialect == "postgresql":
            if not _column_is_nullable(inspector, "divisions", "email"):
                op.alter_column("divisions", "email", nullable=True)
            if not _column_is_nullable(inspector, "divisions", "phone_number"):
                op.alter_column("divisions", "phone_number", nullable=True)
        else:
            with op.batch_alter_table("divisions") as batch_op:
                if not _column_is_nullable(inspector, "divisions", "email"):
                    batch_op.alter_column(
                        "email",
                        existing_type=sa.String(length=255),
                        nullable=True,
                    )
                if not _column_is_nullable(inspector, "divisions", "phone_number"):
                    batch_op.alter_column(
                        "phone_number",
                        existing_type=sa.String(length=50),
                        nullable=True,
                    )

    # 1. Drop notification_templates.
    if _has_table(inspector, "notification_templates"):
        if dialect == "postgresql":
            op.execute(
                "DROP INDEX IF EXISTS "
                "uq_notification_templates_kind_channel_active"
            )
        # The composite non-unique index gets dropped along with the table.
        op.drop_table("notification_templates")
