"""Common formatting utilities for UI display.

This module provides reusable formatting functions for consistent presentation
across different display modules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaskStatusInfo:
    """Information for determining task status."""

    is_finished: bool
    success: bool | None
    description: str
    error_message: str


def determine_task_status_symbol(
    status_info: TaskStatusInfo,
    spinner: str,
) -> str:
    """Determine the status symbol for a task.

    Args:
        status_info: Task status information.
        spinner: Spinner character to use for in-progress tasks.

    Returns:
        Status symbol: ✓ (success), ✖ (error), ! (warning), or spinner.

    """
    if not status_info.is_finished:
        return spinner

    # Warning case: success but "not verified"
    if (
        status_info.success
        and status_info.description
        and "not verified" in status_info.description.lower()
    ):
        return "!"

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
