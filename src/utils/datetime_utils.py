#!/usr/bin/env python3
"""Date and time utility functions.

This module provides common functionality for handling date and time operations,
particularly parsing timestamps from various formats into datetime objects.
"""

import logging
from datetime import datetime
from typing import Optional, Union

# Configure module logger
logger = logging.getLogger(__name__)


def parse_timestamp(timestamp_value: Union[str, float, datetime, None]) -> Optional[datetime]:
    """Parse timestamp from various formats into datetime object.

    Handles different input formats including:
    - ISO format strings (e.g. "2023-01-01T12:00:00")
    - Unix timestamps as integers or floats
    - Unix timestamps as strings
    - datetime objects (returned as-is)

    Args:
        timestamp_value: Timestamp in various formats

    Returns:
        datetime: Parsed datetime object or None if parsing fails

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
                logger.debug(f"Failed to parse timestamp string '{timestamp_value}': {e}")
                return None

    # Handle numeric timestamps (float/int)
    elif isinstance(timestamp_value, (int, float)):
        try:
            return datetime.fromtimestamp(timestamp_value)
        except (ValueError, TypeError, OverflowError) as e:
            logger.debug(f"Failed to parse numeric timestamp '{timestamp_value}': {e}")
            return None

    # Unsupported type
    logger.debug(f"Unsupported timestamp type: {type(timestamp_value)}")
    return None


def format_timestamp(
    timestamp_value: Union[str, float, None], format_str: str = "%Y-%m-%d %H:%M:%S"
) -> Optional[str]:
    """Parse a timestamp and format it as a string.

    Args:
        timestamp_value: Timestamp in various formats
        format_str: Format string for the output

    Returns:
        str: Formatted timestamp string or None if parsing fails

    """
    dt = parse_timestamp(timestamp_value)
    if dt:
        return dt.strftime(format_str)
    return None


def get_next_hour_timestamp() -> int:
    """Get the Unix timestamp for the beginning of the next hour.

    Useful for GitHub API rate limit calculations which reset hourly.

    Returns:
        int: Unix timestamp for the beginning of the next hour

    """
    current_time = int(datetime.now().timestamp())
    return (current_time // 3600 + 1) * 3600
