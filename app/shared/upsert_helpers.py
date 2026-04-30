"""
Small helper: return the dialect-specific `insert()` construct that supports
`.on_conflict_do_update(...)`. Works for both PostgreSQL and SQLite (both
support INSERT ... ON CONFLICT DO UPDATE with identical syntax).
"""
from sqlalchemy.orm import Session


def dialect_insert(db: Session):
    """
    Return the dialect-specific insert() callable for the given session.

    Raises NotImplementedError for unsupported dialects.
    """
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _insert
        return _insert
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _insert
        return _insert
    raise NotImplementedError(
        f"Upsert is not supported for dialect '{dialect}'. "
        "Only PostgreSQL and SQLite are supported."
    )
