"""Pure formatting helper functions for ASCII progress display.

This module contains pure functions (no state dependencies) extracted from
AsciiProgressBackend for better testability and reusability.
"""

from __future__ import annotations

import time

from .progress_types import SPINNER_FRAMES, TaskState


def compute_display_name(task: TaskState) -> str:
    """Return a condensed display name for a task (strip extension).

    Args:
        task: The task state containing the name.

    Returns:
        The task name with .AppImage extension stripped if present.
    """
    name = task.name
    if name.endswith(".AppImage"):
        return name[:-9]
    return name


def format_api_task_status(task: TaskState) -> str:
    """Return the status string for an API fetching task.

    Args:
        task: The task state to format.

    Returns:
        A formatted status string indicating the API task's state.
    """
    if task.total > 0:
        completed = int(task.completed)
        total = int(task.total)
        if task.is_finished or completed >= total:
            if "cached" in task.description.lower():
                return f"{total}/{total}        Retrieved from cache"
            return f"{total}/{total}        Retrieved"

        return f"{completed}/{total}        Fetching..."

    if task.is_finished:
        if "cached" in task.description.lower():
            return "Retrieved from cache"
        return "Retrieved"

    return "Fetching..."


def compute_spinner(fps: int) -> str:
    """Compute the current spinner frame based on time and FPS.

    Args:
        fps: Frames per second for spinner animation.

    Returns:
        The current spinner frame character.
    """
    current_time = time.monotonic()
    spinner_idx = int(current_time * fps) % len(SPINNER_FRAMES)
    return SPINNER_FRAMES[spinner_idx]


def compute_download_header(download_count: int) -> str:
    """Return the downloads section header string.

    Args:
        download_count: The total number of downloads.

    Returns:
        A formatted header string for the downloads section.
    """
    if download_count > 1:
        return f"Downloading ({download_count}):"
    return "Downloading:"
