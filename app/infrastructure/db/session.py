"""
Database session management.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from ...core.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.DEBUG
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Get database session.

    Yields:
        Database session

    Usage:
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database (create tables).
    
    Imports models to register them with Base before creating tables.
    Creates a default admin user if none exists (idempotent).
    """
    # Import models here to avoid circular imports
    # This ensures models are registered with Base before table creation
    from .models import UserModel, ProjectModel, RoleModel, ProjectMemberModel  # noqa: F401
    from ...core.security import hash_password
    from datetime import datetime
    
    Base.metadata.create_all(bind=engine)
    
    # Idempotent admin bootstrap: create admin only if no users exist
    db = SessionLocal()
    try:
        admin_exists = db.query(UserModel).filter(
            UserModel.login == "admin"
        ).first()
        
        if not admin_exists:
            # Create default admin user (only on first run)
            admin_user = UserModel(
                login="admin",
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                first_name="Administrator",
                last_name="System",
                admin=True,
                status="active",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(admin_user)
            db.commit()
    finally:
        db.close()
