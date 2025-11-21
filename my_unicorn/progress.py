"""Progress display with ASCII rendering backend.

This module provides a centralized progress display UI component that handles
different types of operations with ASCII-based visual feedback.
"""

import asyncio
import contextlib
import os
import shutil
import sys
import time
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum, auto
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
        bar_width: int = 30,
        max_name_width: int = 20,
    ) -> None:
        """Initialize ASCII progress backend.

        Args:
            output: Output stream (defaults to sys.stdout)
            interactive: Whether to use interactive mode with cursor control
                        (auto-detected from TTY if None)
            bar_width: Width of progress bars in characters
            max_name_width: Maximum width for task names (fallback value)

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

        self.bar_width = bar_width
        self.max_name_width = max_name_width

        self.tasks: dict[str, TaskState] = {}
        self._task_order: list[str] = []  # Maintain insertion order
        self._lock = asyncio.Lock()
        self._last_output_lines = 0  # Track lines written for clearing

        # Non-interactive output cache to avoid duplicate headers and spam
        self._last_noninteractive_output: str = ""
        self._last_noninteractive_write_time: float = 0.0
        self._noninteractive_write_min_interval: float = 0.25
        # Track which sections have been written to avoid duplicates
        self._written_sections: set[str] = set()

    def add_task(
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
            last_update=time.time(),
            parent_task_id=parent_task_id,
            phase=phase,
            total_phases=total_phases,
        )
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
        task.last_update = time.time()

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
        task.last_update = time.time()

    def _render_api_section(self) -> list[str]:
        """Render API fetching section.

        Returns:
            List of output lines

        """
        api_tasks = [
            t
            for t in self._task_order
            if self.tasks[t].progress_type == ProgressType.API_FETCHING
        ]

        if not api_tasks:
            return []

        lines = ["Fetching from API:"]
        for task_id in api_tasks:
            task = self.tasks[task_id]
            name = truncate_text(task.name, 18)

            # Show progress counter if we have total/completed
            if task.total > 0:
                completed = int(task.completed)
                total = int(task.total)
                # Treat task as retrieved either when explicitly finished
                # or when completed bytes are greater than or equal to total.
                if task.is_finished or completed >= total:
                    # Check if data came from cache
                    if "cached" in task.description.lower():
                        status = f"{total}/{total}        Retrieved from cache"
                    else:
                        status = f"{total}/{total}        Retrieved"
                else:
                    status = f"{completed}/{total}        Fetching..."
            elif task.is_finished:
                # Check if data came from cache
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
        # But ensure minimum of 15 characters for readability
        min_width = 15
        max_width = max(min_width, available_width)

        return min(len(name), max_width)

    def _render_downloads_section(self) -> list[str]:
        """Render downloads section with progress bars.

        Returns:
            List of output lines

        """
        download_tasks = [
            t
            for t in self._task_order
            if self.tasks[t].progress_type == ProgressType.DOWNLOAD
        ]

        if not download_tasks:
            return []

        # First pass: determine the maximum name width for alignment
        max_name_width = 0
        display_names = {}
        for task_id in download_tasks:
            task = self.tasks[task_id]
            # Remove .AppImage extension from display name to save space
            display_name = task.name
            if display_name.endswith(".AppImage"):
                display_name = display_name[:-9]  # Remove ".AppImage"
            display_names[task_id] = display_name

            # Calculate fixed width needed for right-aligned elements
            # size(10) + speed(10) + eta(5) + bar(30+2) + pct(6) + status(1)
            # + spacing between elements (6 spaces)
            fixed_width = 10 + 10 + 5 + (self.bar_width + 2) + 6 + 1 + 6

            # Get dynamic name width for this task
            name_width = self._calculate_dynamic_name_width(
                display_name, fixed_width
            )
            max_name_width = max(
                max_name_width, min(name_width, len(display_name))
            )

        # Count total and completed downloads from task states
        total_downloads = len(download_tasks)
        completed_downloads = sum(
            1 for t in download_tasks if self.tasks[t].is_finished
        )

        # Show counter if we have multiple downloads
        if total_downloads > 1:
            header = f"Downloading ({completed_downloads}/{total_downloads}):"
        else:
            header = "Downloading:"

        lines = [header]
        for task_id in download_tasks:
            task = self.tasks[task_id]
            display_name = display_names[task_id]

            # Truncate name if needed, then left-align to max width
            name = truncate_text(display_name, max_name_width)

            # Format size
            size_str = (
                f"{human_mib(task.total):>10}"
                if task.total > 0
                else "    --    "
            )

            # Format speed
            speed_str = (
                f"{human_speed_bps(task.speed):>10}"
                if task.speed > 0
                else "   --     "
            )

            # Calculate ETA
            if task.speed > 0 and task.total > task.completed:
                remaining_bytes = task.total - task.completed
                eta_seconds = remaining_bytes / task.speed
                eta_str = format_eta(eta_seconds)
            else:
                eta_str = "00:00"

            # Format progress bar
            bar = render_bar(task.completed, task.total, self.bar_width)
            pct = format_percentage(task.completed, task.total)

            # Status icon
            if task.is_finished:
                status = "✓" if task.success else "✖"
            else:
                status = " "

            # Main line with left-aligned name and right-aligned columns
            lines.append(
                f"{name:<{max_name_width}} {size_str} {speed_str} "
                f"{eta_str:>5} {bar} {pct:>6} {status}"
            )

            # Error line if failed
            if task.is_finished and not task.success and task.error_message:
                error_msg = truncate_text(task.error_message, 60)
                lines.append(f"    Error: {error_msg}")

        lines.append("")
        return lines

    def _render_processing_section(self) -> list[str]:
        """Render installation/verification/post-processing section.

        Returns:
            List of output lines

        """
        post_tasks = [
            t
            for t in self._task_order
            if self.tasks[t].progress_type
            in (
                ProgressType.VERIFICATION,
                ProgressType.ICON_EXTRACTION,
                ProgressType.INSTALLATION,
                ProgressType.UPDATE,
            )
        ]

        if not post_tasks:
            return []

        # Determine section header based on task types present
        # Priority: Verifying > Installing > Processing
        has_verification = any(
            self.tasks[t].progress_type == ProgressType.VERIFICATION
            for t in post_tasks
        )
        has_installation = any(
            self.tasks[t].progress_type == ProgressType.INSTALLATION
            for t in post_tasks
        )

        if has_verification and not has_installation:
            section_header = "Verifying:"
        elif has_installation:
            section_header = "Installing:"
        else:
            section_header = "Processing:"

        lines = [section_header]

        # Spinner frames for in-progress tasks
        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        current_time = time.time()
        spinner_idx = int(current_time * 4) % len(spinner_frames)
        spinner = spinner_frames[spinner_idx]

        # Group tasks by app name to show only current phase per app
        app_tasks: dict[str, list[TaskState]] = {}
        for task_id in post_tasks:
            task = self.tasks[task_id]
            app_name = task.name

            if app_name not in app_tasks:
                app_tasks[app_name] = []
            app_tasks[app_name].append(task)

        # Process each app, showing only the latest/current phase
        for _app_name, tasks in app_tasks.items():
            # Sort by phase to determine which task to show
            # Multi-phase workflows: verification (1) → installation (2)
            tasks_sorted = sorted(tasks, key=lambda t: t.phase)

            # Find the current task to display:
            # - If verification is not finished, show verification
            # - If verification is finished, show installation
            # - Otherwise show the latest task
            current_task = None
            for task in tasks_sorted:
                if not task.is_finished:
                    # Show first unfinished task
                    current_task = task
                    break
                elif task.is_finished and not task.success:
                    # Show failed task
                    current_task = task
                    break

            # If all tasks are finished successfully, show the last one
            if current_task is None and tasks_sorted:
                current_task = tasks_sorted[-1]

            if current_task is None:
                continue

            # Determine phase indicator and operation name
            phase_str = f"({current_task.phase}/{current_task.total_phases})"

            if current_task.progress_type == ProgressType.VERIFICATION:
                operation = "Verifying"
            elif current_task.progress_type == ProgressType.INSTALLATION:
                operation = "Installing"
            elif current_task.progress_type == ProgressType.ICON_EXTRACTION:
                operation = "Extracting icon"
            elif current_task.progress_type == ProgressType.UPDATE:
                operation = "Updating"
            else:
                operation = "Processing"

            # Calculate fixed width for phase(5) + operation(~16) + status(1)
            # Format: "{phase} {operation} {name} {status}"
            # Spacing: 3 spaces between elements
            fixed_width = 5 + 1 + 16 + 1 + 1 + 1

            # Get dynamic name width
            name_width = self._calculate_dynamic_name_width(
                current_task.name, fixed_width
            )
            name = truncate_text(current_task.name, name_width)

            # Determine status symbol
            if current_task.is_finished:
                # Task itself is finished - show its result
                status = "✓" if current_task.success else "✖"
            else:
                # Task in progress
                status = spinner

            lines.append(
                f"{phase_str} {operation} {name:<{name_width}} {status}"
            )

            # Error line if failed
            if (
                current_task.is_finished
                and not current_task.success
                and current_task.error_message
            ):
                error_msg = truncate_text(current_task.error_message, 60)
                lines.append(f"    Error: {error_msg}")

        lines.append("")
        return lines

    def _build_output(self) -> str:
        """Build complete output string.

        Returns:
            Complete output string with all sections

        """
        lines: list[str] = []

        # Add sections only if they have content
        api_lines = self._render_api_section()
        download_lines = self._render_downloads_section()
        processing_lines = self._render_processing_section()

        # Only show sections that have tasks
        if api_lines:
            lines.extend(api_lines)
        if download_lines:
            lines.extend(download_lines)
        if processing_lines:
            lines.extend(processing_lines)

        return "\n".join(lines)

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

    def _write_interactive(self, output: str) -> None:
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
            self.output.write(output_text)
            self.output.flush()

            self._last_output_lines = len(lines)
        else:
            self._last_output_lines = 0

    def _write_noninteractive(self, output: str) -> None:
        """Write output in non-interactive mode (minimal output).

        Args:
            output: Output string to write

        Behavior:
          - Write sections progressively as they update
          - Track section content to detect changes
          - Always emit Summary blocks immediately

        """
        # Guard if output is not writable
        if not hasattr(self.output, "write"):
            return

        now = time.time()

        # Always show full summaries
        if "Summary:" in output:
            try:
                self.output.write(output + "\n")
                self.output.flush()
            except Exception:
                # Best-effort: swallow IO errors to avoid breaking flows
                pass
            finally:
                self._last_noninteractive_output = output
                self._last_noninteractive_write_time = now
            return

        # Skip empty output
        if not output.strip():
            return

        # Parse sections from output to track what's new or changed
        sections = output.split("\n\n")
        new_or_updated_sections = []

        for section in sections:
            if not section.strip():
                continue

            # Create a signature for this section using full content
            # This allows us to detect when a section's content changes
            section_sig = section.strip()

            # If this section content is new or changed, write it
            if section_sig not in self._written_sections:
                new_or_updated_sections.append(section)
                self._written_sections.add(section_sig)

        # Write only new or updated sections
        if new_or_updated_sections:
            try:
                output_to_write = "\n\n".join(new_or_updated_sections)
                self.output.write(output_to_write + "\n")
                self.output.flush()
                self._last_noninteractive_output = output
                self._last_noninteractive_write_time = now
            except Exception:
                # Best-effort: ignore write failures
                pass

    async def render_once(self) -> None:
        """Render current state once.

        This is the main rendering method that should be called periodically
        to update the display.
        """
        async with self._lock:
            output = self._build_output()

            if not output:
                return

            if self.interactive:
                self._write_interactive(output)
            else:
                self._write_noninteractive(output)

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
    speed_history: deque[tuple[float, float]] | None = (
        None  # (timestamp, speed) pairs
    )

    # Multi-phase task tracking
    parent_task_id: str | None = None
    phase: int = 1
    total_phases: int = 1

    def __post_init__(self) -> None:
        """Initialize speed history deque."""
        if self.speed_history is None:
            self.speed_history = deque(maxlen=10)


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
        self._backend = AsciiProgressBackend(interactive=interactive)

        # State management
        self._tasks: dict[str, TaskInfo] = {}  # Use namespaced IDs as keys
        self._active: bool = False
        self._task_lock = asyncio.Lock()

        # Task ID tracking to prevent collisions
        self._task_counters: dict[ProgressType, int] = defaultdict(int)
        self._id_cache: dict[tuple[ProgressType, str], str] = {}

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
        # Check cache first
        cache_key = (progress_type, name)
        if cache_key in self._id_cache:
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
        namespaced_id = f"{type_prefix}_{counter}_{clean_name}"

        # Cache the result with size limit to prevent unbounded growth
        if len(self._id_cache) < ID_CACHE_LIMIT:
            self._id_cache[cache_key] = namespaced_id

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

    async def add_task(
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
        current_time = time.time()
        task_info = TaskInfo(
            task_id=namespaced_id,
            namespaced_id=namespaced_id,
            name=name,
            progress_type=progress_type,
            total=total,
            description=description,
            created_at=current_time,
            last_update=current_time,
            last_speed_update=0.0,  # Initialize to 0 for immediate speed calc
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
        # Calculate speed from last update
        time_since_last = current_time - task_info.last_speed_update
        bytes_delta = completed - task_info.completed

        # Need minimum time and progress to calculate speed
        if time_since_last <= 0 or bytes_delta <= 0:
            # Return current speed if available
            if task_info.current_speed_mbps > 0:
                return task_info.current_speed_mbps * (1024 * 1024)
            return 0.0

        speed_bps = bytes_delta / time_since_last

        # Add to history
        if task_info.speed_history is not None:
            task_info.speed_history.append((current_time, speed_bps))

        # Calculate moving average
        if task_info.speed_history and len(task_info.speed_history) > 0:
            speeds = [s for _, s in task_info.speed_history]
            avg_speed = sum(speeds) / len(speeds)
            return avg_speed

        return speed_bps

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
            current_time = time.time()

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

    async def create_icon_extraction_task(
        self, name: str, description: str | None = None
    ) -> str:
        """Create an icon extraction task.

        Args:
            name: Task name
            description: Task description

        Returns:
            Task ID

        """
        return await self.add_task(
            name=name,
            progress_type=ProgressType.ICON_EXTRACTION,
            description=description or f"Extracting icon for {name}",
        )

    async def create_post_processing_task(
        self,
        name: str,
        progress_type: ProgressType = ProgressType.INSTALLATION,
        description: str | None = None,
    ) -> str:
        """Create a post-processing task.

        Args:
            name: Task name
            progress_type: Type of post-processing
            description: Task description

        Returns:
            Task ID

        """
        return await self.add_task(
            name=name,
            progress_type=progress_type,
            description=description or f"Processing {name}",
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
