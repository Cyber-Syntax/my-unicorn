"""Common formatting utilities for UI display.

This module provides reusable formatting functions for consistent presentation
across different display modules.
"""


def format_version_transition(
    current_version: str,
    latest_version: str,
    max_length: int = 40,
) -> str:
    """Format a version transition string (current → latest).

    Args:
        current_version: The current version string.
        latest_version: The latest version string.
        max_length: Maximum length before truncating.

    Returns:
        Formatted version transition string.

    """
    version_str = f"{current_version} → {latest_version}"
    if len(version_str) > max_length:
        return version_str[: max_length - 3] + "..."
    return version_str


def format_version_string(version: str, max_length: int = 40) -> str:
    """Format a single version string with optional truncation.

    Args:
        version: Version string to format.
        max_length: Maximum length before truncating.

    Returns:
        Formatted (possibly truncated) version string.

    """
    if len(version) > max_length:
        return version[: max_length - 3] + "..."
    return version


def format_app_status_line(
    app_name: str,
    status_icon: str,
    status_message: str,
    name_width: int = 25,
) -> str:
    """Format a standard app status line.

    Args:
        app_name: Name of the application.
        status_icon: Icon/emoji representing status (✅, ❌, etc.).
        status_message: Status message to display.
        name_width: Width for the app name column.

    Returns:
        Formatted status line string.

    """
    return f"{app_name:<{name_width}} {status_icon} {status_message}"


def format_indented_detail(message: str, indent: int = 25) -> str:
    """Format an indented detail message (for errors, warnings, etc.).

    Args:
        message: Detail message to format.
        indent: Number of spaces to indent.

    Returns:
        Formatted indented message.

    """
    return f"{'':>{indent}}    → {message}"


def format_section_header(title: str, width: int = 50) -> str:
    """Format a section header with divider line.

    Args:
        title: Section title.
        width: Width of the divider line.

    Returns:
        Formatted section header with title and divider.

    """
    return f"\n{title}\n{'-' * width}"


def format_table_header(
    columns: list[tuple[str, int]],
    total_width: int = 70,
) -> str:
    """Format a table header with column names and divider.

    Args:
        columns: List of (column_name, width) tuples.
        total_width: Total width for the divider line.

    Returns:
        Formatted table header with columns and divider.

    """
    header_parts = [f"{name:<{width}}" for name, width in columns]
    header_line = " ".join(header_parts)
    divider = "-" * total_width
    return f"\n{header_line}\n{divider}"


def format_count_summary(
    label: str,
    count: int,
    icon: str = "",
) -> str:
    """Format a count summary line.

    Args:
        label: Label describing what is being counted.
        count: The count value.
        icon: Optional icon/emoji prefix.

    Returns:
        Formatted count summary string.

    """
    prefix = f"{icon} " if icon else ""
    return f"{prefix}{label}: {count}"
