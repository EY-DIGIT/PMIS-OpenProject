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
    from .models import (  # noqa: F401
        UserModel, ProjectModel, ProjectAuditLogModel, RoleModel, ProjectMemberModel,
        ProjectVendorModel, MilestoneVendorModel, VendorModel, ResourceTypeModel,
        WorkPackageModel, WorkPackageTypeModel, MeetingModel, MeetingParticipantModel,
        MeetingAgendaItemModel,
        MilestoneModel, ActivityModel, ActivityResourceModel,
        TaskModel, TaskResourceModel, SubtaskModel, SubtaskResourceModel,
    )
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

                # projects: add new columns for versioning, audit, and soft-delete
                # on databases that were created before these columns existed.
                try:
                    res = conn.execute(text("PRAGMA table_info('projects')"))
                    project_cols = {r[1] for r in res.fetchall()}

                    # projects.id is now a UUID (String(36)) and there is no
                    # separate uuid column. Schema changes of this magnitude
                    # (PK type change, FK type changes) cannot be applied
                    # in-place on SQLite without a full table rebuild; for dev
                    # we wipe pmis.db and let create_all() build fresh.
                    #
                    # The list below continues to add columns that predate
                    # *other* migrations (for teammate's versioning/audit
                    # work). All NEW additions tied to the UUID migration are
                    # expressed in the SQLAlchemy models themselves.
                    project_column_ddl = [
                        ("actual_end_date",   "ALTER TABLE projects ADD COLUMN actual_end_date DATETIME"),
                        ("is_version",        "ALTER TABLE projects ADD COLUMN is_version BOOLEAN NOT NULL DEFAULT 0"),
                        ("version_no",        "ALTER TABLE projects ADD COLUMN version_no INTEGER"),
                        ("created_by",        "ALTER TABLE projects ADD COLUMN created_by INTEGER REFERENCES users(id)"),
                        ("updated_by",        "ALTER TABLE projects ADD COLUMN updated_by INTEGER REFERENCES users(id)"),
                        ("deleted_at",        "ALTER TABLE projects ADD COLUMN deleted_at DATETIME"),
                        ("deleted_by",        "ALTER TABLE projects ADD COLUMN deleted_by INTEGER REFERENCES users(id)"),
                        ("project_code",      "ALTER TABLE projects ADD COLUMN project_code VARCHAR(30)"),
                        # NEW: free-text label when category == 'others'.
                        ("category_other",    "ALTER TABLE projects ADD COLUMN category_other VARCHAR(255)"),
                    ]
                    for col, ddl in project_column_ddl:
                        if col not in project_cols:
                            try:
                                conn.execute(text(ddl))
                            except Exception as e:
                                logging.warning("Failed to add projects.%s: %s", col, e)

                    # Unique index for project_code (safe on re-run).
                    try:
                        conn.execute(text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_project_code "
                            "ON projects(project_code)"
                        ))
                    except Exception as e:
                        logging.warning("Failed to create idx_projects_project_code: %s", e)

                    # Partial unique index enforcing "one active version per baseline".
                    # Active = is_version AND status != 'suspended' AND not soft-deleted.
                    try:
                        conn.execute(text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS "
                            "ux_projects_active_version_per_baseline "
                            "ON projects(version_of) "
                            "WHERE is_version = 1 AND status != 'suspended' AND deleted_at IS NULL"
                        ))
                    except Exception as e:
                        logging.warning("Failed to create ux_projects_active_version_per_baseline: %s", e)
                except Exception:
                    pass

                # activities / tasks / subtasks: add resource_mode + resource_count
                # columns on databases created before these columns existed. One-time
                # backfill: existing type='resource' rows with a live resource row are
                # assumed to be 'details' mode.
                #
                # Mapping: (main_table, resource_table, fk_column_in_resource_table)
                for main_table, resource_table, fk_col in (
                    ("activities", "activity_resources", "activity_id"),
                    ("tasks",      "task_resources",     "task_id"),
                    ("subtasks",   "subtask_resources",  "subtask_id"),
                ):
                    try:
                        res = conn.execute(text(f"PRAGMA table_info('{main_table}')"))
                        cols = {r[1] for r in res.fetchall()}
                    except Exception:
                        # Main table does not yet exist (first boot); create_all
                        # will make it and the columns will be present already.
                        continue

                    ddl = [
                        ("resource_mode",  f"ALTER TABLE {main_table} ADD COLUMN resource_mode VARCHAR(10)"),
                        ("resource_count", f"ALTER TABLE {main_table} ADD COLUMN resource_count INTEGER"),
                    ]
                    for col, stmt in ddl:
                        if col not in cols:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                logging.warning("Failed to add %s.%s: %s", main_table, col, e)

                    # Backfill: any legacy type='resource' row that still has a
                    # live entry in its resource_table must be 'details' mode.
                    # Leaves resource_mode=NULL on any non-resource rows (correct).
                    try:
                        conn.execute(text(f"""
                            UPDATE {main_table}
                               SET resource_mode = 'details'
                             WHERE type = 'resource'
                               AND resource_mode IS NULL
                               AND id IN (
                                   SELECT {fk_col} FROM {resource_table}
                                    WHERE deleted_at IS NULL
                               )
                        """))
                    except Exception as e:
                        logging.warning("Failed to backfill %s.resource_mode: %s", main_table, e)

                # ---- NEW: milestones.status + milestones.depends ---------
                try:
                    res = conn.execute(text("PRAGMA table_info('milestones')"))
                    mcols = {r[1] for r in res.fetchall()}
                    for col, stmt in (
                        ("status",         "ALTER TABLE milestones ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'not_completed'"),
                        ("depends",        "ALTER TABLE milestones ADD COLUMN depends TEXT"),
                        # Lineage pointer for baseline → version propagation.
                        ("cloned_from_id", "ALTER TABLE milestones ADD COLUMN cloned_from_id VARCHAR(36) REFERENCES milestones(id)"),
                    ):
                        if col not in mcols:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                logging.warning("Failed to add milestones.%s: %s", col, e)
                    try:
                        conn.execute(text(
                            "CREATE INDEX IF NOT EXISTS ix_milestones_cloned_from_id "
                            "ON milestones(cloned_from_id)"
                        ))
                    except Exception as e:
                        logging.warning("Failed to create ix_milestones_cloned_from_id: %s", e)
                except Exception:
                    pass

                # ---- NEW: activities.status + activities.dependency ------
                try:
                    res = conn.execute(text("PRAGMA table_info('activities')"))
                    acols = {r[1] for r in res.fetchall()}
                    for col, stmt in (
                        ("status",         "ALTER TABLE activities ADD COLUMN status VARCHAR(32)"),
                        ("dependency",     "ALTER TABLE activities ADD COLUMN dependency TEXT"),
                        # Lineage pointer for baseline → version propagation.
                        ("cloned_from_id", "ALTER TABLE activities ADD COLUMN cloned_from_id VARCHAR(36) REFERENCES activities(id)"),
                    ):
                        if col not in acols:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                logging.warning("Failed to add activities.%s: %s", col, e)
                    try:
                        conn.execute(text(
                            "CREATE INDEX IF NOT EXISTS ix_activities_cloned_from_id "
                            "ON activities(cloned_from_id)"
                        ))
                    except Exception as e:
                        logging.warning("Failed to create ix_activities_cloned_from_id: %s", e)
                except Exception:
                    pass

                # ---- NEW: activity_resources classification columns ------
                try:
                    res = conn.execute(text("PRAGMA table_info('activity_resources')"))
                    arcols = {r[1] for r in res.fetchall()}
                    for col, stmt in (
                        ("type_of_resource_id", "ALTER TABLE activity_resources ADD COLUMN type_of_resource_id VARCHAR(36) REFERENCES resource_types(id)"),
                        ("division",            "ALTER TABLE activity_resources ADD COLUMN division VARCHAR(32)"),
                        ("division_other",      "ALTER TABLE activity_resources ADD COLUMN division_other VARCHAR(255)"),
                    ):
                        if col not in arcols:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                logging.warning("Failed to add activity_resources.%s: %s", col, e)
                except Exception:
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

    # Seed resource_types catalog (idempotent).
    db = SessionLocal()
    try:
        from .repositories import ResourceTypeRepository
        from ...domain.resource_types.resource_type import RESOURCE_TYPE_SEED

        rt_repo = ResourceTypeRepository(db)
        for code, name in RESOURCE_TYPE_SEED:
            try:
                if not rt_repo.exists_by_code(code):
                    rt_repo.create(code=code, name=name, active=True)
            except Exception:
                pass
        db.commit()
    finally:
        db.close()

    # Seed a few demo vendors so the frontend has something to render on first
    # run. Remove or replace with real vendor data when vendor management
    # flows land.
    db = SessionLocal()
    try:
        from .repositories import VendorRepository

        v_repo = VendorRepository(db)
        for name in ("Infosys", "TCS", "Wipro", "Accenture", "Capgemini"):
            try:
                if v_repo.get_by_name(name) is None:
                    v_repo.create(name=name, active=True)
            except Exception:
                pass
        db.commit()
    finally:
        db.close()
