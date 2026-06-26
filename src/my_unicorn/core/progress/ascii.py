"""ASCII-based progress rendering backend.

This module provides the low-level rendering logic for progress displays
using plain ASCII characters and ANSI escape codes. It handles task state
management, output formatting, and terminal interactions for both interactive
and non-interactive modes.

Design notes:
- Concurrency: Uses `asyncio.Lock` for async rendering and `threading.Lock`
    for sync state updates. Snapshots state to ensure thread-safe rendering.
- Timing: Uses `time.monotonic()` for intervals to handle system clock changes.
- Output: Supports TTY detection, cursor control, and debounced
    non-interactive output.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from typing import TextIO

from my_unicorn.constants import APPIMAGE_SUFFIX
from my_unicorn.logger import get_logger
from my_unicorn.utils.progress_utils import (
    format_eta,
    format_percentage,
    human_mib,
    human_speed_bps,
    render_bar,
    truncate_text,
)

from .progress_types import (
    DEFAULT_BAR_WIDTH,
    DEFAULT_MIN_NAME_WIDTH,
    DEFAULT_SPINNER_FPS,
    PHASE_SECTION_LABELS,
    PROCESSING_LABELS,
    SPINNER_FRAMES,
    Phase,
    ProcessingPhase,
    ProgressConfig,
    TaskError,
    TaskState,
    TaskStatusInfo,
)

logger = get_logger(__name__)


def compute_display_name(task: TaskState) -> str:
    """Return a condensed display name for a task (strip extension).

    Args:
        task: The task state containing the name.

    Returns:
        The task name with .AppImage extension stripped if present.
    """
    name = task.name

    if name.endswith(APPIMAGE_SUFFIX):
        return name[: -len(APPIMAGE_SUFFIX)]
    return name


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


class AsciiProgressBackend:
    """ASCII-based progress rendering backend.

    Renders progress information using plain ASCII characters and ANSI
    escape codes for terminal output. Tasks stay in fixed positions
    and update in place.
    """

    def __init__(
        self,
        output: TextIO | None = None,
        interactive: bool | None = None,
        config: ProgressConfig | None = None,
    ) -> None:
        """Initialize ASCII progress backend.

        Args:
            output: Output stream (defaults to sys.stdout)
            interactive: Whether to use interactive mode with cursor control
                        (auto-detected from TTY if None)
            config: Optional `ProgressConfig` to control rendering
            (bar width and name width are taken from `config`)

        """
        self.output = output or sys.stdout
        # Robust TTY / interactive detection:
        # - Use provided `interactive` if explicit
        # - Otherwise, ensure `output` exposes .isatty() and TERM is not 'dumb'
        is_tty = False
        try:
            is_tty = bool(getattr(self.output, "isatty", lambda: False)())
        except Exception as exc:
            logger.debug("Failed to detect TTY: %s", exc)
            is_tty = False

        if interactive is not None:
            self.interactive = bool(interactive)
        else:
            term = os.environ.get("TERM", "")
            self.interactive = is_tty and term != "dumb"

        cfg = config or ProgressConfig()
        self.bar_width = getattr(cfg, "bar_width", DEFAULT_BAR_WIDTH)
        # Preserve `max_name_width` attribute for backward compatibility
        # (tests and external callers may inspect this private-ish attribute).
        self.max_name_width = getattr(cfg, "max_name_width", 20)
        self._min_name_width = getattr(
            cfg, "min_name_width", DEFAULT_MIN_NAME_WIDTH
        )
        self._spinner_fps = getattr(cfg, "spinner_fps", DEFAULT_SPINNER_FPS)

        # Create section render config for delegated rendering functions
        self._section_config = SectionRenderConfig(
            bar_width=self.bar_width,
            min_name_width=self._min_name_width,
            spinner_fps=self._spinner_fps,
            interactive=self.interactive,
        )

        self.tasks: dict[str, TaskState] = {}
        self._task_order: list[str] = []  # Maintain insertion order
        self._lock = asyncio.Lock()
        # Synchronous lock to protect shared state from sync writers
        # (writers may be called from non-async contexts)
        self._sync_lock = threading.Lock()

        # Terminal writer for managing output
        self._writer = TerminalWriter(self.output, self.interactive)

    def add_task(  # noqa: PLR0913
        self,
        task_id: str,
        name: str,
        progress_type: Phase,
        sub_type: ProcessingPhase | None = None,
        total: float = 0.0,
        parent_task_id: str | None = None,
        phase: int = 1,
        total_phases: int = 1,
    ) -> None:
        """Add a new task to track.

        Args:
            task_id: Unique task identifier
            name: Task name
            progress_type: Type of progress operation
            sub_type: Type of sub-progress operation
            total: Total units for the task
            parent_task_id: Parent task ID for multi-phase operations
            phase: Current phase number
            total_phases: Total number of phases

        """
        task = TaskState(
            task_id=task_id,
            name=name,
            progress_type=progress_type,
            sub_type=sub_type,
            total=total,
            created_at=time.time(),
            last_update=time.monotonic(),
            parent_task_id=parent_task_id,
            phase=phase,
            total_phases=total_phases,
        )
        # Protect modifications with sync lock
        with self._sync_lock:
            self.tasks[task_id] = task
            if task_id not in self._task_order:
                self._task_order.append(task_id)

    def update_task(
        self,
        task_id: str,
        completed: float | None = None,
        total: float | None = None,
        description: str | None = None,
        speed: float | None = None,
    ) -> None:
        """Update task progress.

        Args:
            task_id: Task identifier
            completed: Completed units (if updating)
            total: Total units (if updating)
            description: Task description (if updating)
            speed: Download speed in bytes/sec (if updating)

        """
        # Protect read/modify of shared state
        with self._sync_lock:
            if task_id not in self.tasks:
                logger.warning(
                    "Attempted to update non-existent task: %s", task_id
                )
                return

            task = self.tasks[task_id]
            if completed is not None:
                task.completed = completed
            if total is not None:
                task.total = total
            if description is not None:
                task.description = description
            if speed is not None:
                task.speed = speed
            task.last_update = time.monotonic()

    def finish_task(
        self,
        task_id: str,
        success: bool = True,  # noqa: FBT001, FBT002
        description: str | None = None,
        errors: list[TaskError] | None = None,
        warnings: list[TaskError] | None = None,
    ) -> None:
        """Mark a task as finished.

        Args:
            task_id: Task identifier
            success: Whether the task succeeded
            description: Final description (error message if failed)

        """
        # Protect read/modify of shared state
        with self._sync_lock:
            if task_id not in self.tasks:
                logger.warning(
                    "Attempted to finish non-existent task: %s", task_id
                )
                return

            task = self.tasks[task_id]
            task.is_finished = True
            task.success = success

            if description is not None:
                task.description = description

            if errors:
                task.errors.extend(errors)
            if warnings:
                task.warnings.extend(warnings)

            task.last_update = time.monotonic()

    def _build_output(self) -> str:
        """Build complete output string.

        Returns:
            Complete output string with all sections

        """
        # Snapshot live state and delegate to the snapshot-based builder to
        # avoid duplicating rendering logic.
        try:
            with self._sync_lock:
                tasks_snapshot = dict(self.tasks)
                order_snapshot = list(self._task_order)
        except Exception as exc:
            logger.debug("Failed to snapshot tasks: %s", exc)
            # skip one render frame, never read without lock
            return ""

        return self._build_output_from_snapshot(tasks_snapshot, order_snapshot)

    async def render_once(self) -> None:
        """Render current state once.

        This is the main rendering method that should be called periodically
        to update the display.
        """
        async with self._lock:
            # Snapshot shared state quickly under sync lock
            with self._sync_lock:
                tasks_snapshot = dict(self.tasks)
                order_snapshot = list(self._task_order)
                written_snapshot = set(self._writer._written_sections)  # noqa: SLF001

            # Build output from snapshot (pure function)
            output = self._build_output_from_snapshot(
                tasks_snapshot, order_snapshot
            )

            if not output:
                return

            if self.interactive:
                lines_written = self._writer.write_interactive(output)
                # Update writer state under sync lock
                with self._sync_lock:
                    self._writer._last_output_lines = lines_written  # noqa: SLF001
            else:
                added_sections = self._writer.write_noninteractive(
                    output, written_snapshot
                )
                with self._sync_lock:
                    if added_sections:
                        self._writer._written_sections.update(added_sections)  # noqa: SLF001
                        self._writer._last_noninteractive_output = output  # noqa: SLF001
                        self._writer._last_noninteractive_write_time = (  # noqa: SLF001
                            time.monotonic()
                        )

    async def cleanup(self) -> None:
        """Clean up and write final output."""
        async with self._lock:
            if self.interactive:
                # Final render with all completed tasks
                output = self._build_output()
                if output:
                    self._writer._clear_previous_output()  # noqa: SLF001
                    self.output.write(output + "\n")
                    self.output.flush()
                self._writer._last_output_lines = 0  # noqa: SLF001

            # Reset written sections for next session
            self._writer._written_sections.clear()  # noqa: SLF001

    def _build_output_from_snapshot(
        self, tasks_snapshot: dict[str, TaskState], order_snapshot: list[str]
    ) -> str:
        """Build output string using a snapshot of tasks and order.

        Delegates to section renderers from ascii_sections module.

        Args:
            tasks_snapshot: Snapshot of task states
            order_snapshot: Snapshot of task order

        Returns:
            Complete output string with all sections

        """
        lines: list[str] = []
        lines.extend(render_api_section(tasks_snapshot, order_snapshot))
        lines.extend(
            render_downloads_section(
                tasks_snapshot, order_snapshot, self._section_config
            )
        )
        lines.extend(
            render_processing_section(
                tasks_snapshot, order_snapshot, self._section_config
            )
        )
        return "\n".join(lines)


class TerminalWriter:
    """Manages terminal output for progress display.

    Handles both interactive (with cursor control) and non-interactive
    (with section deduplication) output modes. Tracks output state to
    enable proper clearing and avoid duplicate section headers.

    Attributes:
        output: Output stream (typically sys.stdout or StringIO for tests)
        interactive: Whether to use interactive mode with cursor control
        _last_output_lines: Number of lines written (interactive mode)
        _written_sections: Set of section signatures written (non-interactive)
        _last_noninteractive_output: Cached output (non-interactive)
        _last_noninteractive_write_time: Last write timestamp (non-interactive)
    """

    def __init__(self, output: TextIO, interactive: bool) -> None:  # noqa: FBT001
        """Initialize terminal writer.

        Args:
            output: Output stream for writing
            interactive: Whether to use interactive mode

        """
        self.output = output
        self.interactive = interactive

        # State for interactive mode
        self._last_output_lines = 0

        # State for non-interactive mode
        self._written_sections: set[str] = set()
        self._last_noninteractive_output = ""
        self._last_noninteractive_write_time = 0.0

    def _clear_previous_output(self) -> None:
        """Clear previously written lines in interactive mode."""
        if not self.interactive or self._last_output_lines == 0:
            return

        # Move cursor up to start of previous output
        self.output.write(f"\033[{self._last_output_lines}A")
        # Clear from cursor to end of screen
        self.output.write("\033[J")

        # Ensure output is written immediately
        self.output.flush()

    def _write_output_safe(self, text: str) -> None:
        """Write text to output stream, suppressing IO errors."""
        try:
            self.output.write(text)
            self.output.flush()
        except Exception as exc:
            logger.debug("Failed to write output: %s", exc)

    @staticmethod
    def _find_new_sections(
        output: str, known_sections: set[str]
    ) -> tuple[list[str], set[str]]:
        """Parse output and find sections not in known_sections.

        Args:
            output: Output string containing sections separated by blank lines
            known_sections: Set of section signatures already written

        Returns:
            Tuple of (new_sections_list, new_signatures_set)

        """
        sections = output.split("\n\n")
        new_sections: list[str] = []
        new_signatures: set[str] = set()

        for section in sections:
            section_sig = section.strip()
            if section_sig and section_sig not in known_sections:
                new_sections.append(section)
                new_signatures.add(section_sig)

        return new_sections, new_signatures

    def write_interactive(self, output: str) -> int:
        """Write output in interactive mode with cursor control.

        Args:
            output: Output string to write

        Returns:
            Number of lines written

        """
        self._clear_previous_output()

        if output:
            lines = output.split("\n")
            # Filter out trailing empty string from split to get accurate count
            if lines and lines[-1] == "":
                lines = lines[:-1]

            # Write all lines at once to minimize flickering
            output_text = "\n".join(lines) + "\n"
            try:
                self.output.write(output_text)
                self.output.flush()
            except Exception as exc:
                logger.debug("Failed to write output: %s", exc)

            # Return number of lines written and update writer state
            lines_written = len(lines)
            self._last_output_lines = lines_written

            return lines_written

        # Ensure last output lines is zero when nothing was written
        self._last_output_lines = 0
        return 0

    def write_noninteractive(
        self, output: str, known_sections: set[str] | None = None
    ) -> set[str]:
        """Write output in non-interactive mode (minimal output).

        Args:
            output: Output string to write
            known_sections: Optional set of already-written section signatures
                used to detect new/updated sections. If ``None``, the
                internal `_written_sections` set is used.

        Returns:
            Set of section signatures that were written

        """
        if not hasattr(self.output, "write"):
            return set()

        if "Summary:" in output:
            self._write_output_safe(output + "\n")
            return {output.strip()}

        if not output.strip():
            return set()

        if known_sections is None:
            known_sections = set(self._written_sections)

        new_sections, added_signatures = self._find_new_sections(
            output, known_sections
        )

        if new_sections:
            self._write_output_safe("\n\n".join(new_sections) + "\n")

        return added_signatures


# ASCII section rendering module.
# Pure functions for rendering progress sections (API, downloads, processing).
# These functions were extracted from AsciiProgressBackend for better
# separation of concerns and testability.


@dataclass(frozen=True, slots=True)
class SectionRenderConfig:
    """Configuration for section rendering.

    Groups shared settings to reduce parameter sprawl across
    section rendering functions.
    """

    bar_width: int = DEFAULT_BAR_WIDTH
    min_name_width: int = DEFAULT_MIN_NAME_WIDTH
    spinner_fps: int = DEFAULT_SPINNER_FPS
    interactive: bool = False


def determine_task_status_symbol(
    status_info: TaskStatusInfo,
    spinner: str,
) -> str:
    """Determine the status symbol for a task.

    Args:
        status_info: Task status information.
        spinner: Spinner character to use for in-progress tasks.

    Returns:
        Status symbol:
            ✓ = success
            ✖ = error
            ! = warning
            ? = unknown
            spinner = in-progress

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

    if status_info.success is True:
        return "✓"

    if status_info.success is False:
        return "✖"

    # success is None or unknown
    return "?"


def should_show_warning_message(status_info: TaskStatusInfo) -> bool:
    """Check if a warning message should be displayed.

    Args:
        status_info: Task status information.

    Returns:
        True if warning message should be shown.

    """
    return bool(
        status_info.warnings
        or ("not verified" in status_info.description.lower())
    )


def should_show_error_message(status_info: TaskStatusInfo) -> bool:
    """Check if an error message should be displayed.

    Args:
        status_info: Task status information.

    Returns:
        True if error message should be shown.

    """
    return bool(
        status_info.errors
        or (status_info.success is False and status_info.description)
    )


def calculate_dynamic_name_width(
    interactive: bool,  # noqa: FBT001
    min_name_width: int,
) -> int:
    """Calculate dynamic name width based on terminal size.

    Args:
        interactive: Whether in interactive mode
        min_name_width: Minimum width for name field

    Returns:
        Width to use for name (either full length or truncated)

    """
    # Width of right-aligned section: size + speed + eta + bar + pct
    # Formatted as: "    10.5 MiB    2.3 MB/s 2m 30s [======>     ] 100%"
    right_section_width = 10 + 1 + 10 + 1 + 7 + 1 + 32 + 1 + 4

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
    available_width = terminal_width - right_section_width

    # Use the smaller of: available width or actual name length
    # But ensure a minimum for readability
    return max(min_name_width, available_width)


def compute_max_name_width(
    display_names: list[str],
    interactive: bool,  # noqa: FBT001
    min_name_width: int = DEFAULT_MIN_NAME_WIDTH,
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


def _format_right_section(
    size: str,
    speed: str,
    eta: str,
    bar: str,
    pct: str,
) -> str:
    """Format the right-aligned section with size, speed, ETA, bar, percentage.

    Args:
        size: Formatted size string
        speed: Formatted speed string
        eta: Formatted ETA string
        bar: Progress bar string
        pct: Formatted percentage string

    Returns:
        Formatted right-aligned section

    """
    # Build the right section string
    return f"{size:>10}  {speed:>10} {eta:>7} {bar} {pct:>4}"


def format_download_lines(
    task: TaskState,
    max_name_width: int,
    bar_width: int,
    terminal_width: int | None = None,
) -> list[str]:
    """Format lines for a single download task (main + optional error).

    Args:
        task: TaskState to format
        max_name_width: Maximum width for task name
        bar_width: Width of progress bar
        terminal_width: Terminal width (auto-detect if None)

    Returns:
        List of formatted output lines

    """
    lines: list[str] = []
    display_name = compute_display_name(task)
    name = truncate_text(display_name, max_name_width)

    if terminal_width is None:
        try:
            terminal_width = shutil.get_terminal_size().columns
        except (AttributeError, ValueError, OSError):
            terminal_width = 80

    size_str = human_mib(task.total) if task.total > 0 else "--"
    speed_str = human_speed_bps(task.speed) if task.speed > 0 else "--"

    if task.speed > 0 and task.total > task.completed:
        remaining_bytes = task.total - task.completed
        eta_seconds = remaining_bytes / task.speed
        eta_str = format_eta(eta_seconds)
    else:
        eta_str = "--:--"

    bar = render_bar(task.completed, task.total, bar_width)
    pct = format_percentage(task.completed, task.total)

    # Format the right-aligned section
    right_section = _format_right_section(
        size_str, speed_str, eta_str, bar, pct
    )

    # Format: name on left, right section on right with padding
    name_section = f"{name:<{max_name_width}}"
    total_length = len(name_section) + len(right_section)

    if total_length < terminal_width:
        # Add padding to push right section to the right
        padding = terminal_width - total_length
        line = f"{name_section}{' ' * padding}{right_section}"
    else:
        # Not enough space, just concatenate with single space
        line = f"{name_section} {right_section}"

    lines.append(line)

    # process errors via TaskError
    if task.errors:
        for err in task.errors:
            msg = truncate_text(err.details, 120)
            lines.append(
                f"error: network error while downloading {task.name} : {msg}"
            )

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

    operation = PROCESSING_LABELS.get(task.sub_type)
    if operation is None:
        operation = "processing"

    operation_label = f"{operation[:1]}{operation[1:]}"

    # match ui design e.g "installing"
    name = truncate_text(task.name, name_width)

    # clean output without symbols
    lines.append(f"{phase_str} {operation_label} {name}")

    # Display Warnings/Errors
    if task.warnings:
        for warning in task.warnings:
            # example: "warning: checksum asset not found"
            msg = truncate_text(warning.details, 120)
            lines.append(f"warning: {msg}")

    if task.errors:
        for err in task.errors:
            # Example: "error: failed to install 'appflowy' : Permission denied"
            msg = truncate_text(err.details, 120)
            lines.append(f"error: failed to {operation} '{task.name}' : {msg}")

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
    header = PHASE_SECTION_LABELS.get(Phase.API_FETCHING)
    api_tasks = [
        t
        for t in order
        # using .get() prevents crashes if task state changes during rendering.
        if (task := tasks.get(t)) and task.progress_type == Phase.API_FETCHING
    ]

    if not api_tasks:
        return []

    lines = [header]
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
        t
        for t in order
        # Use .get() to guard against order/tasks snapshot divergence,
        if (task := tasks.get(t)) and task.progress_type == Phase.DOWNLOAD
    ]

    if not download_tasks:
        return []

    display_names = {t: compute_display_name(tasks[t]) for t in download_tasks}

    max_name_width = compute_max_name_width(
        list(display_names.values()),
        config.interactive,
        config.min_name_width,
    )

    # Get terminal width for right-alignment
    try:
        terminal_width = shutil.get_terminal_size().columns
    except (AttributeError, ValueError, OSError):
        terminal_width = 80

    total_downloads = len(download_tasks)

    header = PHASE_SECTION_LABELS.get(Phase.DOWNLOAD)

    lines = [header]
    for task_id in download_tasks:
        task = tasks[task_id]
        lines.extend(
            format_download_lines(
                task, max_name_width, config.bar_width, terminal_width
            )
        )

    # Add total summary line
    total_completed = sum(tasks[t].completed for t in download_tasks)
    total_size = sum(tasks[t].total for t in download_tasks)
    completed_count = sum(
        1 for t in download_tasks if tasks[t].is_finished and tasks[t].success
    )
    total_speed = (
        sum(tasks[t].speed for t in download_tasks) / len(download_tasks)
        if download_tasks
        else 0.0
    )

    if total_size > total_completed:
        remaining_bytes = total_size - total_completed
        eta_seconds = remaining_bytes / total_speed if total_speed > 0 else 0
        eta_str = format_eta(eta_seconds)
    else:
        eta_str = "--:--"

    size_str = human_mib(total_size)
    speed_str = human_speed_bps(total_speed)
    bar = render_bar(total_completed, total_size, config.bar_width)
    pct = format_percentage(total_completed, total_size)

    # Format the right-aligned section for total line
    right_section = _format_right_section(
        size_str, speed_str, eta_str, bar, pct
    )

    # Format total line with left-aligned label and right-aligned metrics
    total_label = f"Total ({completed_count}/{total_downloads})"
    name_section = f"{total_label:<{max_name_width}}"
    total_length = len(name_section) + len(right_section)

    if total_length < terminal_width:
        padding = terminal_width - total_length
        total_line = f"{name_section}{' ' * padding}{right_section}"
    else:
        total_line = f"{name_section} {right_section}"

    lines.append(total_line)
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
    installing_header = PHASE_SECTION_LABELS.get(Phase.PROCESSING)
    verifying_header = PROCESSING_LABELS.get(ProcessingPhase.VERIFICATION)

    post_tasks = [
        t
        for t in order
        # Use .get() to guard against order/tasks snapshot divergence,
        if (task := tasks.get(t)) and task.progress_type == Phase.PROCESSING
    ]

    if not post_tasks:
        return []

    sub_types = {
        tasks[t].sub_type for t in post_tasks if tasks[t].sub_type is not None
    }

    has_installation = ProcessingPhase.INSTALLATION in sub_types
    has_verification = ProcessingPhase.VERIFICATION in sub_types

    if has_verification and not has_installation:
        section_header = verifying_header
    elif has_installation:
        section_header = installing_header
    else:
        section_header = "processing"

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

    return lines
