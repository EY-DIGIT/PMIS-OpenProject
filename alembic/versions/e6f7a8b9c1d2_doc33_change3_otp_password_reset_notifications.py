"""Doc 33 change 3: 2FA OTP + forgot-password + notification log tables.

Revision ID: e6f7a8b9c1d2
Revises: d5e6f7a8b9c1
Create Date: 2026-05-05 21:00:00

Adds three tables backing the doc 33 change 3 features:

  - ``otp_codes`` — login 2FA: hashed OTP rows keyed on an ephemeral
    session token. Single-use semantics.
  - ``password_reset_tokens`` — self-service password reset: hashed
    URL token (email channel) or hashed numeric OTP (SMS channel).
  - ``notification_log`` — every dispatched notification recorded
    here regardless of which backend (mock / http) sent it. Audit
    trail for "did the system attempt to notify?".

Plus the ``users.two_factor_enabled`` column (default True per Q3a.4 —
mandatory by default with admin override) and a follow-up update that
sets the column to True for every existing row (NOT NULL constraint
needs a value).

Down revision is structural — drops the tables and the column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c1d2"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- users.two_factor_enabled ---------------------------------------
    # Add as nullable first, backfill, then mark NOT NULL.
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("two_factor_enabled", sa.Boolean(), nullable=True))
    op.execute("UPDATE users SET two_factor_enabled = 1 WHERE two_factor_enabled IS NULL")
    with op.batch_alter_table("users") as b:
        b.alter_column(
            "two_factor_enabled",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        )

    # ---- notification_log -----------------------------------------------
    op.create_table(
        "notification_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("template_kind", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notification_log_user_id", "notification_log", ["user_id"])
    op.create_index("ix_notification_log_channel", "notification_log", ["channel"])
    op.create_index("ix_notification_log_template_kind", "notification_log", ["template_kind"])
    op.create_index("ix_notification_log_status", "notification_log", ["status"])
    op.create_index("idx_notification_log_user_id_kind", "notification_log", ["user_id", "template_kind"])
    op.create_index("idx_notification_log_created_at", "notification_log", ["created_at"])

    # ---- otp_codes ------------------------------------------------------
    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("ephemeral_token_hash", sa.String(128), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sent_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_otp_codes_user_id", "otp_codes", ["user_id"])
    op.create_index("ix_otp_codes_ephemeral_token_hash", "otp_codes", ["ephemeral_token_hash"])
    op.create_index("ix_otp_codes_expires_at", "otp_codes", ["expires_at"])
    op.create_index("ix_otp_codes_consumed_at", "otp_codes", ["consumed_at"])
    op.create_index("idx_otp_codes_user_id_active", "otp_codes", ["user_id", "consumed_at"])

    # ---- password_reset_tokens -----------------------------------------
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column(
            "token_hash", sa.String(128), nullable=False, unique=True,
        ),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])
    op.create_index("ix_password_reset_tokens_consumed_at", "password_reset_tokens", ["consumed_at"])
    op.create_index("idx_password_reset_tokens_user_id_active", "password_reset_tokens", ["user_id", "consumed_at"])


def downgrade() -> None:
    op.drop_index("idx_password_reset_tokens_user_id_active", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_consumed_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    op.drop_index("idx_otp_codes_user_id_active", table_name="otp_codes")
    op.drop_index("ix_otp_codes_consumed_at", table_name="otp_codes")
    op.drop_index("ix_otp_codes_expires_at", table_name="otp_codes")
    op.drop_index("ix_otp_codes_ephemeral_token_hash", table_name="otp_codes")
    op.drop_index("ix_otp_codes_user_id", table_name="otp_codes")
    op.drop_table("otp_codes")

    op.drop_index("idx_notification_log_created_at", table_name="notification_log")
    op.drop_index("idx_notification_log_user_id_kind", table_name="notification_log")
    op.drop_index("ix_notification_log_status", table_name="notification_log")
    op.drop_index("ix_notification_log_template_kind", table_name="notification_log")
    op.drop_index("ix_notification_log_channel", table_name="notification_log")
    op.drop_index("ix_notification_log_user_id", table_name="notification_log")
    op.drop_table("notification_log")

    with op.batch_alter_table("users") as b:
        b.drop_column("two_factor_enabled")
