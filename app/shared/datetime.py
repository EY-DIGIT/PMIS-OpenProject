"""
DateTime utilities.
"""
from datetime import datetime, timezone
from typing import Optional


def ensure_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Return a timezone-aware UTC datetime.

    If ``dt`` is naive, assume UTC and attach tzinfo. If aware, convert to UTC.
    Use this before comparing user-supplied datetimes (which may be naive or
    aware depending on client) against DB values or ``datetime.now(utc)``.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """
    Format datetime to ISO 8601 string.

    Args:
        dt: Datetime to format

    Returns:
        ISO 8601 formatted string or None
    """
    if dt is None:
        return None

    return dt.isoformat()


def iso_utc(dt: Optional[datetime]) -> Optional[str]:
    """Format a datetime as a tz-aware UTC ISO 8601 string.

    Doc 27 part 2 (response-format consistency): every API response
    should emit datetimes with an explicit ``+00:00`` (UTC) suffix, so
    FE date pickers / locale converters can reliably interpret them
    without having to guess whether a naive value means UTC or local.

    Behavior:
      - ``None`` → ``None``
      - Naive datetime → assumed UTC; suffix attached.
      - tz-aware datetime → converted to UTC; suffix attached.

    Pairs with ``app/infrastructure/db/utc_datetime.UtcDateTime``: that
    type guarantees stored values are canonical naive UTC; this helper
    guarantees responses re-attach the ``+00:00`` so FE never sees a
    bare naive datetime.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """
    Parse ISO 8601 datetime string.

    Args:
        dt_str: ISO 8601 datetime string

    Returns:
        Datetime object or None if parsing fails
    """
    try:
        return datetime.fromisoformat(dt_str)
    except (ValueError, AttributeError):
        return None
