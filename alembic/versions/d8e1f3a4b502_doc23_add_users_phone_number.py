"""doc 23: add users.phone_number column

Revision ID: d8e1f3a4b502
Revises: c4d9a1b3e201
Create Date: 2026-05-02

Adds the ``phone_number`` column to ``users`` (per FE request — same
shape as ``vendors.phone_number``). The column is nullable in the DB
so the bootstrap admin row + any pre-feature user rows stay valid;
the wire-level schema enforces it as **required** on user create.
On user update the field is optional (you don't have to re-send it on
every PATCH).

IDEMPOTENT — wrapped in an inspector check so re-running against an
already-migrated DB is a no-op (matches the pattern of the other
recent migrations in this chain).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e1f3a4b502"
down_revision: Union[str, Sequence[str], None] = "c4d9a1b3e201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in set(inspector.get_table_names()):
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "users", "phone_number"):
        op.add_column(
            "users",
            sa.Column("phone_number", sa.String(length=50), nullable=True),
        )


def downgrade() -> None:
    """Drop the column on downgrade. Safe because nothing depends on it
    (no FK references)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "users", "phone_number"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("phone_number")
