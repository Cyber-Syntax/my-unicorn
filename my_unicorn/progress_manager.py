#!/usr/bin/env python3
"""Dynamic progress management for concurrent operations with standard terminal output.

This module provides customizable progress tracking for both synchronous and asynchronous
operations with support for nested progress bars using standard terminal output.

NOTE: These classes are primarily used for testing. The main application uses
AppImageProgressMeter from progress.py for actual download progress tracking.
"""

import asyncio
import logging
import shutil
import sys
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from typing import Any, ClassVar

from .progress import format_number

# Constants for progress display
BYTES_IN_KB = 1024
BYTES_IN_MB = 1024 * 1024
SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 3600
THOUSAND = 1000
MILLION = 1000000

# Status constants
STATUS_OK = 0
STATUS_FAILED = 1
STATUS_ALREADY_EXISTS = 2
STATUS_MIRROR = 3
STATUS_DRPM = 4


def _terminal_width() -> int:
    """Get terminal width."""
    return shutil.get_terminal_size((80, 20)).columns

def format_time(seconds: float | None) -> str:
    """Format time duration to MM:SS."""
    if seconds is None or seconds <= 0:
        return "--:--"
    minutes = int(seconds // SECONDS_IN_MINUTE)
    seconds_remainder = int(seconds % SECONDS_IN_MINUTE)
    return f"{minutes:02d}:{seconds_remainder:02d}"


class AsyncMultiFileProgressMeter:
    """Asynchronous multi-file download progress meter with individual progress bars.

    This class provides the core async progress functionality that was successful
    in the example file, adapted for our app update use case.
    """

    STATUS_2_STR: ClassVar[dict[int, str]] = {
        STATUS_OK: "COMPLETED",
        STATUS_FAILED: "FAILED",
        STATUS_ALREADY_EXISTS: "SKIPPED",
        STATUS_MIRROR: "MIRROR",
        STATUS_DRPM: "DRPM",
    }

    def __init__(self, fo=sys.stderr, update_period: float = 0.1) -> None:
        """Initialize the async progress meter.

        Args:
            fo: File object for output
            update_period: Update interval in seconds

        """
        self.fo = fo
        self.update_period = update_period
        self.isatty = sys.stdout.isatty()

        # App state - keyed by app ID
        self.apps: dict[int, dict[str, Any]] = {}
        self.total_apps = 0
        self.total_size = 0
        self.completed_apps = 0
        self.app_counter = 0
        self.last_update_time = 0.0
        self.lock = asyncio.Lock()
        self.update_task: asyncio.Task[None] | None = None
        self.stop_event = asyncio.Event()

    def message(self, msg: str) -> None:
        """Write message to output."""
        if self.fo:
            self.fo.write(msg)
            self.fo.flush()

    def _get_app_name(self, app_data: dict[str, Any]) -> str:
        """Extract readable app name from app data."""
        return app_data.get("name", "Unknown App")

    async def start(self, total_apps: int, total_size: int = 0) -> None:
        """Start progress tracking for multiple apps.

        Args:
            total_apps: Total number of apps to update
            total_size: Total download size (optional)

        """
        async with self.lock:
            self.total_apps = total_apps
            self.total_size = total_size
            self.completed_apps = 0

        if total_apps == 0:
            return

        # Clear screen and position cursor
        if self.isatty:
            self.message("\n" * 3)  # Reserve space for progress display
            self.message("\033[3A")  # Move cursor up 3 lines

        # Start update task
        self.update_task = asyncio.create_task(self._update_loop())

    async def _update_loop(self) -> None:
        """Continuously update the display until stopped."""
        while not self.stop_event.is_set():
            try:
                self._update_display()
                await asyncio.sleep(self.update_period)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.getLogger(__name__).debug(f"Progress update error: {e}")

    async def progress(self, app_data: dict[str, Any], done: int) -> None:
        """Update progress for an app.

        Args:
            app_data: App information dictionary
            done: Bytes downloaded so far

        """
        app_id = id(app_data)

        async with self.lock:
            if app_id not in self.apps:
                # First time seeing this app - initialize it
                self.apps[app_id] = {
                    "app_data": app_data,
                    "status": "downloading",
                    "progress": 0,
                    "start_time": time.time(),
                    "end_time": None,
                    "error": None,
                    "display_name": self._get_app_name(app_data),
                }

            # Update progress
            self.apps[app_id]["progress"] = done

    async def end(self, app_data: dict[str, Any], status: int, err_msg: str | None = None) -> None:
        """Mark an app as completed.

        Args:
            app_data: App information dictionary
            status: Status code (STATUS_OK, STATUS_FAILED, etc.)
            err_msg: Error message if failed

        """
        app_id = id(app_data)

        async with self.lock:
            if app_id in self.apps:
                self.apps[app_id]["status"] = "completed" if status == STATUS_OK else "failed"
                self.apps[app_id]["end_time"] = time.time()
                if err_msg:
                    self.apps[app_id]["error"] = err_msg

                if status == STATUS_OK:
                    self.completed_apps += 1

    def _update_display(self) -> None:
        """Update the progress display."""
        if not self.isatty or not self.apps:
            return

        # Move cursor to start of download area
        self.message("\033[3;1H")  # Move to line 3, column 1

        # Display each app's progress
        for _app_id, app_info in sorted(self.apps.items(), key=lambda x: x[1]["display_name"]):
            self._display_app_progress(app_info)

        # Display summary
        self._display_summary()

        # Clear any remaining lines
        self.message("\033[K")  # Clear to end of line

    def _display_app_progress(self, app_info: dict[str, Any]) -> None:
        """Display progress for a single app."""
        progress_data = self._calculate_progress_data(app_info)
        status_info = self._get_status_display(app_info)
        progress_bar = self._create_progress_bar(progress_data["pct"])
        size_info = self._format_size_info(progress_data, app_info["progress"])

        self._render_app_line(app_info, status_info, progress_bar, progress_data, size_info)

    def _calculate_progress_data(self, app_info: dict[str, Any]) -> dict[str, Any]:
        """Calculate progress data for an app."""
        app_data = app_info["app_data"]
        progress = app_info["progress"]
        start_time = app_info["start_time"]

        # Estimate total size
        total_size = app_data.get("download_size", 0)
        if total_size == 0 and progress > 0:
            total_size = max(progress * 2, 50 * BYTES_IN_MB)

        # Calculate percentage
        pct = int(progress * 100 / total_size) if total_size > 0 else 0
        if app_info["status"] != "downloading" and pct == 0:
            pct = 100

        # Calculate speed and ETA
        now = time.time()
        elapsed = now - start_time

        if elapsed > 0 and progress > 0:
            speed = progress / elapsed
            speed_str = f"{speed / BYTES_IN_MB:.1f} MB/s"

            if total_size > progress and speed > 0:
                eta_seconds = (total_size - progress) / speed
                eta_str = format_time(eta_seconds)
            else:
                eta_str = "00:00"
        else:
            speed_str = "-- MB/s"
            eta_str = "--:--"

        return {
            "total_size": total_size,
            "pct": pct,
            "speed_str": speed_str,
            "eta_str": eta_str,
        }

    def _get_status_display(self, app_info: dict[str, Any]) -> dict[str, str]:
        """Get status display information."""
        status = app_info.get("status", "downloading")

        status_map = {
            "completed": ("✓", "\033[32m"),  # Green
            "failed": ("✗", "\033[31m"),  # Red
            "downloading": ("⬇", "\033[33m"),  # Yellow
        }

        icon, color = status_map.get(status, ("◯", "\033[37m"))  # Default white

        return {
            "icon": icon,
            "color": color,
            "reset": "\033[0m",
        }

    def _create_progress_bar(self, pct: int) -> str:
        """Create a progress bar string."""
        bar_width = 30
        if pct > 0:
            filled = int(bar_width * pct / 100)
            return "█" * filled + "░" * (bar_width - filled)
        return "░" * bar_width

    def _format_size_info(self, progress_data: dict[str, Any], progress: int) -> str:
        """Format size information string."""
        total_size = progress_data["total_size"]
        return f"{format_number(progress)}/{format_number(total_size)}"

    def _render_app_line(
        self,
        app_info: dict[str, Any],
        status_info: dict[str, str],
        progress_bar: str,
        progress_data: dict[str, Any],
        size_info: str,
    ) -> None:
        """Render the complete app progress line."""
        display_name = app_info["display_name"]
        max_name_length = 40

        if len(display_name) > max_name_length:
            display_name = display_name[: max_name_length - 3] + "..."

        line = (
            f"{status_info['color']}{status_info['icon']}{status_info['reset']} "
            f"{display_name:<{max_name_length}} [{progress_bar}] "
            f"{progress_data['pct']:3d}% {size_info:>12} "
            f"{progress_data['speed_str']:>8} ETA {progress_data['eta_str']}"
        )

        # Add error message if failed
        if app_info.get("status") == "failed" and app_info.get("error"):
            line += f"\n    Error: {app_info['error'][:60]}"

        self.message(line + "\033[K\n")  # Clear to end of line and add newline

    def _display_summary(self) -> None:
        """Display overall progress summary."""
        # Calculate totals
        total_downloaded = sum(f["progress"] for f in self.apps.values())
        overall_pct = int(total_downloaded * 100 / self.total_size) if self.total_size > 0 else 0

        # Count by status
        downloading = sum(1 for f in self.apps.values() if f["status"] == "downloading")
        completed = sum(1 for f in self.apps.values() if f["status"] == "completed")
        failed = sum(1 for f in self.apps.values() if f["status"] == "failed")

        # Summary line
        summary = f"\n{'─' * 80}\n"
        summary += (
            f"Overall: {completed}/{self.total_apps} completed, {failed} failed, "
            f"{downloading} active"
        )

        if self.total_size > 0:
            total_info = (
                f"{format_number(total_downloaded)}/"
                f"{format_number(self.total_size)} ({overall_pct}%)"
            )
            summary += f" | Total: {total_info}"

        summary += "\n"
        self.message(summary)

    async def stop(self) -> None:
        """Stop the progress display."""
        self.stop_event.set()
        if self.update_task and not self.update_task.done():
            try:
                await asyncio.wait_for(self.update_task, timeout=1.0)
            except TimeoutError:
                self.update_task.cancel()

        # Final display
        async with self.lock:
            self._update_display()

        # Show final results
        if self.isatty:
            self.message("\n" + "=" * 80 + "\n")


class AsyncAppUpdateProgressManager:
    """Async progress manager specifically designed for concurrent app updates.

    This manager integrates the successful asyncio patterns from the example
    with our app update workflow.
    """

    def __init__(self) -> None:
        """Initialize the async app update progress manager."""
        self._progress_meter: AsyncMultiFileProgressMeter | None = None
        self._active = False
        self._logger = logging.getLogger(__name__)

    @asynccontextmanager
    async def track_updates(self, total_apps: int, title: str = "Updating Apps"):
        """Context manager for tracking app updates with progress display.

        Args:
            total_apps: Total number of apps to update
            title: Title for the progress display

        Yields:
            self: The progress manager instance

        """
        try:
            # Print header
            start_time_str = datetime.now().strftime("%H:%M:%S")
            print("\n" + "=" * 60)
            print(f"{title} - Started at {start_time_str}")
            print(f"Processing {total_apps} apps")
            print("-" * 60)

            # Initialize progress meter
            self._progress_meter = AsyncMultiFileProgressMeter()
            await self._progress_meter.start(total_apps)
            self._active = True

            yield self

        except Exception as e:
            self._logger.error(f"Error in progress tracking: {e}")
            raise
        finally:
            # Clean up
            self._active = False
            if self._progress_meter:
                await self._progress_meter.stop()

            # Show completion summary
            print("\n" + "=" * 60)
            print("Update process completed")
            print("=" * 60)

    async def start_app_update(self, app_data: dict[str, Any]) -> None:
        """Start tracking an app update.

        Args:
            app_data: Dictionary with app information

        """
        if self._progress_meter and self._active:
            await self._progress_meter.progress(app_data, 0)

    async def update_app_progress(self, app_data: dict[str, Any], bytes_downloaded: int) -> None:
        """Update progress for an app download.

        Args:
            app_data: Dictionary with app information
            bytes_downloaded: Number of bytes downloaded so far

        """
        if self._progress_meter and self._active:
            await self._progress_meter.progress(app_data, bytes_downloaded)

    async def complete_app_update(
        self, app_data: dict[str, Any], success: bool = True, error_msg: str | None = None
    ) -> None:
        """Mark an app update as completed.

        Args:
            app_data: Dictionary with app information
            success: Whether the update was successful
            error_msg: Error message if failed

        """
        if self._progress_meter and self._active:
            status = STATUS_OK if success else STATUS_FAILED
            await self._progress_meter.end(app_data, status, error_msg)


# Global instance for use across the application
async_progress_manager = AsyncAppUpdateProgressManager()


# BasicMultiAppProgress removed - replaced by AppImageProgressMeter for better concurrent operation support


class BasicProgressBar:
    """A simple progress bar implementation using standard terminal output.

    This class provides basic progress tracking functionality without external dependencies.
    """

    def __init__(self, description: str = "", total: int = 100):
        """Initialize a progress bar.

        Args:
            description: Description of the progress bar
            total: Total number of steps

        """
        self.description = description
        self.total = total
        self.completed = 0
        self.start_time = time.time()
        self.status = ""
        self.visible = True

    def update(self, completed: int | None = None, advance: int = 0, status: str = ""):
        """Update the progress bar.

        Args:
            completed: set absolute completion value
            advance: Increment completion by this amount
            status: Status message to display

        """
        if completed is not None:
            self.completed = completed
        else:
            self.completed += advance

        self.completed = min(self.completed, self.total)

        if status:
            self.status = status

    def render(self) -> str:
        """Render the progress bar as a string.

        Returns:
            str: The formatted progress bar

        """
        if not self.visible:
            return ""

        percentage = (self.completed / self.total) * 100 if self.total > 0 else 0

        bar_width = 30
        filled_width = int(bar_width * percentage / 100)
        bar = "=" * filled_width + "-" * (bar_width - filled_width)

        elapsed = time.time() - self.start_time
        elapsed_str = f"{int(elapsed)}s"

        return (
            f"{self.description}: [{bar}] {percentage:.1f}% "
            f"({format_number(self.completed)}/{format_number(self.total)}) {elapsed_str} {self.status}"
        )


class ProgressManager:
    """Manages display of multiple progress bars in the terminal."""

    def __init__(self):
        """Initialize the progress manager."""
        self.progress_bars: dict[int, BasicProgressBar] = {}
        self.next_id = 0
        self.active = False
        self.last_render_lines = 0

    def add_task(self, description: str, total: int = 100, **kwargs) -> int:
        """Add a new task to the progress display.

        Args:
            description: Description of the task
            total: Total number of steps
            **kwargs: Additional arguments

        Returns:
            int: Task ID

        """
        task_id = self.next_id
        self.next_id += 1

        self.progress_bars[task_id] = BasicProgressBar(description, total)

        for key, value in kwargs.items():
            if key == "status" and value:
                self.progress_bars[task_id].status = value
            elif key == "visible":
                self.progress_bars[task_id].visible = value

        return task_id

    def update(self, task_id: int, **kwargs):
        """Update a task's progress.

        Args:
            task_id: ID of the task to update
            **kwargs: Arguments to update (completed, advance, status)

        """
        if task_id not in self.progress_bars:
            return

        task = self.progress_bars[task_id]

        completed = kwargs.get("completed")
        advance = kwargs.get("advance", 0)
        status = kwargs.get("status", "")

        task.update(completed, advance, status)

        if self.active:
            self.render()

    def remove_task(self, task_id: int):
        """Remove a task from the progress display.

        Args:
            task_id: ID of the task to remove

        """
        if task_id in self.progress_bars:
            del self.progress_bars[task_id]

        if self.active:
            self.render()

    def start(self):
        """Start the progress display."""
        self.active = True
        self.render()

    def stop(self):
        """Stop the progress display."""
        self.active = False
        self._clear_lines()

    def render(self):
        """Render all visible progress bars."""
        if not self.active:
            return

        self._clear_lines()

        visible_tasks = [(tid, bar) for tid, bar in self.progress_bars.items() if bar.visible]

        if not visible_tasks:
            return

        lines_to_render = len(visible_tasks)

        output_lines = []
        for _, bar in visible_tasks:
            output_lines.append(bar.render())

        print("\n".join(output_lines))
        sys.stdout.flush()

        self.last_render_lines = lines_to_render

    def _clear_lines(self):
        """Clear previously rendered lines."""
        if self.last_render_lines > 0:
            for _ in range(self.last_render_lines):
                sys.stdout.write("\033[1A")
                sys.stdout.write("\033[K")
            sys.stdout.flush()


class DynamicProgressManager[T]:
    """Manages dynamic progress display for concurrent operations.

    This class handles progress tracking for multiple concurrent operations
    with support for nested progress displays and both synchronous and
    asynchronous operation.
    """

    def __init__(self) -> None:
        """Initialize the progress manager."""
        self.progress = ProgressManager()
        self.task_map: dict[T, dict[str, Any]] = {}
        self.task_stats: dict[str, Any] = {
            "start_time": None,
            "items": 0,
            "completed": 0,
            "failed": 0,
        }
        self._download_in_progress: dict[T, bool] = {}
        self._user_count = 0

    def add_item(self, item_id: T, name: str, steps: list[str] | None = None) -> None:
        """Add an item to track in the progress display.

        Args:
            item_id: Unique identifier for the item
            name: Display name for the item
            steps: list of step names for this item

        """
        if steps is None:
            steps = []

        description = f"{name}"
        task_id = self.progress.add_task(
            description,
            total=len(steps) if steps else 1,
            status="Starting...",
            completed=0,
        )

        self.task_map[item_id] = {
            "name": name,
            "task_id": task_id,
            "steps": steps,
            "current_step": None,
            "completed_steps": set(),
            "success": None,
        }

        self._download_in_progress[item_id] = False

    def complete_item(self, item_id: T, success: bool = True) -> None:
        """Mark an item as completed.

        Args:
            item_id: Identifier for the item
            success: Whether the operation was successful

        """
        if item_id in self.task_map:
            task_data = self.task_map[item_id]
            task_data["success"] = success

            steps_count = len(task_data["steps"])

            if success:
                self.task_stats["completed"] += 1
                status_msg = "✓ Success"
            else:
                self.task_stats["failed"] += 1
                status_msg = "✗ Failed"

            self.progress.update(task_data["task_id"], completed=steps_count, status=status_msg)
            self._download_in_progress[item_id] = False

    @contextmanager
    def start_progress(self, total_items: int, title: str):
        """Start a progress context for download operations.

        Args:
            total_items: Total number of items to process
            title: Title for the progress display

        Yields:
            ProgressContext: Context manager for progress tracking

        """
        self.task_stats["start_time"] = time.time()
        self.task_stats["items"] = total_items
        self.task_stats["completed"] = 0
        self.task_stats["failed"] = 0

        # Start the progress display
        self.progress.start()

        try:
            # Yield a context that provides the interface expected by download code
            yield ProgressContext(self.progress)
        finally:
            # Clean up and stop progress display
            self.progress.stop()


class ProgressContext:
    """Context manager wrapper for progress tracking during downloads."""

    def __init__(self, progress_manager: "ProgressManager"):
        """Initialize with a progress manager instance."""
        self.progress_manager = progress_manager
        self._task_ids: dict[str, int] = {}

    def add_task(self, filename: str, total: int, description: str) -> str:
        """Add a task to track progress.

        Args:
            filename: Name of the file being downloaded
            total: Total bytes to download
            description: Description of the task

        Returns:
            Task identifier

        """
        task_id = self.progress_manager.add_task(
            description=description, total=total, status="Starting..."
        )
        self._task_ids[filename] = task_id
        return filename

    def update(self, task_id: str, completed: int):
        """Update progress for a task.

        Args:
            task_id: Task identifier (filename)
            completed: Number of bytes completed

        """
        if task_id in self._task_ids:
            real_task_id = self._task_ids[task_id]
            self.progress_manager.update(real_task_id, completed=completed)
