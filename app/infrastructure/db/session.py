"""
Database session management.
"""
from typing import Generator
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
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
class Base(DeclarativeBase):
    pass


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
    from .models import UserModel, ProjectModel, RoleModel, ProjectMemberModel, WorkPackageTypeModel, MeetingModel, MeetingParticipantModel, MeetingAgendaItemModel  # noqa: F401
    from ...core.security import hash_password
    from datetime import datetime, timezone
    
    Base.metadata.create_all(bind=engine)

    # SQLite schema drift handler: add missing nullable columns via ALTER TABLE
    # This runs only for SQLite and is idempotent. It MUST run before any
    # ORM queries that expect the new columns.
    try:
        from sqlalchemy import text
        import logging

        if engine.dialect.name == "sqlite":
            with engine.connect() as conn:
                try:
                    res = conn.execute(text("PRAGMA table_info('users')"))
                    rows = res.fetchall()
                    existing_cols = {r[1] for r in rows}  # PRAGMA cols: (cid,name,type,notnull,dflt_value,pk)

                    # Add refresh_token_jti if missing
                    if "refresh_token_jti" not in existing_cols:
                        try:
                            conn.execute(text("ALTER TABLE users ADD COLUMN refresh_token_jti VARCHAR(64)"))
                        except Exception as e:
                            logging.warning("Failed to add column refresh_token_jti: %s", e)

                    # Add refresh_token_expires_at if missing
                    if "refresh_token_expires_at" not in existing_cols:
                        try:
                            conn.execute(text("ALTER TABLE users ADD COLUMN refresh_token_expires_at DATETIME"))
                        except Exception as e:
                            logging.warning("Failed to add column refresh_token_expires_at: %s", e)
                except Exception:
                    # If PRAGMA fails for any reason, do not prevent app startup
                    pass
    except Exception:
        # Non-fatal: do not prevent application start on unexpected errors
        pass
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
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
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
            ("Activity", "activity"),
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
