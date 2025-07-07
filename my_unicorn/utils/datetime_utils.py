#!/usr/bin/env python3
"""Date and time utility functions.

This module provides functionality for handling date and time operations. It includes utilities for:
- Parsing timestamps from various formats (ISO strings, Unix timestamps, datetime objects)
- Converting timestamps to standardized string formats
- Calculating time-based values for rate limiting
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_timestamp(timestamp_value: str | float | datetime | None) -> datetime | None:
    """Parse timestamp from various formats into datetime object.

    Converts timestamps from multiple formats into standard datetime objects.

    Args:
        timestamp_value: Input timestamp in one of:
            - ISO format string ("2023-01-01T12:00:00Z")
            - Unix timestamp (float/int)
            - Unix timestamp string
            - datetime object
            - None

    Returns:
        datetime | None: Parsed UTC datetime object if successful, None if parsing fails

    Raises:
        No exceptions - returns None for any parsing failures

    """
    if timestamp_value is None:
        return None

    # If already a datetime object, return it directly
    if isinstance(timestamp_value, datetime):
        return timestamp_value

    # Handle string timestamps
    if isinstance(timestamp_value, str):
        try:
            # Try ISO format first (most common in JSON data)
            return datetime.fromisoformat(timestamp_value)
        except ValueError:
            try:
                # Try parsing as float/int string
                return datetime.fromtimestamp(float(timestamp_value))
            except (ValueError, TypeError, OverflowError) as e:
                logger.debug("Failed to parse timestamp string '%s': %s", timestamp_value, e)
                return None

    # Handle numeric timestamps (float/int)
    elif isinstance(timestamp_value, (int, float)):
        try:
            return datetime.fromtimestamp(timestamp_value)
        except (ValueError, TypeError, OverflowError) as e:
            logger.debug("Failed to parse numeric timestamp '%s': %s", timestamp_value, e)
            return None

    # Unsupported type
    logger.debug("Unsupported timestamp type: %s", type(timestamp_value))
    return None


def format_timestamp(
    timestamp_value: str | float | datetime, format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str | None:
    """Parse a timestamp and format it as a string.

    Args:
        timestamp_value: Input timestamp in one of:
            - ISO format string
            - Unix timestamp
            - datetime object
        format_str: strftime format string (default: "%Y-%m-%d %H:%M:%S")

    Returns:
        str | None: Formatted timestamp string if successful, None if parsing fails

    Examples:
        >>> format_timestamp("2023-01-01T12:00:00Z")
        '2023-01-01 12:00:00'
        >>> format_timestamp(1672574400)
        '2023-01-01 12:00:00'

    """
    dt = parse_timestamp(timestamp_value)
    if dt:
        return dt.strftime(format_str)
    return None


def get_next_hour_timestamp() -> int:
    """Get the Unix timestamp for the beginning of the next hour.

    Calculates the timestamp for the start of the next hour, used primarily
    for GitHub API rate limit reset timing.

    Returns:
        int: Unix timestamp (seconds since epoch) for the start of next hour

    Example:
        >>> current = 1672574400  # 2023-01-01 12:30:00
        >>> get_next_hour_timestamp()
        1672578000  # 2023-01-01 13:00:00

    """
    current_time = int(datetime.now().timestamp())
    return (current_time // 3600 + 1) * 3600
