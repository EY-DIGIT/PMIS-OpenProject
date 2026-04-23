"""
Alembic environment.

Wired into the application so:
- DATABASE_URL is read from app.core.config.settings (env-driven, not from
  alembic.ini), so dev/staging/prod all use the same migration runner.
- target_metadata is the project's SQLAlchemy ``Base.metadata`` after every
  model module has been imported, so ``alembic revision --autogenerate``
  sees every table.
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Project imports — must come BEFORE target_metadata so the model classes
# register themselves with Base.metadata.
from app.core.config import settings
from app.infrastructure.db.session import Base
from app.infrastructure.db import models  # noqa: F401  (re-exports every model)


# Alembic Config object (reads alembic.ini).
config = context.config

# Override sqlalchemy.url from the env-driven app settings so we never have
# to keep alembic.ini in sync with .env.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate target.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
