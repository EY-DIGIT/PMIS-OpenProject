"""
User database model.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from ..session import Base


class UserModel(Base):
    """User database model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    login = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    admin = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    # Refresh token tracking for stateless rotation
    refresh_token_jti = Column(String(64), nullable=True, index=False)
    refresh_token_expires_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_users_login", "login"),
        Index("idx_users_email", "email"),
        Index("idx_users_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, login='{self.login}', email='{self.email}')>"
