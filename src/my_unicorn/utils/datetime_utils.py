"""Datetime utilities for consistent timestamp handling.

This module provides utilities for generating timestamps in local timezone
for user-facing dates in configurations and metadata.
"""

from datetime import datetime


def get_current_datetime_local_iso() -> str:
    """Get current datetime in local timezone as ISO format string.

    Returns:
        ISO 8601 formatted datetime string with local timezone offset.
        Example: "2026-02-04T14:02:04.556063+03:00"

    """
    return datetime.now().astimezone().isoformat()


def get_current_datetime_local() -> datetime:
    """Get current datetime in local timezone.

    Returns:
        datetime object in local timezone.

    """
    return datetime.now().astimezone()
