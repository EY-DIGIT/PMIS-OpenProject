"""doc 38 field trim — activities owner_division/concerned_division/vendor_id

Revision ID: e8d4f7a2b9c1
Revises: d3e5f7a9b1c2
Create Date: 2026-05-07

Adds three optional columns to the ``activities`` table:

  owner_division      VARCHAR(32) NULL  — division catalog code
  concerned_division  VARCHAR(32) NULL  — division catalog code
  vendor_id           VARCHAR(36) NULL  — FK to vendors.id

Also relaxes the legacy ``ck_activities_type`` CHECK so new rows can
have ``type IS NULL`` (the four type-specific create endpoints collapse
to a single POST /activities/create per doc 38). Existing legacy rows
keep their populated ``type`` value.

Idempotent — safe to re-run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8d4f7a2b9c1"
down_revision: Union[str, Sequence[str], None] = "d3e5f7a9b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(inspector, table_name: str):
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name
    cols = _existing_columns(inspector, "activities")

    if "owner_division" not in cols:
        op.add_column(
            "activities",
            sa.Column("owner_division", sa.String(length=32), nullable=True),
        )
        try:
            op.create_index(
                "ix_activities_owner_division",
                "activities",
                ["owner_division"],
                unique=False,
            )
        except Exception:
            pass

    if "concerned_division" not in cols:
        op.add_column(
            "activities",
            sa.Column("concerned_division", sa.String(length=32), nullable=True),
        )
        try:
            op.create_index(
                "ix_activities_concerned_division",
                "activities",
                ["concerned_division"],
                unique=False,
            )
        except Exception:
            pass

    if "vendor_id" not in cols:
        op.add_column(
            "activities",
            sa.Column("vendor_id", sa.String(length=36), nullable=True),
        )
        try:
            op.create_index(
                "ix_activities_vendor_id", "activities", ["vendor_id"], unique=False,
            )
        except Exception:
            pass
        # FK only on Postgres — SQLite-test path skips since the row count
        # is empty and FK enforcement isn't required in unit tests.
        if dialect == "postgresql":
            try:
                op.create_foreign_key(
                    "fk_activities_vendor_id",
                    "activities",
                    "vendors",
                    ["vendor_id"],
                    ["id"],
                )
            except Exception:
                pass

    # Doc 38: relax the type CHECK so new rows can be NULL. Postgres-only
    # via raw SQL (SQLite recreates the table on alter, expensive; the
    # SQLite test path validates via SQLAlchemy CheckConstraint at the
    # ORM level instead).
    if dialect == "postgresql":
        op.execute("ALTER TABLE activities DROP CONSTRAINT IF EXISTS ck_activities_type")
        op.execute(
            "ALTER TABLE activities ADD CONSTRAINT ck_activities_type "
            "CHECK (type IS NULL OR type IN ('standard', 'resource', 'transactional'))"
        )


def downgrade() -> None:
    """Intentional no-op (matches the project pattern for additive migrations)."""
    pass
