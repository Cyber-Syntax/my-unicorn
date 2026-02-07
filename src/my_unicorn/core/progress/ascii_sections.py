"""ASCII section rendering module.

Pure functions for rendering progress sections (API, downloads, processing).
These functions were extracted from AsciiProgressBackend to improve separation
of concerns and testability.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from my_unicorn.utils.progress_utils import (
    format_eta,
    format_percentage,
    human_mib,
    human_speed_bps,
    render_bar,
    truncate_text,
)

from .ascii_format import (
    compute_display_name,
    compute_download_header,
    compute_spinner,
)
from .formatters import (
    TaskStatusInfo,
    determine_task_status_symbol,
    should_show_error_message,
    should_show_warning_message,
)
from .progress_types import OPERATION_NAMES, ProgressType, TaskState


@dataclass(frozen=True, slots=True)
class SectionRenderConfig:
    """Configuration for section rendering.

    Groups shared settings to reduce parameter sprawl across
    section rendering functions.
    """

    bar_width: int
    min_name_width: int
    spinner_fps: int
    interactive: bool


def select_current_task(
    tasks: list[TaskState],
) -> TaskState | None:
    """Select the current task to display for a multi-phase app.

    Preference order:
      - first unfinished task
      - first failed task
      - otherwise the last (completed) phase

    Args:
        tasks: List of TaskState objects to select from

    Returns:
        Selected TaskState or None if list is empty

    """
    return next(
        (
            t
            for t in tasks
            if (not t.is_finished) or (t.is_finished and not t.success)
        ),
        tasks[-1] if tasks else None,
    )


def calculate_dynamic_name_width(
    interactive: bool,
    min_name_width: int,
) -> int:
    """Calculate dynamic name width based on terminal size.

    Args:
        interactive: Whether in interactive mode
        min_name_width: Minimum width for name field

    Returns:
        Width to use for name (either full length or truncated)

    """
    # Fixed width for: size + speed + eta + bar + pct + status
    fixed_width = 10 + 10 + 5 + 32 + 6 + 1 + 6

    if interactive:
        try:
            terminal_width = shutil.get_terminal_size().columns
        except (AttributeError, ValueError, OSError):
            # Fallback if terminal size cannot be determined
            terminal_width = 80
    else:
        # Use fixed width in non-interactive mode for consistent rendering
        terminal_width = 80

    # Calculate available space for name
    available_width = terminal_width - fixed_width

    # Use the smaller of: available width or actual name length
    # But ensure a minimum for readability
    return max(min_name_width, available_width)


def compute_max_name_width(
    display_names: list[str],
    interactive: bool,
    min_name_width: int,
) -> int:
    """Compute maximum name width across items for alignment.

    Args:
        display_names: List of display names to measure
        interactive: Whether in interactive mode
        min_name_width: Minimum width for name field

    Returns:
        Maximum width needed for alignment

    """
    max_name_width = 0
    for display_name in display_names:
        name_width = calculate_dynamic_name_width(interactive, min_name_width)
        max_name_width = max(
            max_name_width, min(name_width, len(display_name))
        )
    return max_name_width


def format_download_lines(
    task: TaskState,
    max_name_width: int,
    bar_width: int,
) -> list[str]:
    """Format lines for a single download task (main + optional error).

    Args:
        task: TaskState to format
        max_name_width: Maximum width for task name
        bar_width: Width of progress bar

    Returns:
        List of formatted output lines

    """
    lines: list[str] = []
    display_name = compute_display_name(task)
    name = truncate_text(display_name, max_name_width)

    if task.total > 0:
        size_str = f"{human_mib(task.total):>10}"
    else:
        size_str = "    --    "

    if task.speed > 0:
        speed_str = f"{human_speed_bps(task.speed):>10}"
    else:
        speed_str = "   --     "

    if task.speed > 0 and task.total > task.completed:
        remaining_bytes = task.total - task.completed
        eta_seconds = remaining_bytes / task.speed
        eta_str = format_eta(eta_seconds)
    else:
        eta_str = "00:00"

    bar = render_bar(task.completed, task.total, bar_width)
    pct = format_percentage(task.completed, task.total)

    # Create status info for status determination
    status_info = TaskStatusInfo(
        is_finished=task.is_finished,
        success=task.success,
        description=task.description,
        error_message=task.error_message,
    )

    # Use status symbol, but show empty space for in-progress downloads
    status = (
        ("✓" if status_info.success else "✖")
        if status_info.is_finished
        else " "
    )

    lines.append(
        f"{name:<{max_name_width}} {size_str} {speed_str} "
        f"{eta_str:>5} {bar} {pct:>6} {status}"
    )

    # Show error message if applicable
    if should_show_error_message(status_info):
        error_msg = truncate_text(task.error_message, 60)
        lines.append(f"    Error: {error_msg}")

    return lines


def format_processing_task_lines(
    task: TaskState,
    name_width: int,
    spinner: str,
) -> list[str]:
    """Format the main and optional error lines for a processing task.

    Args:
        task: TaskState to format
        name_width: Width for task name
        spinner: Spinner character to display

    Returns:
        List of formatted output lines

    """
    lines: list[str] = []
    phase_str = f"({task.phase}/{task.total_phases})"
    operation = OPERATION_NAMES.get(task.progress_type, "Processing")

    # Create status info for status determination
    status_info = TaskStatusInfo(
        is_finished=task.is_finished,
        success=task.success,
        description=task.description,
        error_message=task.error_message,
    )

    # Determine status symbol using helper function
    status = determine_task_status_symbol(status_info, spinner)

    name = truncate_text(task.name, name_width)
    lines.append(f"{phase_str} {operation} {name:<{name_width}} {status}")

    # Show warning message if applicable
    if should_show_warning_message(status_info):
        msg = truncate_text(task.description, 60)
        lines.append(f"    {msg}")
    # Show error message if applicable
    elif should_show_error_message(status_info):
        error_msg = truncate_text(task.error_message, 60)
        lines.append(f"    Error: {error_msg}")

    return lines


def render_api_section(
    tasks: dict[str, TaskState],
    order: list[str],
) -> list[str]:
    """Render API fetching section.

    Args:
        tasks: Dictionary of all tasks
        order: List of task IDs in order

    Returns:
        List of formatted output lines for API section

    """
    api_tasks = [
        t for t in order if tasks[t].progress_type == ProgressType.API_FETCHING
    ]

    if not api_tasks:
        return []

    lines = ["Fetching from API:"]
    for task_id in api_tasks:
        task = tasks[task_id]
        name = truncate_text(task.name, 18)

        if task.total > 0:
            completed = int(task.completed)
            total = int(task.total)
            if task.is_finished or completed >= total:
                if "cached" in task.description.lower():
                    status = f"{total}/{total} Retrieved from cache"
                else:
                    status = f"{total}/{total} Retrieved"
            else:
                status = f"{completed}/{total} Fetching..."
        elif task.is_finished:
            if "cached" in task.description.lower():
                status = "Retrieved from cache"
            else:
                status = "Retrieved"
        else:
            status = "Fetching..."

        lines.append(f"{name:20} {status}")

    lines.append("")
    return lines


def render_downloads_section(
    tasks: dict[str, TaskState],
    order: list[str],
    config: SectionRenderConfig,
) -> list[str]:
    """Render downloads section with progress bars.

    Args:
        tasks: Dictionary of all tasks
        order: List of task IDs in order
        config: SectionRenderConfig with rendering options

    Returns:
        List of formatted output lines for downloads section

    """
    download_tasks = [
        t for t in order if tasks[t].progress_type == ProgressType.DOWNLOAD
    ]

    if not download_tasks:
        return []

    display_names = {t: compute_display_name(tasks[t]) for t in download_tasks}

    max_name_width = compute_max_name_width(
        list(display_names.values()),
        config.interactive,
        config.min_name_width,
    )

    total_downloads = len(download_tasks)

    header = compute_download_header(total_downloads)

    lines = [header]
    for task_id in download_tasks:
        task = tasks[task_id]
        lines.extend(
            format_download_lines(task, max_name_width, config.bar_width)
        )

    lines.append("")
    return lines


def render_processing_section(
    tasks: dict[str, TaskState],
    order: list[str],
    config: SectionRenderConfig,
) -> list[str]:
    """Render installation/verification/post-processing section.

    Args:
        tasks: Dictionary of all tasks
        order: List of task IDs in order
        config: SectionRenderConfig with rendering options

    Returns:
        List of formatted output lines for processing section

    """
    post_tasks = [
        t
        for t in order
        if tasks[t].progress_type
        in (
            ProgressType.VERIFICATION,
            ProgressType.ICON_EXTRACTION,
            ProgressType.INSTALLATION,
            ProgressType.UPDATE,
        )
    ]

    if not post_tasks:
        return []

    has_verification = any(
        tasks[t].progress_type == ProgressType.VERIFICATION for t in post_tasks
    )
    has_installation = any(
        tasks[t].progress_type == ProgressType.INSTALLATION for t in post_tasks
    )

    if has_verification and not has_installation:
        section_header = "Verifying:"
    elif has_installation:
        section_header = "Installing:"
    else:
        section_header = "Processing:"

    lines = [section_header]

    spinner = compute_spinner(config.spinner_fps)

    app_tasks: dict[str, list[TaskState]] = {}
    for task_id in post_tasks:
        task = tasks[task_id]
        app_name = task.name
        app_tasks.setdefault(app_name, []).append(task)

    for app_task_list in app_tasks.values():
        tasks_sorted = sorted(app_task_list, key=lambda t: t.phase)

        name_width = calculate_dynamic_name_width(
            config.interactive, config.min_name_width
        )

        for task in tasks_sorted:
            lines.extend(
                format_processing_task_lines(task, name_width, spinner)
            )

    lines.append("")
    return lines
