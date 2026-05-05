"""
Core configuration module.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class Settings(BaseSettings):
    """Application settings."""
    model_config = ConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Application
    APP_NAME: str = "PMIS API"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production-minimum-32-characters-long",
        description="Secret key for JWT encoding"
    )
    ALGORITHM: str = "HS256"
    # Access token TTL (minutes) - 15 minutes per token rules
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    # Refresh token TTL (days)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Grace window (seconds) during which the just-rotated-out refresh token
    # is still accepted by /users/refresh. Lets concurrent refresh attempts
    # (timer + 401 interceptor firing in parallel, multi-tab races, retry
    # queues holding a stale token) succeed instead of returning 401. The
    # previous jti is recorded on every rotation event (login or refresh)
    # and remains valid for this many seconds.
    REFRESH_TOKEN_GRACE_SECONDS: int = 120

    # Doc 24 part 2: optional cap on subtask nesting depth. ``None`` (the
    # default) means unlimited — set via env to a small int (e.g. 50) if a
    # specific deployment wants to bound the recursion / label length.
    # Depth = number of subtask ancestors above the new row (top-level
    # subtask = depth 1). The check rejects ``create_subtask`` calls that
    # would exceed the cap.
    SUBTASK_MAX_NESTING_DEPTH: Optional[int] = None

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./pmis.db",
        description="Database connection URL"
    )

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Bootstrap admin — only inserted on first boot when no admin user
    # exists. Idempotent: subsequent boots check for existence and skip.
    BOOTSTRAP_ADMIN_LOGIN: str = "admin"
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@example.com"
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin123"

    # ---- File attachments (Comments & Attachments feature) ----
    #
    # All values are env-driven so they can change per environment without
    # code redeploys. In production the base path points at an NFS-mounted
    # folder (the OS handles the mount; the app just reads/writes it). In
    # local dev it's a plain folder under the repo root.
    #
    # The NFS server / export are informational only — they're surfaced in
    # /health and boot logs so ops can confirm which file store is in use,
    # but the app NEVER connects to them directly. The OS-level mount does.

    # Local mount point / dev folder where attachment bytes live.
    ATTACHMENTS_STORAGE_BASE_PATH: str = Field(
        default="./local_uploads",
        description=(
            "Filesystem path where attachment bytes are stored. In prod this "
            "is the NFS mount point (e.g. /mnt/pmis_files). In dev it's a "
            "local folder. Created at startup if missing."
        ),
    )

    # Per-file size cap. 25 MB matches the frontend design's client-side limit.
    ATTACHMENTS_MAX_BYTES: int = Field(
        default=26214400,  # 25 MiB
        description="Maximum size per uploaded file in bytes.",
    )

    # Comma-separated list of allowed file extensions (case-insensitive,
    # leading dots optional). Sniffed against the ACTUAL filename suffix —
    # we do NOT trust the client's Content-Type header.
    ATTACHMENTS_ALLOWED_EXTENSIONS: str = Field(
        default="pdf,doc,docx,xls,xlsx,ppt,pptx,txt,csv,png,jpg,jpeg,gif,webp",
        description="Comma-separated allowed file extensions (no leading dots).",
    )

    # Subdirectory layout under the base path. Options:
    #   "year_month"  → attachments/2026/04/{uuid}_{name}    (recommended)
    #   "flat"        → attachments/{uuid}_{name}            (small scale only)
    ATTACHMENTS_SUBDIR_STRATEGY: str = Field(
        default="year_month",
        description="Subdirectory strategy: 'year_month' or 'flat'.",
    )

    # Days after a soft-delete before the actual file bytes are purged by
    # the (future) cleanup cron. Metadata row stays forever.
    ATTACHMENTS_RETENTION_DAYS: int = Field(
        default=90,
        description="Days to keep file bytes after soft-delete before purge.",
    )

    # Behaviour when the storage path is unreachable / not mounted.
    #   "fail"  → upload/download endpoints return 503 (recommended)
    ATTACHMENTS_ON_UNAVAILABLE: str = Field(
        default="fail",
        description="What to do when storage is unreachable: 'fail'.",
    )

    # Informational only — surfaced in /health and boot logs. The app
    # itself never connects to the NFS server; the OS mount does.
    ATTACHMENTS_NFS_SERVER: str = Field(
        default="",
        description="NFS server address (informational; for /health only).",
    )
    ATTACHMENTS_NFS_EXPORT: str = Field(
        default="",
        description="NFS export path (informational; for /health only).",
    )

    # ---- Doc 33 change 3: 2FA OTP + forgot-password ----

    # Whether 2FA is mandatory by default. When True (the default per
    # Q3a.4), every user is forced through the OTP flow at login. Admins
    # can opt individual users OUT via PATCH /users/{id} setting
    # ``twoFactorEnabled=false``. Set this env var to False to disable
    # 2FA entirely for the deployment (e.g. local dev).
    REQUIRE_2FA: bool = Field(
        default=True,
        description="Require 2FA at login by default. Per-user override allowed.",
    )

    # OTP code TTL in seconds. Default 5 minutes — long enough for a
    # user to receive an SMS and type it in, short enough to limit
    # brute-force window.
    OTP_TTL_SECONDS: int = Field(
        default=300,
        description="How long an OTP stays valid (seconds).",
    )

    # Cooldown between resends. Prevents notification spam + locks out
    # automated abuse. Default 60s.
    OTP_RESEND_COOLDOWN_SECONDS: int = Field(
        default=60,
        description="Min seconds between OTP send / resend per ephemeral session.",
    )

    # Max wrong-code attempts before the OTP row is invalidated. Default 5.
    OTP_MAX_ATTEMPTS: int = Field(
        default=5,
        description="Max wrong-code attempts before the OTP is invalidated.",
    )

    # OTP code length (digits). Default 6.
    OTP_CODE_LENGTH: int = Field(
        default=6,
        description="Number of digits in an OTP code.",
    )

    # Server-side pepper added to OTP / reset-token hashes. Combined with
    # SECRET_KEY ensures DB readers cannot regenerate active codes from
    # the stored hash alone.
    OTP_HASH_PEPPER: str = Field(
        default="",
        description="Server-side pepper for OTP hashing. Defaults to SECRET_KEY when blank.",
    )

    # Forgot-password reset-token TTL (seconds). Default 1 hour.
    PASSWORD_RESET_TTL_SECONDS: int = Field(
        default=3600,
        description="How long a password-reset token stays valid (seconds).",
    )

    # Notification client backend. ``mock`` writes to the
    # notification_log table for inspection during dev/tests; ``http``
    # POSTs to the real notification microservice (stub until the
    # service is reachable).
    NOTIFICATION_CLIENT: str = Field(
        default="mock",
        description="Notification client: 'mock' (DB log) or 'http' (real microservice).",
    )

    # Real notification microservice base URL — used when
    # NOTIFICATION_CLIENT='http'. The service surface is documented at
    # https://github.com/EY-DIGIT/PMIS-notification-service.
    NOTIFICATION_SERVICE_URL: str = Field(
        default="",
        description="Base URL of the notification microservice (HTTP backend).",
    )


settings = Settings()
