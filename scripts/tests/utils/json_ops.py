#!/usr/bin/env python3
"""JSON operation utilities for test framework.

This module provides pure JSON read/write operations using orjson
to eliminate code duplication and ensure consistent JSON handling.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from pathlib import Path
from typing import Any

import orjson


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON from file.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON data as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        orjson.JSONDecodeError: If JSON is invalid
        PermissionError: If file can't be read
    """
    return orjson.loads(path.read_bytes())


def save_json(
    path: Path,
    data: dict[str, Any],
    indent: bool = True,  # noqa: FBT001, FBT002
) -> None:
    """Save JSON to file.

    Args:
        path: Path to JSON file
        data: Dictionary to save as JSON
        indent: Whether to use indentation (2 spaces)

    Raises:
        PermissionError: If file can't be written
        TypeError: If data is not JSON serializable
    """
    options = orjson.OPT_INDENT_2 if indent else 0
    path.write_bytes(orjson.dumps(data, option=options))


def is_valid_json(path: Path) -> bool:
    """Check if file contains valid JSON.

    Args:
        path: Path to file

    Returns:
        True if file contains valid JSON, False otherwise
    """
    if not path.exists():
        return False
    try:
        orjson.loads(path.read_bytes())
    except (orjson.JSONDecodeError, ValueError):
        return False
    return True


def merge_json(
    base: dict[str, Any], updates: dict[str, Any]
) -> dict[str, Any]:
    """Merge two dictionaries recursively.

    Updates take precedence over base values.

    Args:
        base: Base dictionary
        updates: Dictionary with updates

    Returns:
        Merged dictionary (new instance, doesn't modify inputs)
    """
    result = base.copy()
    for key, value in updates.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = merge_json(result[key], value)
        else:
            result[key] = value
    return result


def get_json_value(
    data: dict[str, Any],
    path: str,
    default: Any = None,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Get nested value from JSON using dot notation.

    Args:
        data: Dictionary to search
        path: Dot-separated path (e.g., "metadata.version")
        default: Default value if path not found

    Returns:
        Value at path or default if not found

    Examples:
        >>> data = {"metadata": {"version": "1.0"}}
        >>> get_json_value(data, "metadata.version")
        '1.0'
        >>> get_json_value(data, "metadata.missing", "default")
        'default'
    """
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
