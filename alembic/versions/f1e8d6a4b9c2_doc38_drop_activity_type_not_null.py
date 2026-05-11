"""doc 38 follow-up — drop NOT NULL on activities.type

Revision ID: f1e8d6a4b9c2
Revises: e8d4f7a2b9c1
Create Date: 2026-05-07

Doc 38 collapsed the four type-specific activity create endpoints into a
single ``POST /milestones/{id}/activities/create`` that no longer
accepts ``type`` in the body. The previous migration relaxed the
``ck_activities_type`` CHECK to allow NULL, but missed the column-level
NOT NULL constraint on Postgres. New rows created via the doc-38
endpoint set ``type=NULL`` and the INSERT failed with NotNullViolation.

This migration drops the NOT NULL on ``activities.type``. Idempotent —
checks current state before altering.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1e8d6a4b9c2"
down_revision: Union[str, Sequence[str], None] = "e8d4f7a2b9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "activities" not in set(inspector.get_table_names()):
        return
    cols = {c["name"]: c for c in inspector.get_columns("activities")}
    if "type" not in cols:
        return
    if cols["type"].get("nullable"):
        # Already nullable — nothing to do.
        return

    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute("ALTER TABLE activities ALTER COLUMN type DROP NOT NULL")
    else:
        # SQLite recreates the table on alter — skip; the model-level
        # column is already nullable so the test path doesn't hit the
        # NOT NULL constraint via the ORM.
        try:
            with op.batch_alter_table("activities") as batch:
                batch.alter_column("type", nullable=True)
        except Exception:
            pass


def downgrade() -> None:
    """Intentional no-op — see project pattern for additive migrations."""
    pass
