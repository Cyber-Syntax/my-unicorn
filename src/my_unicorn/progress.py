"""Progress display with ASCII rendering backend.

This module provides a centralized progress display UI component that handles
different types of operations with ASCII-based visual feedback.

Design notes:
- Concurrency: the backend (`AsciiProgressBackend`) uses an
    `asyncio.Lock` to protect async rendering and a separate
    `threading.Lock` (`_sync_lock`) to protect state when synchronous
    callers update tasks. The renderer snapshots shared state while
    holding locks, releases them, and then formats output so rendering
    is safe for concurrent use.
- Timing: use `time.monotonic()` for measuring intervals (spinner
    frames, speed calculations, and debounce timestamps) so rendering is
    robust to system clock changes. Wall-clock creation timestamps may
    continue to use `time.time()` when appropriate.

Usage (simple, recommended):

    from my_unicorn.progress import progress_session

    async with progress_session() as progress:
        # create linked verification & installation tasks
        verification_id, installation_id = (
        await progress.create_installation_workflow("App")
        )
        # update/finish tasks as work proceeds

"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import sys
import threading
import time
from collections import OrderedDict, defaultdict, deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum, auto
from typing import TextIO

from my_unicorn.logger import get_logger
from my_unicorn.utils.progress_utils import (
    calculate_speed,
    format_eta,
    format_percentage,
    human_mib,
    human_speed_bps,
    render_bar,
    truncate_text,
)

logger = get_logger(__name__)

# caps the size of cached generated IDs to avoid unbounded growth.
ID_CACHE_LIMIT = 1000


class ProgressType(Enum):
    """Types of progress operations."""

    API_FETCHING = auto()
    DOWNLOAD = auto()
    VERIFICATION = auto()
    ICON_EXTRACTION = auto()
    INSTALLATION = auto()
    UPDATE = auto()


# Mapping from progress type to human-friendly operation name
OPERATION_NAMES: dict[ProgressType, str] = {
    ProgressType.VERIFICATION: "Verifying",
    ProgressType.INSTALLATION: "Installing",
    ProgressType.ICON_EXTRACTION: "Extracting icon",
    ProgressType.UPDATE: "Updating",
}

# Small tunables exposed for easier testing
DEFAULT_MIN_NAME_WIDTH: int = 15
DEFAULT_SPINNER_FPS: int = 4

# Spinner frames for in-progress tasks
SPINNER_FRAMES: list[str] = [
    "⠋",
    "⠙",
    "⠹",
    "⠸",
    "⠼",
    "⠴",
    "⠦",
    "⠧",
    "⠇",
    "⠏",
]


@dataclass(slots=True)
class TaskState:
    """State information for a single task in the backend."""

    task_id: str
    name: str
    progress_type: ProgressType
    total: float = 0.0
    completed: float = 0.0
    description: str = ""
    speed: float = 0.0  # bytes per second
    success: bool | None = None
    is_finished: bool = False
    created_at: float = 0.0
    last_update: float = 0.0
    error_message: str = ""
    # Multi-phase task tracking
    parent_task_id: str | None = None  # For tracking related tasks
    phase: int = 1  # Current phase (1 for verify, 2 for install)
    total_phases: int = 1  # Total number of phases


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
        except Exception:
            is_tty = False

        if interactive is not None:
            self.interactive = bool(interactive)
        else:
            term = os.environ.get("TERM", "")
            self.interactive = is_tty and term != "dumb"

        cfg = config or ProgressConfig()
        self.bar_width = getattr(cfg, "bar_width", 30)
        # Preserve `max_name_width` attribute for backward compatibility
        # (tests and external callers may inspect this private-ish attribute).
        self.max_name_width = getattr(cfg, "max_name_width", 20)
        self._min_name_width = getattr(
            cfg, "min_name_width", DEFAULT_MIN_NAME_WIDTH
        )
        self._spinner_fps = getattr(cfg, "spinner_fps", DEFAULT_SPINNER_FPS)

        self.tasks: dict[str, TaskState] = {}
        self._task_order: list[str] = []  # Maintain insertion order
        self._lock = asyncio.Lock()
        # Synchronous lock to protect shared state from sync writers
        # (writers may be called from non-async contexts)
        self._sync_lock = threading.Lock()
        self._last_output_lines = 0  # Track lines written for clearing

        # Non-interactive output cache to avoid duplicate headers and spam
        self._last_noninteractive_output: str = ""
        self._last_noninteractive_write_time: float = 0.0
        # Track which sections have been written to avoid duplicates
        self._written_sections: set[str] = set()

    # Helpers for downloads rendering (kept small and testable)
    def _compute_display_name(self, task: TaskState) -> str:
        """Return a condensed display name for a task (strip extension)."""
        name = task.name
        if name.endswith(".AppImage"):
            return name[:-9]
        return name

    def _compute_max_name_width(self, display_names: list[str]) -> int:
        """Compute maximum name width across downloads for alignment."""
        max_name_width = 0
        fixed_width = 10 + 10 + 5 + (self.bar_width + 2) + 6 + 1 + 6
        for display_name in display_names:
            name_width = self._calculate_dynamic_name_width(
                display_name, fixed_width
            )
            max_name_width = max(
                max_name_width, min(name_width, len(display_name))
            )
        return max_name_width

    def _format_download_lines(self, task: TaskState, max_name_width: int):
        """Format lines for a single download task (main + optional error)."""
        lines: list[str] = []
        display_name = self._compute_display_name(task)
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

        bar = render_bar(task.completed, task.total, self.bar_width)
        pct = format_percentage(task.completed, task.total)

        status = ("✓" if task.success else "✖") if task.is_finished else " "

        lines.append(
            f"{name:<{max_name_width}} {size_str} {speed_str} "
            f"{eta_str:>5} {bar} {pct:>6} {status}"
        )

        if task.is_finished and not task.success and task.error_message:
            error_msg = truncate_text(task.error_message, 60)
            lines.append(f"    Error: {error_msg}")

        return lines

    def add_task(  # noqa: PLR0913
        self,
        task_id: str,
        name: str,
        progress_type: ProgressType,
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
            total: Total units for the task
            parent_task_id: Parent task ID for multi-phase operations
            phase: Current phase number
            total_phases: Total number of phases

        """
        task = TaskState(
            task_id=task_id,
            name=name,
            progress_type=progress_type,
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
        success: bool = True,
        description: str | None = None,
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
                if not success and "Error:" not in description:
                    # Extract error message for cleaner display
                    task.error_message = description
                task.description = description
            task.last_update = time.monotonic()

    def _render_api_section(
        self,
        tasks_snapshot: dict[str, TaskState] | None = None,
        order_snapshot: list[str] | None = None,
    ) -> list[str]:
        """Render API fetching section.

        Accepts optional snapshots so callers can render from a copied
        state without holding backend locks.
        """
        order = (
            order_snapshot if order_snapshot is not None else self._task_order
        )
        tasks = tasks_snapshot if tasks_snapshot is not None else self.tasks

        api_tasks = [
            t
            for t in order
            if tasks[t].progress_type == ProgressType.API_FETCHING
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

    def _calculate_dynamic_name_width(
        self, name: str, fixed_width: int
    ) -> int:
        """Calculate dynamic name width based on terminal size.

        Args:
            name: The task name to display
            fixed_width: Width needed for fixed elements (size, speed, etc.)

        Returns:
            Width to use for name (either full length or truncated)

        """
        if self.interactive:
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
        min_width = self._min_name_width
        max_width = max(min_width, available_width)

        return min(len(name), max_width)

    def _format_api_task_status(self, task: TaskState) -> str:
        """Return the status string for an API fetching task."""
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

    def _select_current_task(
        self, tasks_sorted: list[TaskState]
    ) -> TaskState | None:
        """Select the current task to display for a multi-phase app.

        Preference order:
          - first unfinished task
          - first failed task
          - otherwise the last (completed) phase
        """
        return next(
            (
                t
                for t in tasks_sorted
                if (not t.is_finished) or (t.is_finished and not t.success)
            ),
            tasks_sorted[-1] if tasks_sorted else None,
        )

    def _compute_spinner(self) -> str:
        """Compute the current spinner frame based on time and FPS."""
        current_time = time.monotonic()
        spinner_idx = int(current_time * self._spinner_fps) % len(
            SPINNER_FRAMES
        )
        return SPINNER_FRAMES[spinner_idx]

    def _compute_download_header(self, total: int, completed: int) -> str:
        """Return the downloads section header string."""
        if total > 1:
            return f"Downloading ({completed}/{total}):"
        return "Downloading:"

    def _format_processing_task_lines(
        self, current_task: TaskState, name_width: int, spinner: str
    ) -> list[str]:
        """Format the main and optional error lines for a processing task."""
        lines: list[str] = []
        phase_str = f"({current_task.phase}/{current_task.total_phases})"
        operation = OPERATION_NAMES.get(
            current_task.progress_type, "Processing"
        )

        # Determine status symbol
        if current_task.is_finished:
            # Check for warning case (success but with "not verified" message)
            if (
                current_task.success
                and current_task.description
                and "not verified" in current_task.description.lower()
            ):
                status = "⚠"
            else:
                status = "✓" if current_task.success else "✖"
        else:
            status = spinner

        name = truncate_text(current_task.name, name_width)
        lines.append(f"{phase_str} {operation} {name:<{name_width}} {status}")

        # Show description for warning or error cases
        if current_task.is_finished:
            # For warning case (not verified)
            if (
                current_task.success
                and current_task.description
                and "not verified" in current_task.description.lower()
            ):
                msg = truncate_text(current_task.description, 60)
                lines.append(f"    {msg}")
            # For error case
            elif not current_task.success and current_task.error_message:
                error_msg = truncate_text(current_task.error_message, 60)
                lines.append(f"    Error: {error_msg}")

        return lines

    def _render_downloads_section(
        self,
        tasks_snapshot: dict[str, TaskState] | None = None,
        order_snapshot: list[str] | None = None,
    ) -> list[str]:
        """Render downloads section with progress bars.

        Returns a list of output lines. Accepts optional snapshots to render
        from a copied state.
        """
        order = (
            order_snapshot if order_snapshot is not None else self._task_order
        )
        tasks = tasks_snapshot if tasks_snapshot is not None else self.tasks

        download_tasks = [
            t for t in order if tasks[t].progress_type == ProgressType.DOWNLOAD
        ]

        if not download_tasks:
            return []

        display_names = {
            t: self._compute_display_name(tasks[t]) for t in download_tasks
        }

        max_name_width = self._compute_max_name_width(
            list(display_names.values())
        )

        total_downloads = len(download_tasks)
        completed_downloads = sum(
            1 for t in download_tasks if tasks[t].is_finished
        )

        header = self._compute_download_header(
            total_downloads, completed_downloads
        )

        lines = [header]
        for task_id in download_tasks:
            task = tasks[task_id]
            lines.extend(self._format_download_lines(task, max_name_width))

        lines.append("")
        return lines

    def _render_processing_section(
        self,
        tasks_snapshot: dict[str, TaskState] | None = None,
        order_snapshot: list[str] | None = None,
    ) -> list[str]:
        """Render installation/verification/post-processing section.

        Accepts optional snapshots for rendering from a copied state.
        """
        order = (
            order_snapshot if order_snapshot is not None else self._task_order
        )
        tasks = tasks_snapshot if tasks_snapshot is not None else self.tasks

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
            tasks[t].progress_type == ProgressType.VERIFICATION
            for t in post_tasks
        )
        has_installation = any(
            tasks[t].progress_type == ProgressType.INSTALLATION
            for t in post_tasks
        )

        if has_verification and not has_installation:
            section_header = "Verifying:"
        elif has_installation:
            section_header = "Installing:"
        else:
            section_header = "Processing:"

        lines = [section_header]

        spinner = self._compute_spinner()

        app_tasks: dict[str, list[TaskState]] = {}
        for task_id in post_tasks:
            task = tasks[task_id]
            app_name = task.name
            app_tasks.setdefault(app_name, []).append(task)

        for _app_name, tasks in app_tasks.items():
            tasks_sorted = sorted(tasks, key=lambda t: t.phase)

            fixed_width = 5 + 1 + 16 + 1 + 1 + 1
            name_width = self._calculate_dynamic_name_width(
                tasks_sorted[-1].name, fixed_width
            )

            for task in tasks_sorted:
                lines.extend(
                    self._format_processing_task_lines(
                        task, name_width, spinner
                    )
                )

        lines.append("")
        return lines

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
        except Exception:
            tasks_snapshot = dict(self.tasks)
            order_snapshot = list(self._task_order)

        return self._build_output_from_snapshot(tasks_snapshot, order_snapshot)

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

    def _write_interactive(self, output: str) -> int:
        """Write output in interactive mode with cursor control.

        Args:
            output: Output string to write

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
            except Exception:
                # swallow IO errors
                pass

            # Return number of lines written and update writer state
            lines_written = len(lines)
            try:
                with self._sync_lock:
                    self._last_output_lines = lines_written
            except Exception:
                # best-effort: do not fail render on sync-lock issues
                pass

            return lines_written

        # Ensure last output lines is zero when nothing was written
        try:
            with self._sync_lock:
                self._last_output_lines = 0
        except Exception:
            pass
        return 0

    def _write_output_safe(self, text: str) -> None:
        """Write text to output stream, suppressing IO errors."""
        try:
            self.output.write(text)
            self.output.flush()
        except Exception:
            pass

    def _find_new_sections(
        self, output: str, known_sections: set[str]
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

    def _write_noninteractive(
        self, output: str, known_sections: set[str] | None = None
    ) -> set[str]:
        """Write output in non-interactive mode (minimal output).

        Args:
            output: Output string to write
            known_sections: Optional set of already-written section signatures
                used to detect new/updated sections. If ``None``, the
                backend's internal `_written_sections` set is used.

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
                written_snapshot = set(self._written_sections)

            # Build output from snapshot (pure function)
            output = self._build_output_from_snapshot(
                tasks_snapshot, order_snapshot
            )

            if not output:
                return

            if self.interactive:
                lines_written = self._write_interactive(output)
                # Update writer state under sync lock
                with self._sync_lock:
                    self._last_output_lines = lines_written
            else:
                added_sections = self._write_noninteractive(
                    output, written_snapshot
                )
                with self._sync_lock:
                    if added_sections:
                        self._written_sections.update(added_sections)
                        self._last_noninteractive_output = output
                        self._last_noninteractive_write_time = time.monotonic()

    async def cleanup(self) -> None:
        """Clean up and write final output."""
        async with self._lock:
            if self.interactive:
                # Final render with all completed tasks
                output = self._build_output()
                if output:
                    self._clear_previous_output()
                    self.output.write(output + "\n")
                    self.output.flush()
                self._last_output_lines = 0

            # Reset written sections for next session
            self._written_sections.clear()

    def _build_output_from_snapshot(
        self, tasks_snapshot: dict[str, TaskState], order_snapshot: list[str]
    ) -> str:
        """Build output string using a snapshot of tasks and order.

        Delegates to the existing section renderers to avoid code duplication.

        Args:
            tasks_snapshot: Snapshot of task states
            order_snapshot: Snapshot of task order

        Returns:
            Complete output string with all sections

        """
        lines: list[str] = []
        lines.extend(self._render_api_section(tasks_snapshot, order_snapshot))
        lines.extend(
            self._render_downloads_section(tasks_snapshot, order_snapshot)
        )
        lines.extend(
            self._render_processing_section(tasks_snapshot, order_snapshot)
        )
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ProgressConfig:
    """Configuration for progress display."""

    refresh_per_second: int = 4
    show_overall: bool = False
    show_api_fetching: bool = True
    show_downloads: bool = True
    show_post_processing: bool = True
    batch_ui_updates: bool = True
    ui_update_interval: float = 0.25  # Seconds between batched UI updates
    speed_calculation_interval: float = (
        0.5  # Minimum interval for speed recalculation
    )
    max_speed_history: int = 10  # Number of speed measurements to retain

    # Display tuning
    bar_width: int = 30
    min_name_width: int = DEFAULT_MIN_NAME_WIDTH
    spinner_fps: int = DEFAULT_SPINNER_FPS
    max_name_width: int = 20

    def __post_init__(self) -> None:
        """Validate config fields to prevent invalid runtime values."""
        # Basic validation to catch obviously invalid configs early.
        if self.refresh_per_second < 1:
            raise ValueError("refresh_per_second must be >= 1")
        if self.bar_width < 1:
            raise ValueError("bar_width must be >= 1")
        if self.spinner_fps < 1:
            raise ValueError("spinner_fps must be >= 1")


@dataclass(slots=True)
class TaskInfo:
    """Task information with all metadata in one structure."""

    # Core task data
    task_id: str
    namespaced_id: str
    name: str
    progress_type: ProgressType
    total: float = 0.0
    completed: float = 0.0
    description: str = ""
    success: bool | None = None
    is_finished: bool = False

    # Timing data
    created_at: float = 0.0
    last_update: float = 0.0
    last_speed_update: float = 0.0

    # Speed tracking for downloads
    current_speed_mbps: float = 0.0
    # (timestamp, speed) pairs
    speed_history: deque[tuple[float, float]] | None = None

    # Multi-phase task tracking
    parent_task_id: str | None = None
    phase: int = 1
    total_phases: int = 1

    def __post_init__(self) -> None:
        """Initialize speed history deque."""
        if self.speed_history is None:
            # Use configured max history length (no magic number)
            maxlen = ProgressConfig().max_speed_history
            self.speed_history = deque(maxlen=maxlen)


class ProgressDisplay:
    """Progress display UI component using ASCII backend."""

    def __init__(
        self,
        config: ProgressConfig | None = None,
        interactive: bool | None = None,
    ) -> None:
        """Initialize progress display.

        Args:
            config: Progress configuration
            interactive: Whether to use interactive mode
                        (auto-detected if None)

        """
        self.config = config or ProgressConfig()
        self._backend = AsciiProgressBackend(
            config=self.config, interactive=interactive
        )

        # State management
        self._tasks: dict[str, TaskInfo] = {}  # Use namespaced IDs as keys
        self._active: bool = False
        self._task_lock = asyncio.Lock()

        # Task ID tracking to prevent collisions
        self._task_counters: dict[ProgressType, int] = defaultdict(int)
        # Use OrderedDict for simple LRU eviction semantics
        self._id_cache: OrderedDict[tuple[ProgressType, str], str] = (
            OrderedDict()
        )

        # Task sets for fast lookup
        self._task_sets: dict[ProgressType, set[str]] = {
            ProgressType.API_FETCHING: set(),
            ProgressType.DOWNLOAD: set(),
            ProgressType.VERIFICATION: set(),
            ProgressType.ICON_EXTRACTION: set(),
            ProgressType.INSTALLATION: set(),
            ProgressType.UPDATE: set(),
        }

        # Background rendering task
        self._render_task: asyncio.Task | None = None
        self._stop_rendering: asyncio.Event = asyncio.Event()

    def _generate_namespaced_id(
        self, progress_type: ProgressType, name: str
    ) -> str:
        """Generate a unique namespaced ID for a task with optimized caching.

        Args:
            progress_type: Type of progress operation
            name: Task name

        Returns:
            Unique namespaced ID

        """
        # Check cache first (move-to-end on access)
        cache_key = (progress_type, name)
        if cache_key in self._id_cache:
            # OrderedDict.move_to_end may raise on unusual implementations;
            # suppress exceptions as caching is best-effort.
            with contextlib.suppress(Exception):
                self._id_cache.move_to_end(cache_key)
            return self._id_cache[cache_key]

        self._task_counters[progress_type] += 1
        counter = self._task_counters[progress_type]

        # Type prefix mapping for readable IDs
        type_prefixes = {
            ProgressType.API_FETCHING: "api",
            ProgressType.DOWNLOAD: "dl",
            ProgressType.VERIFICATION: "vf",
            ProgressType.ICON_EXTRACTION: "ic",
            ProgressType.INSTALLATION: "in",
            ProgressType.UPDATE: "up",
        }

        type_prefix = type_prefixes[progress_type]

        # Sanitize name for use in ID
        clean_name = "".join(c for c in name if c.isalnum() or c in "-_.")[:20]
        # Fallback when sanitization yields empty name
        if not clean_name:
            clean_name = "unnamed"

        namespaced_id = f"{type_prefix}_{counter}_{clean_name}"

        # Cache the result with simple LRU eviction when limit exceeded
        self._id_cache[cache_key] = namespaced_id
        if len(self._id_cache) > ID_CACHE_LIMIT:
            with contextlib.suppress(Exception):
                self._id_cache.popitem(last=False)

        return namespaced_id

    def _clear_id_cache(self) -> None:
        """Clear the ID generation cache."""
        self._id_cache.clear()

    async def _render_loop(self) -> None:
        """Background loop for rendering progress updates."""
        interval = 1.0 / self.config.refresh_per_second

        while not self._stop_rendering.is_set():
            try:
                await self._backend.render_once()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Error in render loop: %s", e)

    async def start_session(self, total_operations: int = 0) -> None:
        """Start a progress display session.

        Args:
            total_operations: Total number of operations (currently unused)

        """
        if self._active:
            logger.warning("Progress session already active")
            return

        self._active = True
        self._stop_rendering.clear()

        # Start background rendering loop
        self._render_task = asyncio.create_task(self._render_loop())

        logger.debug(
            "Progress session started with %d total operations",
            total_operations,
        )

    async def stop_session(self) -> None:
        """Stop the progress display session."""
        if not self._active:
            return

        self._active = False
        self._stop_rendering.set()

        # Stop rendering task
        if self._render_task:
            self._render_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._render_task
            self._render_task = None

        # Final cleanup render
        await self._backend.cleanup()

        # Clear cached state
        self._clear_id_cache()

        logger.debug("Progress session stopped")

    async def add_task(  # noqa: PLR0913
        self,
        name: str,
        progress_type: ProgressType,
        total: float = 0.0,
        description: str | None = None,
        parent_task_id: str | None = None,
        phase: int = 1,
        total_phases: int = 1,
    ) -> str:
        """Add a new progress task.

        Args:
            name: Task name
            progress_type: Type of progress operation
            total: Total units for the task
            description: Task description
            parent_task_id: Parent task ID for multi-phase operations
            phase: Current phase number
            total_phases: Total number of phases

        Returns:
            Unique namespaced task ID

        """
        if not self._active:
            raise RuntimeError("Progress session not active")

        # Generate description if not provided
        if description is None:
            description = (
                f"📦 {name}"
                if progress_type == ProgressType.DOWNLOAD
                else f"⚙️ {name}"
            )

        # Generate unique namespaced ID
        namespaced_id = self._generate_namespaced_id(progress_type, name)

        # Create task info structure
        current_time = time.monotonic()
        task_info = TaskInfo(
            task_id=namespaced_id,
            namespaced_id=namespaced_id,
            name=name,
            progress_type=progress_type,
            total=total,
            description=description,
            created_at=current_time,
            last_update=current_time,
            last_speed_update=current_time,  # Initialize to created time
            parent_task_id=parent_task_id,
            phase=phase,
            total_phases=total_phases,
        )

        async with self._task_lock:
            # Store task info in consolidated structure
            self._tasks[namespaced_id] = task_info

            # Add to appropriate task set for fast lookup
            self._task_sets[progress_type].add(namespaced_id)

        # Add task to backend
        self._backend.add_task(
            task_id=namespaced_id,
            name=name,
            progress_type=progress_type,
            total=total,
            parent_task_id=parent_task_id,
            phase=phase,
            total_phases=total_phases,
        )

        # Perform an immediate render to make short-lived phases visible.
        # Awaiting the render here ensures the UI is updated before callers
        # may immediately finish the next phase (common in fast unit tests
        # or synchronous flows).
        with contextlib.suppress(Exception):
            await self._backend.render_once()

        logger.debug(
            "Added %s task: %s (total: %.1f)",
            progress_type.name,
            name,
            total,
        )

        return namespaced_id

    def _calculate_speed(
        self, task_info: TaskInfo, completed: float, current_time: float
    ) -> float:
        """Calculate download speed using moving average.

        Args:
            task_info: Task information
            completed: Completed bytes
            current_time: Current timestamp

        Returns:
            Speed in bytes per second

        """
        # Delegate calculation to the pure helper which returns an average
        # speed (bytes/sec) and an updated history (does not mutate caller).
        avg_speed_bps, updated_history = calculate_speed(
            prev_completed=task_info.completed,
            prev_time=task_info.last_speed_update,
            speed_history=task_info.speed_history,
            completed=completed,
            current_time=current_time,
            max_history=self.config.max_speed_history,
        )

        # If helper returned 0 (no new data) fall back to previously
        # recorded speed (stored in MB/s) to preserve previous behavior.
        if avg_speed_bps == 0.0:
            if task_info.current_speed_mbps > 0:
                return task_info.current_speed_mbps * (1024 * 1024)
            return 0.0

        # Persist updated history back to task_info (caller expects mutation)
        task_info.speed_history = updated_history

        return avg_speed_bps

    async def update_task(
        self,
        task_id: str,
        completed: float | None = None,
        total: float | None = None,
        description: str | None = None,
    ) -> None:
        """Update task progress.

        Args:
            task_id: Task identifier
            completed: Completed units (if updating)
            total: Total units (if updating)
            description: Task description (if updating)

        """
        async with self._task_lock:
            if task_id not in self._tasks:
                logger.warning("Task not found: %s", task_id)
                return

            task_info = self._tasks[task_id]
            current_time = time.monotonic()

            # Calculate speed for download tasks
            speed_bps = 0.0
            if (
                completed is not None
                and task_info.progress_type == ProgressType.DOWNLOAD
            ):
                speed_bps = self._calculate_speed(
                    task_info, completed, current_time
                )
                task_info.current_speed_mbps = speed_bps / (1024 * 1024)
                task_info.last_speed_update = current_time

            # Update task info
            if completed is not None:
                task_info.completed = completed
            if total is not None:
                task_info.total = total
            if description is not None:
                task_info.description = description
            task_info.last_update = current_time

        # Update backend
        self._backend.update_task(
            task_id=task_id,
            completed=completed,
            total=total,
            description=description,
            speed=speed_bps,
        )

        # No immediate render here — the background render loop will
        # pick up rapid updates. For short-lived phases we trigger an
        # initial render in `add_task` to ensure phase visibility.

    async def update_task_total(self, task_id: str, total: float) -> None:
        """Update task total separately.

        Args:
            task_id: Task identifier
            total: New total value

        """
        await self.update_task(task_id, total=total)

    async def finish_task(
        self,
        task_id: str,
        success: bool = True,
        description: str | None = None,
    ) -> None:
        """Mark a task as finished.

        Args:
            task_id: Task identifier
            success: Whether the task succeeded
            description: Final description

        """
        async with self._task_lock:
            if task_id not in self._tasks:
                logger.warning("Task not found: %s", task_id)
                return

            task_info = self._tasks[task_id]
            task_info.is_finished = True
            task_info.success = success

            if description is not None:
                task_info.description = description

            # Mark as completed if successful
            if success and task_info.total > 0:
                task_info.completed = task_info.total

        # Update backend
        self._backend.finish_task(
            task_id=task_id, success=success, description=description
        )

        # Let the regular render loop handle finished states; avoid
        # scheduling extra renders here to reduce duplicate output.

        logger.debug(
            "Finished task: %s (success: %s)",
            task_id,
            success,
        )

    @asynccontextmanager
    async def session(
        self, total_operations: int = 0
    ) -> AsyncGenerator[None, None]:
        """Context manager for progress session.

        Args:
            total_operations: Total number of operations

        Yields:
            None

        """
        await self.start_session(total_operations)
        try:
            yield
        finally:
            await self.stop_session()

    def get_task_info(self, task_id: str) -> TaskInfo | None:
        """Get task information by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task information or None if not found

        """
        return self._tasks.get(task_id)

    def is_active(self) -> bool:
        """Check if progress session is active.

        Returns:
            True if active, False otherwise

        """
        return self._active

    async def create_api_fetching_task(
        self, name: str, description: str | None = None
    ) -> str:
        """Create an API fetching task.

        Args:
            name: Task name
            description: Task description

        Returns:
            Task ID

        """
        return await self.add_task(
            name=name,
            progress_type=ProgressType.API_FETCHING,
            description=description or f"Fetching {name}",
        )

    async def create_verification_task(
        self, name: str, description: str | None = None
    ) -> str:
        """Create a verification task.

        Args:
            name: Task name
            description: Task description

        Returns:
            Task ID

        """
        return await self.add_task(
            name=name,
            progress_type=ProgressType.VERIFICATION,
            description=description or f"Verifying {name}",
        )

    async def create_installation_workflow(
        self, name: str, with_verification: bool = True
    ) -> tuple[str | None, str]:
        """Create a multi-phase installation workflow.

        This creates linked verification and installation tasks for the
        same app.
        The verification task is phase 1/2, and installation is phase 2/2.

        Args:
            name: Application name
            with_verification: Whether to create a verification task

        Returns:
            Tuple of (verification_task_id, installation_task_id)
            verification_task_id will be None if with_verification=False

        """
        verification_task_id = None

        if with_verification:
            # Create verification task as phase 1/2
            verification_task_id = await self.add_task(
                name=name,
                progress_type=ProgressType.VERIFICATION,
                description=f"Verifying {name}",
                phase=1,
                total_phases=2,
            )

            # Create installation task as phase 2/2
            installation_task_id = await self.add_task(
                name=name,
                progress_type=ProgressType.INSTALLATION,
                description=f"Installing {name}",
                parent_task_id=verification_task_id,
                phase=2,
                total_phases=2,
            )
        else:
            # Create installation task as phase 1/1 (no verification)
            installation_task_id = await self.add_task(
                name=name,
                progress_type=ProgressType.INSTALLATION,
                description=f"Installing {name}",
                phase=1,
                total_phases=1,
            )

        return verification_task_id, installation_task_id


# Global progress service instance
_progress_service: ProgressDisplay | None = None


def get_progress_service() -> ProgressDisplay | None:
    """Get the global progress service instance.

    Returns:
        Progress service instance or None

    """
    return _progress_service


def set_progress_service(service: ProgressDisplay | None) -> None:
    """Set the global progress service instance.

    Args:
        service: Progress service instance

    """
    global _progress_service  # noqa: PLW0603
    _progress_service = service


@asynccontextmanager
async def progress_session(
    total_operations: int = 0,
) -> AsyncGenerator[ProgressDisplay, None]:
    """Context manager for creating and managing a progress session.

    Args:
        total_operations: Total number of operations

    Yields:
        Progress display instance

    """
    service = get_progress_service()
    if service is None:
        service = ProgressDisplay()
        set_progress_service(service)

    async with service.session(total_operations):
        yield service
