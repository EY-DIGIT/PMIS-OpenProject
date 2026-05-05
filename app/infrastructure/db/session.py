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


def _heal_sqlite_column_drift(conn, metadata) -> list:
    """Generic auto-healer: add any model column missing from the SQLite DB.

    Iterates ``metadata.tables`` and, for each table that already exists,
    compares the model's columns against the actual table's columns via
    PRAGMA. Missing columns are added with ``ALTER TABLE ADD COLUMN``,
    using the SQLAlchemy column's compiled type and (when present) its
    default. NOT NULL columns are skipped unless they have a default,
    because SQLite can't add a NOT NULL column without a default.

    Returns the list of ``(table.column)`` strings that were added (for
    logging/tests). No-op on non-SQLite dialects.

    This is a defensive backstop — explicit ALTER blocks above this still
    run first (and handle index creation, partial-index DDL, etc.). This
    pass catches columns that landed in a model after the explicit blocks
    were last hand-maintained, so the next post-doc-N feature drop doesn't
    silently break the SQLite dev environment.
    """
    from sqlalchemy import text
    from sqlalchemy.schema import CreateColumn

    added: list = []
    dialect = conn.dialect
    if dialect.name != "sqlite":
        return added

    for table in metadata.sorted_tables:
        try:
            res = conn.execute(text(f"PRAGMA table_info('{table.name}')"))
            existing = {r[1] for r in res.fetchall()}
        except Exception:
            # Table doesn't exist yet; create_all will build it.
            continue
        if not existing:
            continue

        for column in table.columns:
            if column.name in existing:
                continue
            # SQLite can't add a NOT NULL column without a default value.
            # Skip those — they'd need a manual data-migration plan.
            has_default = column.default is not None or column.server_default is not None
            if not column.nullable and not has_default:
                logging.warning(
                    "Cannot auto-heal %s.%s on SQLite: column is NOT NULL "
                    "without a default. Add an explicit ALTER above.",
                    table.name, column.name,
                )
                continue
            try:
                # Compile the column DDL fragment (type + nullability +
                # default) for the active dialect, then wrap it in
                # ALTER TABLE ADD COLUMN.
                ddl_fragment = str(
                    CreateColumn(column).compile(dialect=dialect)
                )
                conn.execute(text(
                    f"ALTER TABLE {table.name} ADD COLUMN {ddl_fragment}"
                ))
                added.append(f"{table.name}.{column.name}")
                logging.info(
                    "Auto-healed SQLite drift: added %s.%s",
                    table.name, column.name,
                )
            except Exception as e:
                logging.warning(
                    "Failed to auto-heal %s.%s: %s",
                    table.name, column.name, e,
                )

    return added


def _heal_legacy_dep_tables(conn) -> list:
    """Drop any dep table still using the v1 schema.

    Schema v1 (initial dep-feature push): composite PK on
    (source, target), no ``id`` column, no ``deleted_at``.
    Schema v2 (soft-delete): surrogate UUID ``id`` PK, ``deleted_at`` +
    ``deleted_by``, partial unique on (source, target) WHERE deleted_at
    IS NULL.

    SQLite can't alter PK in place, so we drop the legacy table and let
    ``Base.metadata.create_all`` rebuild it with the v2 schema. Dep edges
    are derived structural data — losing them during the dev upgrade is
    acceptable; production had no v1 data.

    Returns the list of table names that were dropped (for logging/tests).
    No-op on non-SQLite dialects or when tables already have v2 shape.
    """
    from sqlalchemy import text

    dropped = []
    for tbl in ("activity_dependencies", "task_dependencies", "subtask_dependencies"):
        try:
            res = conn.execute(text(f"PRAGMA table_info('{tbl}')"))
            cols = {r[1] for r in res.fetchall()}
        except Exception:
            # Table doesn't exist yet; create_all will build it.
            continue
        if cols and "id" not in cols:
            try:
                conn.execute(text(f"DROP TABLE {tbl}"))
                dropped.append(tbl)
                logging.info("Dropped legacy %s (schema v1 -> v2).", tbl)
            except Exception as e:
                logging.warning("Failed to drop legacy %s: %s", tbl, e)
    return dropped


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
        RevokedTokenModel,
        WorkPackageModel, WorkPackageTypeModel, MeetingModel, MeetingParticipantModel,
        MeetingAgendaItemModel,
        MilestoneModel,
        ActivityModel, ActivityDependencyModel, ActivityResourceModel,
        TaskModel, TaskDependencyModel, TaskResourceModel,
        SubtaskModel, SubtaskDependencyModel, SubtaskResourceModel,
        CommentModel, AttachmentModel,
        DivisionModel,
    )
    from ...core.security import hash_password
    from ...core.config import settings
    from datetime import datetime, timezone

    # ---- Schema management -------------------------------------------------
    # Two paths, mutually exclusive based on the active dialect:
    #
    # SQLite (tests + any legacy dev DB):
    #   Use Base.metadata.create_all (Alembic adds no value for in-memory
    #   test DBs, which are torn down per test). The SQLite-only ALTER
    #   blocks below also stay active to handle legacy on-disk pmis.db
    #   files left over from before the column-by-column migrations landed.
    #
    # Postgres (and any other prod-grade engine):
    #   Alembic is the single source of truth. We auto-run
    #   ``alembic upgrade head`` on every boot so devs never have to
    #   remember to run migrations manually. Idempotent — already-applied
    #   migrations are no-ops.
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
    elif not settings.MIGRATIONS_AUTORUN:
        # Operator opted out of at-boot migrations entirely. Typical use
        # case: deploys where the runtime DB role lacks DDL rights and a
        # DBA / CI pipeline runs ``alembic upgrade head`` out-of-band
        # with elevated credentials. The app boots immediately and
        # assumes the schema is already at head — first query against a
        # missing column/table will surface the real error.
        logging.warning(
            "MIGRATIONS_AUTORUN=false: skipping alembic upgrade head. "
            "Schema is assumed to already be at head. If it isn't, "
            "endpoints touching new columns/tables will fail at first "
            "request."
        )
    else:
        # Run ``alembic upgrade head`` as a subprocess so it gets a clean
        # Python state — no shared logger config, no shared SQLAlchemy
        # engine pool. Calling alembic in-process while the app's own
        # engine is initialized has been observed to hang on Windows.
        # Subprocess pattern is widely used (Django, Flask-Migrate, etc.).
        #
        # Doc 33: if ``DATABASE_URL_MIGRATIONS`` is configured, the
        # alembic env switches to it (see alembic/env.py) so DDL runs as
        # the elevated role. Log which path is in use so ops can
        # confirm the right role is being used.
        import subprocess
        import sys
        from pathlib import Path
        try:
            if settings.DATABASE_URL_MIGRATIONS:
                logging.info(
                    "alembic will run as DATABASE_URL_MIGRATIONS "
                    "(elevated/admin role); runtime sessions continue to "
                    "use DATABASE_URL."
                )
            else:
                logging.info(
                    "alembic will run as DATABASE_URL (no separate "
                    "DATABASE_URL_MIGRATIONS configured). If migrations "
                    "fail with 'must be owner of table', either set "
                    "DATABASE_URL_MIGRATIONS to a role that owns the "
                    "schema, or set MIGRATIONS_AUTORUN=false and run "
                    "migrations out-of-band with elevated creds."
                )
        except Exception:
            pass

        project_root = Path(__file__).resolve().parents[3]
        try:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=120,
                env={**__import__("os").environ},
            )
        except subprocess.TimeoutExpired as e:
            if settings.MIGRATIONS_REQUIRED:
                raise RuntimeError(
                    "alembic upgrade head timed out after 120s"
                ) from e
            logging.error(
                "alembic upgrade head timed out after 120s — continuing "
                "boot anyway because MIGRATIONS_REQUIRED=false. Schema "
                "may be behind code; investigate the migration runner."
            )
        else:
            if result.returncode != 0:
                msg = (
                    f"alembic upgrade head failed (exit {result.returncode}):\n"
                    f"STDOUT: {result.stdout}\n"
                    f"STDERR: {result.stderr}"
                )
                if settings.MIGRATIONS_REQUIRED:
                    raise RuntimeError(msg)
                logging.error(
                    "%s\n"
                    "Continuing boot anyway because MIGRATIONS_REQUIRED="
                    "false. Run the failing migration out-of-band with "
                    "elevated creds, then either flip the flag back to "
                    "true or leave it off if a DBA/CI handles migrations.",
                    msg,
                )
            else:
                logging.info("alembic upgrade head completed successfully")

    # SQLite schema drift handler: add missing nullable columns via ALTER TABLE
    # This runs only for SQLite and is idempotent. It MUST run before any
    # ORM queries that expect the new columns.
    try:
        from sqlalchemy import text
        # NOTE: ``logging`` is imported at module level — do NOT re-import
        # here, or it would become a local in init_db and shadow the
        # module-level reference used earlier in the function.

        if engine.dialect.name == "sqlite":
            # ``engine.begin()`` (NOT ``engine.connect()``) so DDL emitted
            # below is committed on success. With plain connect(), SA 2.x
            # autobegins an implicit transaction and rolls it back on close
            # — every ALTER TABLE in this block would silently vanish, and
            # the admin-bootstrap session a few lines down would crash with
            # ``no such column: users.vendor_id`` against any legacy on-disk
            # DB. begin() commits on clean exit, rolls back on exception.
            with engine.begin() as conn:
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

                    # Refresh-token grace window (added when concurrent /refresh
                    # races started returning 401s in normal FE use). Holds
                    # the just-rotated-out jti for REFRESH_TOKEN_GRACE_SECONDS
                    # so a parallel call still resolves successfully.
                    if "previous_refresh_token_jti" not in existing_cols:
                        try:
                            conn.execute(text(
                                "ALTER TABLE users ADD COLUMN "
                                "previous_refresh_token_jti VARCHAR(64)"
                            ))
                        except Exception as e:
                            logging.warning(
                                "Failed to add column previous_refresh_token_jti: %s", e,
                            )
                    if "previous_refresh_token_jti_valid_until" not in existing_cols:
                        try:
                            conn.execute(text(
                                "ALTER TABLE users ADD COLUMN "
                                "previous_refresh_token_jti_valid_until DATETIME"
                            ))
                        except Exception as e:
                            logging.warning(
                                "Failed to add column "
                                "previous_refresh_token_jti_valid_until: %s", e,
                            )
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
                    # Doc 33: ``is_version`` / ``version_no`` columns + the
                    # ``ux_projects_active_version_per_baseline`` index were
                    # removed along with the versioning feature.
                    project_column_ddl = [
                        ("actual_end_date",        "ALTER TABLE projects ADD COLUMN actual_end_date DATETIME"),
                        ("actual_start_date",      "ALTER TABLE projects ADD COLUMN actual_start_date DATETIME"),
                        ("created_by",             "ALTER TABLE projects ADD COLUMN created_by INTEGER REFERENCES users(id)"),
                        ("updated_by",             "ALTER TABLE projects ADD COLUMN updated_by INTEGER REFERENCES users(id)"),
                        ("deleted_at",             "ALTER TABLE projects ADD COLUMN deleted_at DATETIME"),
                        ("deleted_by",             "ALTER TABLE projects ADD COLUMN deleted_by INTEGER REFERENCES users(id)"),
                        ("project_code",           "ALTER TABLE projects ADD COLUMN project_code VARCHAR(30)"),
                        # Free-text label when category == 'others'.
                        ("category_other",         "ALTER TABLE projects ADD COLUMN category_other VARCHAR(255)"),
                        # Reason text when category == 'others' (added in doc-15 catalogs migration).
                        ("category_other_reason",  "ALTER TABLE projects ADD COLUMN category_other_reason VARCHAR(1000)"),
                        # Free-text owner label when owner == 'others' (added in doc-18 owner-as-division migration).
                        ("owner_other",            "ALTER TABLE projects ADD COLUMN owner_other VARCHAR(255)"),
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

                # ---- NEW: vendors.deleted_at + vendors.deleted_by --------
                # Legacy on-disk dev DBs predate the vendor soft-delete
                # feature. Add the columns + index in-place so the new
                # repository code finds the schema it expects.
                # Doc 18 also added contact-detail columns (email,
                # contact_person, phone_number); they're listed here too
                # so a single PRAGMA pass picks up everything missing.
                try:
                    res = conn.execute(text("PRAGMA table_info('vendors')"))
                    vcols = {r[1] for r in res.fetchall()}
                    for col, stmt in (
                        ("deleted_at",      "ALTER TABLE vendors ADD COLUMN deleted_at DATETIME"),
                        ("deleted_by",      "ALTER TABLE vendors ADD COLUMN deleted_by INTEGER REFERENCES users(id)"),
                        ("email",           "ALTER TABLE vendors ADD COLUMN email VARCHAR(255)"),
                        ("contact_person",  "ALTER TABLE vendors ADD COLUMN contact_person VARCHAR(255)"),
                        ("phone_number",    "ALTER TABLE vendors ADD COLUMN phone_number VARCHAR(50)"),
                        # Doc 25: human-readable identifier (VN-XXXX-YYMMDDHHMMSS).
                        ("vendor_code",     "ALTER TABLE vendors ADD COLUMN vendor_code VARCHAR(50)"),
                    ):
                        if col not in vcols:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                logging.warning("Failed to add vendors.%s: %s", col, e)
                    try:
                        conn.execute(text(
                            "CREATE INDEX IF NOT EXISTS idx_vendors_deleted_at "
                            "ON vendors(deleted_at)"
                        ))
                        conn.execute(text(
                            "CREATE INDEX IF NOT EXISTS idx_vendors_created_at "
                            "ON vendors(created_at)"
                        ))
                        conn.execute(text(
                            "CREATE INDEX IF NOT EXISTS idx_vendors_email "
                            "ON vendors(email)"
                        ))
                    except Exception as e:
                        logging.warning("Failed to create vendors indexes: %s", e)
                except Exception:
                    pass

                # ---- NEW: users.vendor_id / division / division_other / ---
                # ---- deleted_at / deleted_by + indexes -------------------
                # Legacy on-disk dev DBs predate the User-management
                # feature batch. Add columns in-place so existing rows
                # (e.g. the bootstrap admin) stay valid (NULLs are fine
                # because the API enforces "required at create" via the
                # Pydantic schema, not at the DB layer).
                try:
                    res = conn.execute(text("PRAGMA table_info('users')"))
                    ucols = {r[1] for r in res.fetchall()}
                    for col, stmt in (
                        ("vendor_id", "ALTER TABLE users ADD COLUMN vendor_id VARCHAR(36) REFERENCES vendors(id)"),
                        ("division", "ALTER TABLE users ADD COLUMN division VARCHAR(32)"),
                        ("division_other", "ALTER TABLE users ADD COLUMN division_other VARCHAR(255)"),
                        ("deleted_at", "ALTER TABLE users ADD COLUMN deleted_at DATETIME"),
                        ("deleted_by", "ALTER TABLE users ADD COLUMN deleted_by INTEGER REFERENCES users(id)"),
                        # Doc 23: phone_number (required on wire create, nullable
                        # in DB so the bootstrap admin + legacy rows stay valid).
                        ("phone_number", "ALTER TABLE users ADD COLUMN phone_number VARCHAR(50)"),
                        # Doc 25: human-readable identifier (US-XXXX-YYMMDDHHMMSS).
                        ("user_code", "ALTER TABLE users ADD COLUMN user_code VARCHAR(50)"),
                    ):
                        if col not in ucols:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                logging.warning("Failed to add users.%s: %s", col, e)
                    for stmt in (
                        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
                        "CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON users(deleted_at)",
                        "CREATE INDEX IF NOT EXISTS idx_users_vendor_id ON users(vendor_id)",
                    ):
                        try:
                            conn.execute(text(stmt))
                        except Exception as e:
                            logging.warning("Failed to create users index: %s", e)
                except Exception:
                    pass

                # ---- milestones.status ----
                # Doc 33: milestones.cloned_from_id was removed with the
                # versioning feature.
                try:
                    res = conn.execute(text("PRAGMA table_info('milestones')"))
                    mcols = {r[1] for r in res.fetchall()}
                    for col, stmt in (
                        ("status",         "ALTER TABLE milestones ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'not_completed'"),
                    ):
                        if col not in mcols:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                logging.warning("Failed to add milestones.%s: %s", col, e)
                except Exception:
                    pass

                # ---- activities.status ----
                # Doc 33: activities.cloned_from_id was removed with the
                # versioning feature. The legacy `dependency` column is
                # intentionally NOT re-added — deps now live in
                # activity_dependencies.
                try:
                    res = conn.execute(text("PRAGMA table_info('activities')"))
                    acols = {r[1] for r in res.fetchall()}
                    for col, stmt in (
                        ("status",         "ALTER TABLE activities ADD COLUMN status VARCHAR(32)"),
                    ):
                        if col not in acols:
                            try:
                                conn.execute(text(stmt))
                            except Exception as e:
                                logging.warning("Failed to add activities.%s: %s", col, e)
                except Exception:
                    pass

                # Dep tables: drop any table still using the legacy v1
                # composite-PK / no-soft-delete schema so create_all() below
                # rebuilds it fresh. Extracted into a module-level helper so
                # tests can exercise it directly.
                _heal_legacy_dep_tables(conn)

                # Generic backstop: any nullable model column that is missing
                # from the SQLite DB gets auto-added. Catches drift introduced
                # in future feature drops where the explicit ALTER blocks
                # above weren't updated. NOT NULL columns without defaults
                # still need an explicit block above this — they get logged
                # loud here so devs notice.
                try:
                    _heal_sqlite_column_drift(conn, Base.metadata)
                except Exception as e:
                    logging.warning("Generic SQLite drift heal failed: %s", e)

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
    
    # Idempotent admin bootstrap. Creds come from env (BOOTSTRAP_ADMIN_*) so
    # ops can rotate them without code changes. If the configured login
    # already exists, skip — no overwrite, no demotion of an existing admin.
    # RBAC seed (doc 21 part B): upsert built-in permissions, ensure the
    # admin/member/viewer roles exist with the right grants. Must happen
    # BEFORE the bootstrap admin user is created so the user-role
    # assignment can find the admin role row.
    db = SessionLocal()
    try:
        from .repositories.rbac_repository import RbacRepository
        RbacRepository(db).sync_builtin_permissions()
        db.commit()
    except Exception as e:
        logging.warning("RBAC seed sync failed: %s", e)
    finally:
        db.close()

    # Idempotent bootstrap admin. Doc 21 part B: admin status now derived
    # from membership in the seeded ``admin`` role (created by the RBAC
    # seed above). The ``UserModel`` no longer has an ``admin`` column.
    #
    # Doc 33 change 3 + hotfix: the bootstrap admin is the always-reachable
    # account for first-boot ops, so it MUST stay single-stage-loginnable.
    # If 2FA is left on for it, a fresh deploy that hasn't yet wired up
    # the notification microservice locks the admin out — there's no email
    # / SMS path to receive the OTP. We force ``two_factor_enabled=false``
    # on the bootstrap login on every boot (idempotent) so the demo + the
    # ops break-glass flow keep working. Other users honour ``REQUIRE_2FA``
    # + their per-user flag normally.
    db = SessionLocal()
    try:
        from .models.role import RoleModel
        from .models.user_role import UserRoleModel

        admin_user = db.query(UserModel).filter(
            UserModel.login == settings.BOOTSTRAP_ADMIN_LOGIN
        ).first()

        if admin_user is None:
            admin_user = UserModel(
                login=settings.BOOTSTRAP_ADMIN_LOGIN,
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                hashed_password=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                first_name="Administrator",
                last_name="System",
                status="active",
                two_factor_enabled=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(admin_user)
            db.flush()
        elif admin_user.two_factor_enabled:
            # Existing bootstrap admin from a pre-doc-33 deploy: force the
            # flag off so single-stage login keeps working post-upgrade.
            admin_user.two_factor_enabled = False
            admin_user.updated_at = datetime.now(timezone.utc)
            db.flush()

        admin_role = (
            db.query(RoleModel).filter(RoleModel.name == "admin").first()
        )
        if admin_role is not None:
            already_admin = (
                db.query(UserRoleModel)
                .filter(
                    UserRoleModel.user_id == admin_user.id,
                    UserRoleModel.role_id == admin_role.id,
                )
                .first()
            )
            if already_admin is None:
                db.add(UserRoleModel(
                    user_id=admin_user.id, role_id=admin_role.id,
                ))
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

    # Seed a few demo vendors so the frontend has something to render on
    # first run. Five well-known IT services orgs plus minimal demo contact
    # info per row (email/contact_person/phone_number) so the post-doc-18
    # Vendor Management columns aren't empty on a fresh install. Replace
    # with real vendor data when vendor management flows land.
    #
    # ``include_deleted=True`` matters: post-doc-17, ``get_by_name`` defaults
    # to filtering out soft-deleted rows, but the underlying ``vendors.name``
    # UNIQUE constraint applies regardless of deletion state. If a vendor
    # named e.g. "Infosys" was soft-deleted on this server, the existence
    # check would return None, the create() call would fire, and the DB
    # would reject the insert with a UniqueViolation. Checking with
    # include_deleted=True correctly skips the insert for deleted rows.
    #
    # Per-row commit pattern: we commit after each successful insert so a
    # later UniqueViolation (e.g. concurrent boot, partially-applied
    # migration) doesn't roll back already-seeded earlier rows. The per-
    # iteration rollback in the except clause keeps the session usable
    # for the next iteration — without it, the final commit would raise
    # PendingRollbackError and crash app startup.
    _vendor_seed = (
        ("Infosys",    "vendor.contact@infosys.example",    "Infosys Liaison",     "+91 80 4116 7777"),
        ("TCS",        "vendor.contact@tcs.example",        "TCS Liaison",         "+91 22 6778 9595"),
        ("Wipro",      "vendor.contact@wipro.example",      "Wipro Liaison",       "+91 80 2844 0011"),
        ("Accenture",  "vendor.contact@accenture.example",  "Accenture Liaison",   "+91 80 2298 9999"),
        ("Capgemini",  "vendor.contact@capgemini.example",  "Capgemini Liaison",   "+91 22 6755 7000"),
    )
    db = SessionLocal()
    try:
        from .repositories import VendorRepository

        v_repo = VendorRepository(db)
        for name, email, contact_person, phone_number in _vendor_seed:
            try:
                if v_repo.get_by_name(name, include_deleted=True) is None:
                    v_repo.create(
                        name=name,
                        active=True,
                        email=email,
                        contact_person=contact_person,
                        phone_number=phone_number,
                    )
                    db.commit()
            except Exception as e:
                # A failed insert leaves the session needing a rollback
                # before the next iteration can run; without this rollback
                # any subsequent commit raises PendingRollbackError and
                # crashes app startup.
                logging.warning("Skipping vendor seed for %r: %s", name, e)
                db.rollback()
    finally:
        db.close()

    # Seed divisions catalog with the three built-in rows. Idempotent:
    # only inserts the rows that aren't already present (matched by code).
    # User-added divisions (created on the fly when a project is saved
    # with owner='others' + a free-text ownerOther) coexist with the
    # built-ins as is_builtin=False rows.
    db = SessionLocal()
    try:
        from .models.division import DivisionModel
        for code, label, requires_other in (
            ("tmd1",   "TMD1",   False),
            ("tmd2",   "TMD2",   False),
            ("others", "Others", True),
        ):
            existing = (
                db.query(DivisionModel)
                .filter(DivisionModel.code == code)
                .first()
            )
            if existing is None:
                db.add(DivisionModel(
                    code=code, label=label,
                    is_builtin=True,
                    requires_other=requires_other,
                    active=True,
                ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    # Seed project_status_transitions catalog from the in-code rules. Idempotent:
    # only inserts edges that aren't already present (matched by from/to pair).
    # The in-code constants in services.transitions remain the spec; this seed
    # keeps the table in sync on every boot so DB-only callers (FE discovery)
    # see the same picture.
    db = SessionLocal()
    try:
        from .models.project_status_transition import ProjectStatusTransitionModel
        from ...api.v3.projects.services.transitions import (
            ADMIN_ONLY_TRANSITIONS,
            STATUS_NEW,
            _LEGAL_TRANSITIONS,
        )

        # Initial-status seed: an empty/None from_status means "valid initial
        # value on a fresh create". We only allow 'new' as the initial value.
        existing_initial = (
            db.query(ProjectStatusTransitionModel)
            .filter(ProjectStatusTransitionModel.from_status.is_(None))
            .filter(ProjectStatusTransitionModel.to_status == STATUS_NEW)
            .first()
        )
        if existing_initial is None:
            db.add(ProjectStatusTransitionModel(
                from_status=None,
                to_status=STATUS_NEW,
                requires_admin=False,
                active=True,
                description="Default status assigned to a freshly created project.",
            ))

        for (from_s, to_s) in _LEGAL_TRANSITIONS:
            existing = (
                db.query(ProjectStatusTransitionModel)
                .filter(ProjectStatusTransitionModel.from_status == from_s)
                .filter(ProjectStatusTransitionModel.to_status == to_s)
                .first()
            )
            if existing is None:
                db.add(ProjectStatusTransitionModel(
                    from_status=from_s,
                    to_status=to_s,
                    requires_admin=(from_s, to_s) in ADMIN_ONLY_TRANSITIONS,
                    active=True,
                    description=(
                        f"Transition {from_s} -> {to_s} (seeded from "
                        f"in-code _LEGAL_TRANSITIONS)."
                    ),
                ))
        db.commit()
    except Exception:
        # Bootstrap failures should not prevent app start.
        db.rollback()
    finally:
        db.close()

    # NOTE: the project_owners catalog seed used to live here, populating
    # the bootstrap admin into the per-user owner whitelist. The whitelist
    # was deprecated in doc 18 (project.owner became a strict division
    # code, not a user reference) and the table itself was dropped in
    # doc 20. No seed needed anymore.

    # ---- File storage readiness check --------------------------------------
    # Verify the attachments storage path is reachable + writable. In prod
    # this means the NFS mount is healthy; in dev it auto-creates the
    # local folder. A failure here logs loud but does NOT crash the app —
    # storage-dependent endpoints will return 503; everything else stays
    # online. See ATTACHMENTS_ON_UNAVAILABLE setting.
    try:
        from ..storage import get_storage, StorageUnavailableError
        try:
            get_storage().ensure_ready()
        except StorageUnavailableError as e:
            logging.error(
                "Attachments storage NOT ready: %s. "
                "Comments/attachments endpoints will return 503 until fixed.",
                e,
            )
    except Exception as e:  # noqa: BLE001
        logging.error("Storage init unexpected error: %s", e)
