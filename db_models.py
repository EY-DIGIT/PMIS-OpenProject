"""
SQLAlchemy database models for User Service.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

try:
    from .database import Base
except ImportError:
    from database import Base


class DBUser(Base):
    """SQLAlchemy User model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(256), unique=True, nullable=False, index=True)
    firstname = Column(String(256))
    lastname = Column(String(256))
    mail = Column(String(256), unique=True, index=True)
    status = Column(Integer, default=1)  # 1=ACTIVE, 2=REGISTERED, 3=INVITED, 4=LOCKED, 5=DELETED
    admin = Column(Boolean, default=False)
    language = Column(String(10), default='en')

    # Authentication
    password_digest = Column(String(256))
    failed_login_count = Column(Integer, default=0)
    last_failed_login_on = Column(DateTime(timezone=True))
    force_password_change = Column(Boolean, default=False)
    last_login_on = Column(DateTime(timezone=True))

    # External auth
    ldap_auth_source_id = Column(Integer, nullable=True)
    uses_external_auth = Column(Boolean, default=False)
    identity_url = Column(String(512), nullable=True)

    # API tokens
    api_key = Column(String(256), unique=True, nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    preference = relationship("DBUserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    passwords = relationship("DBUserPassword", back_populates="user", cascade="all, delete-orphan")
    tokens = relationship("DBAPIToken", back_populates="user", cascade="all, delete-orphan")


class DBUserPreference(Base):
    """SQLAlchemy UserPreference model"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    timezone = Column(String(64), default='UTC')
    hide_mail = Column(Boolean, default=True)
    comments_sorting = Column(String(10), default='asc')
    warn_on_leaving_unsaved = Column(Boolean, default=True)
    theme = Column(String(50), default='default')
    notification_settings = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("DBUser", back_populates="preference")


class DBUserPassword(Base):
    """SQLAlchemy UserPassword model"""
    __tablename__ = "user_passwords"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hashed_password = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("DBUser", back_populates="passwords")


class DBAPIToken(Base):
    """SQLAlchemy API Token model"""
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(256), unique=True, nullable=False, index=True)
    name = Column(String(256))
    description = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("DBUser", back_populates="tokens")
