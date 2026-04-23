"""
Core configuration module.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class Settings(BaseSettings):
    """Application settings."""
    model_config = ConfigDict(env_file=".env", case_sensitive=True)

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


settings = Settings()
