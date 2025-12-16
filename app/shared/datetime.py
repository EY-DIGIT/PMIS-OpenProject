"""
DateTime utilities.
"""
from datetime import datetime
from typing import Optional


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
