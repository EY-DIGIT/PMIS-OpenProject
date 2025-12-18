"""
Database session management.
"""
from typing import Generator
import logging
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
    from .models import UserModel, ProjectModel, RoleModel, ProjectMemberModel, WorkPackageTypeModel  # noqa: F401
    from ...core.security import hash_password
    from datetime import datetime
    
    Base.metadata.create_all(bind=engine)
    # Development-only: detect SQLite schema drift for work_packages.type_id
    try:
        # Only run the drift-fix for SQLite to avoid impacting other DBs
        if engine.dialect.name == "sqlite":
            from sqlalchemy import inspect
            inspector = inspect(engine)
            if inspector.has_table("work_packages"):
                cols = [c["name"] for c in inspector.get_columns("work_packages")]
                if "type_id" not in cols:
                    logging.warning("Schema drift detected for work_packages, recreating table (dev-only)")
                    # Import model and drop the specific table, then recreate schema
                    from .models import WorkPackageModel

                    try:
                        WorkPackageModel.__table__.drop(bind=engine)
                    except Exception:
                        # Drop may fail if the table is locked or already removed; ignore in dev
                        pass

                    Base.metadata.create_all(bind=engine)
    except Exception:
        # Do not prevent application start for any unexpected inspector errors
        pass
    
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

    # Ensure builtin work package types exist (idempotent)
    db = SessionLocal()
    try:
        # Import repository here to avoid circular imports at module level
        from .repositories import WorkPackageTypeRepository

        type_repo = WorkPackageTypeRepository(db)
        builtin_types = [
            ("Task", "task"),
            ("Bug", "bug"),
            ("Feature", "feature"),
            ("Story", "story"),
            ("Milestone", "milestone"),
        ]

        for pos, (name, internal) in enumerate(builtin_types, start=1):
            try:
                if not type_repo.exists_by_internal_name(internal):
                    type_repo.create(
                        name=name,
                        internal_name=internal,
                        is_builtin=True,
                        is_active=True,
                        position=pos,
                    )
            except Exception:
                # Do not raise on bootstrap failures; log could be added
                pass
    finally:
        db.close()
