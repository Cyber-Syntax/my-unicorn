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
from typing import TextIO

from my_unicorn.logger import get_logger
from my_unicorn.utils.progress_utils import (
    format_eta,
    format_percentage,
    human_mib,
    human_speed_bps,
    render_bar,
    truncate_text,
)

from .formatters import (
    TaskStatusInfo,
    determine_task_status_symbol,
    should_show_error_message,
    should_show_warning_message,
)
from .progress_types import (
    DEFAULT_MIN_NAME_WIDTH,
    DEFAULT_SPINNER_FPS,
    OPERATION_NAMES,
    SPINNER_FRAMES,
    ProgressConfig,
    ProgressType,
    TaskState,
)

logger = get_logger(__name__)


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

    def _format_download_lines(
        self, task: TaskState, max_name_width: int
    ) -> list[str]:
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

        # Create status info for status determination
        status_info = TaskStatusInfo(
            is_finished=current_task.is_finished,
            success=current_task.success,
            description=current_task.description,
            error_message=current_task.error_message,
        )

        # Determine status symbol using helper function
        status = determine_task_status_symbol(status_info, spinner)

        name = truncate_text(current_task.name, name_width)
        lines.append(f"{phase_str} {operation} {name:<{name_width}} {status}")

        # Show warning message if applicable
        if should_show_warning_message(status_info):
            msg = truncate_text(current_task.description, 60)
            lines.append(f"    {msg}")
        # Show error message if applicable
        elif should_show_error_message(status_info):
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

        for app_task_list in app_tasks.values():
            tasks_sorted = sorted(app_task_list, key=lambda t: t.phase)

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
