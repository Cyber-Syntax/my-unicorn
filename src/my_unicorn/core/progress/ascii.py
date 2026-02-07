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
import sys
import threading
import time
from typing import TextIO

from my_unicorn.logger import get_logger

from .ascii_sections import (
    SectionRenderConfig,
    render_api_section,
    render_downloads_section,
    render_processing_section,
)
from .progress_types import (
    DEFAULT_MIN_NAME_WIDTH,
    DEFAULT_SPINNER_FPS,
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
        self._last_output_lines = 0  # Track lines written for clearing

        # Non-interactive output cache to avoid duplicate headers and spam
        self._last_noninteractive_output: str = ""
        self._last_noninteractive_write_time: float = 0.0
        # Track which sections have been written to avoid duplicates
        self._written_sections: set[str] = set()

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
