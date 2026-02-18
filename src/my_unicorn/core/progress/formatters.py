"""Common formatting utilities for UI display.

This module provides reusable formatting functions for consistent presentation
across different display modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TaskStatusInfo:
    """Information for determining task status."""

    is_finished: bool
    success: bool | None
    description: str
    error_message: str


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


def determine_task_status_symbol(
    status_info: TaskStatusInfo,
    spinner: str,
) -> str:
    """Determine the status symbol for a task.

    Args:
        status_info: Task status information.
        spinner: Spinner character to use for in-progress tasks.

    Returns:
        Status symbol: ✓ (success), ✖ (error), ⚠ (warning), or spinner.

    """
    if not status_info.is_finished:
        return spinner

    # Warning case: success but "not verified"
    if (
        status_info.success
        and status_info.description
        and "not verified" in status_info.description.lower()
    ):
        return "⚠"

    return "✓" if status_info.success else "✖"


def should_show_warning_message(status_info: TaskStatusInfo) -> bool:
    """Check if a warning message should be displayed.

    Args:
        status_info: Task status information.

    Returns:
        True if warning message should be shown.

    """
    return bool(
        status_info.is_finished
        and status_info.success
        and status_info.description
        and "not verified" in status_info.description.lower()
    )


def should_show_error_message(status_info: TaskStatusInfo) -> bool:
    """Check if an error message should be displayed.

    Args:
        status_info: Task status information.

    Returns:
        True if error message should be shown.

    """
    return bool(
        status_info.is_finished
        and not status_info.success
        and status_info.error_message
    )


def format_verification_info(verification: dict[str, Any]) -> str:
    """Format verification information for display.

    Supports both new multi-method format and legacy single-method format.

    Args:
        verification: Verification state from app config

    Returns:
        Formatted string for display

    Example output:
        ✓ SHA256 digest (github_api)
        ✗ SHA256 checksum (SHA256SUMS.txt)
        ⚠ Partial verification: 1 passed, 1 failed

    """
    methods = verification.get("methods")
    if not methods or not isinstance(methods, list):
        return _format_verification_legacy(verification)

    lines = []
    for method in methods:
        status_marker = "✓" if method.get("status") == "passed" else "✗"
        algorithm = str(method.get("algorithm", "SHA256")).upper()
        method_type = method.get("type", "unknown")
        source = method.get("source", "unknown")

        # Shorten source display for readability
        if source.startswith("https://"):
            # Extract filename from URL
            source = source.split("/")[-1] if "/" in source else source

        line = f"{status_marker} {algorithm} {method_type} ({source})"
        lines.append(line)

    warning = verification.get("warning")
    if warning:
        lines.append(f"⚠ {warning}")

    return "\n".join(lines)


def _format_verification_legacy(verification: dict[str, Any]) -> str:
    """Format legacy verification info (backward compatibility).

    Args:
        verification: Legacy verification state from app config

    Returns:
        Formatted string for display

    """
    if "digest" in verification:
        digest = verification["digest"]
        if isinstance(digest, dict):
            passed = digest.get("passed", False)
            hash_type = str(digest.get("hash_type", "sha256")).upper()
            status_marker = "✓" if passed else "✗"
            return f"● {status_marker} {hash_type} digest"

    if "checksum_file" in verification:
        checksum = verification["checksum_file"]
        if isinstance(checksum, dict):
            passed = checksum.get("passed", False)
            hash_type = str(checksum.get("hash_type", "sha256")).upper()
            status_marker = "✓" if passed else "✗"
            return f"● {status_marker} {hash_type} checksum file"

    return "Not verified"
