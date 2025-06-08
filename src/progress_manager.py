#!/usr/bin/env python3
"""Dynamic progress management for concurrent operations with standard terminal output.

This module provides customizable progress tracking for both synchronous and asynchronous
operations with support for nested progress bars using standard terminal output.
"""

import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime

from typing import Any




class BasicMultiAppProgress:
    """Basic progress display for multiple app downloads using terminal output.

    Each app gets its own progress bar with its own styling and prefix.
    All progress bars are rendered together in a single display
    """

    def __init__(self, expand: bool = True, transient: bool = False) -> None:
        """Initialize a new progress instance.

        Args:
            expand: Whether to expand the progress bar
            transient: Whether to hide completed tasks

        """
        # TODO: remove any and specify the type of tasks
        self.tasks: dict[int, dict[str, Any]] = {}  # dictionary to store tasks
        self.task_counter: int = 0  # Counter for task IDs
        self.active: bool = False  # Whether the progress display is active
        # Options similar to the original class
        self.expand = expand
        self.transient = transient
        # Store start times for speed calculation
        self.start_times: dict[int, float] = {}
        # Track the number of lines used in last render
        self.last_render_lines: int = 0

    def add_task(
        self,
        description: str,
        total: int = 100,
        completed: int = 0,
        prefix: str = "",
        visible: bool = True,
        **kwargs,
    ) -> int:
        """Add a new task to track.

        Args:
            description: Description of the task
            total: Total size or steps
            completed: Already completed size or steps
            prefix: Prefix to show before the description
            visible: Whether this task is visible
            **kwargs: Additional fields

        Returns:
            int: Task ID for the new task

        """
        task_id = self.task_counter
        self.task_counter += 1

        self.tasks[task_id] = {
            "description": description,
            "total": total,
            "completed": completed,
            "prefix": prefix,
            "visible": visible,
            "fields": kwargs,  # Store any additional fields
        }

        # Save start time for speed calculation
        self.start_times[task_id] = time.time()

        # Render if active
        if self.active:
            self._render()

        return task_id

    def update(self, task_id: int, **kwargs) -> None:
        """Update a task's progress.

        Args:
            task_id: ID of the task to update
            **kwargs: Attributes to update

        """
        if task_id not in self.tasks:
            return

        # Update task attributes
        for key, value in kwargs.items():
            if key == "advance":
                self.tasks[task_id]["completed"] += value
            elif key == "completed":
                self.tasks[task_id]["completed"] = value
            else:
                self.tasks[task_id][key] = value

        # Ensure completed doesn't exceed total
        self.tasks[task_id]["completed"] = min(
            self.tasks[task_id]["completed"], self.tasks[task_id]["total"]
        )

        # If display is active, refresh it
        if self.active:
            self._render()

    def remove_task(self, task_id: int) -> None:
        """Remove a task from progress tracking.

        Args:
            task_id: ID of the task to remove
        """
        if task_id in self.tasks:
            del self.tasks[task_id]

        if task_id in self.start_times:
            del self.start_times[task_id]

        # Re-render if active
        if self.active:
            self._render()

    def start(self) -> None:
        """Start displaying progress."""
        self.active = True
        self._render()

    def stop(self) -> None:
        """Stop displaying progress."""
        self.active = False
        # Clear the progress display by moving up and clearing lines
        if self.last_render_lines > 0:
            for _ in range(self.last_render_lines):
                sys.stdout.write("\033[K\033[1A")  # Clear line and move up
            sys.stdout.write("\033[K")  # Clear the current line
            sys.stdout.flush()
            self.last_render_lines = 0

    def _format_size(self, size_bytes: int) -> str:
        """Format size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            str: Formatted size string (e.g., '10.5 MB')
        """
        if size_bytes <= 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return (
            f"{size:.1f} {units[unit_index]}"
            if unit_index > 0
            else f"{int(size)} {units[unit_index]}"
        )

    def _format_speed(self, task_id: int) -> str:
        """Calculate and format download speed.

        Args:
            task_id: ID of the task

        Returns:
            str: Formatted speed string (e.g., '5.2 MB/s')
        """
        if task_id not in self.start_times:
            return "? MB/s"

        elapsed = time.time() - self.start_times[task_id]
        if elapsed <= 0:
            return "? MB/s"

        task = self.tasks[task_id]
        bytes_per_second = task["completed"] / elapsed

        return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"

    def _format_eta(self, task_id: int) -> str:
        """Estimate and format time remaining.

        Args:
            task_id: ID of the task

        Returns:
            str: Formatted estimated time (e.g., '5m 30s')
        """
        if task_id not in self.start_times:
            return "?"

        task = self.tasks[task_id]
        elapsed = time.time() - self.start_times[task_id]

        if task["completed"] <= 0 or elapsed <= 0:
            return "?"

        # Calculate ETA based on current speed
        bytes_remaining = task["total"] - task["completed"]
        bytes_per_second = task["completed"] / elapsed

        if bytes_per_second <= 0:
            return "?"

        seconds_remaining = bytes_remaining / bytes_per_second

        # Format time
        if seconds_remaining < 60:
            return f"{int(seconds_remaining)}s"
        elif seconds_remaining < 3600:
            return f"{int(seconds_remaining / 60)}m {int(seconds_remaining % 60)}s"
        else:
            hours = int(seconds_remaining / 3600)
            minutes = int((seconds_remaining % 3600) / 60)
            return f"{hours}h {minutes}m"

    def _render(self) -> None:
        """Render progress bars for all visible tasks."""
        if not self.active:
            return

        # Get only visible tasks
        visible_tasks = [(tid, task) for tid, task in self.tasks.items() if task["visible"]]

        if not visible_tasks:
            return

        # Clear previous output
        if self.last_render_lines > 0:
            for _ in range(self.last_render_lines):
                sys.stdout.write("\033[K\033[1A")  # Clear line and move up
            sys.stdout.write("\033[K")  # Clear the current line

        # Count the lines we're about to render
        self.last_render_lines = 0

        # Render each task
        for task_id, task in visible_tasks:
            lines_rendered = self._render_task(task_id, task)
            self.last_render_lines += lines_rendered

        sys.stdout.flush()

    def _render_task(self, task_id: int, task: dict[str, Any]) -> int:
        """Render a single task's progress bar.

        Args:
            task_id: ID of the task
            task: Task data dictionary

        Returns:
            int: Number of lines rendered
        """
        # Calculate percentage
        percentage = 100 * (task["completed"] / task["total"]) if task["total"] > 0 else 0

        # Create the progress bar
        bar_width = 40  # Width of the progress bar
        completed_width = int(bar_width * percentage / 100)

        bar = "=" * completed_width + "-" * (bar_width - completed_width)

        # Format the prefix
        prefix = task["prefix"] if "prefix" in task else ""

        # Line 1: Description and progress bar
        line1 = f"{prefix}{task['description']}"
        sys.stdout.write(f"{line1}\n")

        # Line 2: Progress details
        completed_size = self._format_size(task["completed"])
        total_size = self._format_size(task["total"])
        speed = self._format_speed(task_id)
        eta = self._format_eta(task_id)

        line2 = f"[{bar}] {percentage:.1f}% {completed_size}/{total_size} {speed} ETA: {eta}"
        sys.stdout.write(f"{line2}\n")

        # Return number of lines rendered
        return 2  # We rendered 2 lines for this task


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

        # Cap at total
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

        # Calculate percentage
        percentage = (self.completed / self.total) * 100 if self.total > 0 else 0

        # Create the progress bar (30 chars wide)
        bar_width = 30
        filled_width = int(bar_width * percentage / 100)
        bar = "=" * filled_width + "-" * (bar_width - filled_width)

        # Calculate elapsed time
        elapsed = time.time() - self.start_time
        elapsed_str = f"{int(elapsed)}s"

        # Format the output
        return f"{self.description}: [{bar}] {percentage:.1f}% ({self.completed}/{self.total}) {elapsed_str} {self.status}"


class ProgressManager:
    """Manages display of multiple progress bars in the terminal."""

    def __init__(self):
        """Initialize the progress manager."""
        self.progress_bars: dict[int, BasicProgressBar] = {}
        self.next_id = 0
        self.active = False
        self.last_render_lines = 0
        self.lock = threading.RLock()

    def add_task(self, description: str, total: int = 100, **kwargs) -> int:
        """Add a new task to the progress display.

        Args:
            description: Description of the task
            total: Total number of steps
            **kwargs: Additional arguments

        Returns:
            int: Task ID
        """
        with self.lock:
            task_id = self.next_id
            self.next_id += 1

            self.progress_bars[task_id] = BasicProgressBar(description, total)

            # Apply any additional properties from kwargs
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
        with self.lock:
            if task_id not in self.progress_bars:
                return

            task = self.progress_bars[task_id]

            # Update the task
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
        with self.lock:
            if task_id in self.progress_bars:
                del self.progress_bars[task_id]

            if self.active:
                self.render()

    def start(self):
        """Start the progress display."""
        with self.lock:
            self.active = True
            self.render()

    def stop(self):
        """Stop the progress display."""
        with self.lock:
            self.active = False
            self._clear_lines()

    def render(self):
        """Render all visible progress bars."""
        if not self.active:
            return

        with self.lock:
            # Clear previous output first
            self._clear_lines()

            # Get all visible tasks
            visible_tasks = [(tid, bar) for tid, bar in self.progress_bars.items() if bar.visible]

            if not visible_tasks:
                return

            # Count lines we'll render
            lines_to_render = len(visible_tasks)

            # Render each task
            output_lines = []
            for _, bar in visible_tasks:
                output_lines.append(bar.render())

            # Print all lines
            print("\n".join(output_lines))
            sys.stdout.flush()

            # Store number of lines rendered
            self.last_render_lines = lines_to_render

    def _clear_lines(self):
        """Clear previously rendered lines."""
        if self.last_render_lines > 0:
            # Move cursor up and clear lines
            for _ in range(self.last_render_lines):
                sys.stdout.write("\033[1A")  # Move up one line
                sys.stdout.write("\033[K")  # Clear to the end of line
            sys.stdout.flush()

class DynamicProgressManager[T]:
    """Manages dynamic progress display for concurrent operations.

    This class handles progress tracking for multiple concurrent operations
    with support for nested progress displays and both synchronous and
    asynchronous operation.
    """

    def __init__(self) -> None:
        """Initialize the progress manager."""
        # Initialize progress tracking
        self.progress = ProgressManager()

        # Task mapping
        self.task_map: dict[T, dict[str, Any]] = {}

        # Overall stats
        self.task_stats: dict[str, Any] = {
            "start_time": None,
            "items": 0,
            "completed": 0,
            "failed": 0,
        }

        # Download tracking
        self._download_in_progress: dict[T, bool] = {}

        # Reference counting for nested progress
        self._user_count = 0

        # For thread safety
        self._lock = threading.Lock()

    @contextmanager
    def start_progress(self, total_items: int, title: str = "Processing") -> None:
        """Start progress tracking with a live display.

        Args:
            total_items: Total number of items to process
            title: Title for the progress display

        Yields:
            self: The progress manager instance
        """
        try:
            with self._lock:
                self.task_stats["start_time"] = time.time()
                self.task_stats["items"] = total_items
                self._user_count += 1

                # Only start display if this is the first caller
                if self._user_count == 1:
                    # Print header
                    start_time_str = datetime.now().strftime("%H:%M:%S")
                    print("\n" + "=" * 60)
                    print(f"{title} - Started at {start_time_str}")
                    print(f"Processing {total_items} items")
                    print("-" * 60)

                    # Start progress display
                    self.progress.start()

            yield self

        finally:
            with self._lock:
                self._user_count -= 1

                # Only clean up if this is the last user
                if self._user_count == 0:
                    # Calculate stats for summary
                    elapsed = time.time() - self.task_stats["start_time"]
                    completed = self.task_stats["completed"]
                    failed = self.task_stats["failed"]
                    in_progress = self.task_stats["items"] - completed - failed

                    # Stop progress display
                    self.progress.stop()

                    # Show completion summary
                    print("\n" + "=" * 60)
                    print(f"Completed in {elapsed:.1f}s - {completed} succeeded, {failed} failed")
                    if in_progress > 0:
                        print(f"Items not completed: {in_progress}")
                    print("=" * 60)

                    # Reset progress tracking
                    self.task_map.clear()
                    self._download_in_progress.clear()

    def add_item(self, item_id: T, name: str, steps: list[str] = None) -> None:
        """Add an item to track in the progress display.

        Args:
            item_id: Unique identifier for the item
            name: Display name for the item
            steps: list of step names for this item
        """
        if steps is None:
            steps = []

        with self._lock:
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

            # Initialize download tracking
            self._download_in_progress[item_id] = False

    def start_item_step(self, item_id: T, step: str) -> None:
        """Start a step for an item.

        Args:
            item_id: Identifier for the item
            step: Name of the step
        """
        with self._lock:
            if item_id in self.task_map:
                task_data = self.task_map[item_id]
                task_data["current_step"] = step

                # Update progress display
                self.progress.update(task_data["task_id"], status=f"Working on {step}...")

    def update_item_step(self, item_id: T, step: str, completed: bool = False) -> None:
        """Update a step for an item.

        Args:
            item_id: Identifier for the item
            step: Name of the step
            completed: Whether the step is completed
        """
        with self._lock:
            if item_id in self.task_map:
                task_data = self.task_map[item_id]

                if completed and step not in task_data["completed_steps"]:
                    # Mark step as completed
                    task_data["completed_steps"].add(step)

                    # Update progress display
                    self.progress.update(
                        task_data["task_id"],
                        completed=len(task_data["completed_steps"]),
                        status=f"Completed {step}",
                    )

    def complete_item(self, item_id: T, success: bool = True) -> None:
        """Mark an item as completed.

        Args:
            item_id: Identifier for the item
            success: Whether the operation was successful
        """
        with self._lock:
            if item_id in self.task_map:
                task_data = self.task_map[item_id]
                task_data["success"] = success

                # Mark all steps as completed
                steps_count = len(task_data["steps"])

                # Update stats
                if success:
                    self.task_stats["completed"] += 1
                    status_msg = "✓ Success"
                else:
                    self.task_stats["failed"] += 1
                    status_msg = "✗ Failed"

                # Update progress display
                self.progress.update(task_data["task_id"], completed=steps_count, status=status_msg)

                # Mark download as no longer in progress
                self._download_in_progress[item_id] = False

    def start_download(self, item_id: T, filename: str, total_size: int) -> int:
        """Start tracking a file download.

        Args:
            item_id: Identifier for the parent item
            filename: Name of the file being downloaded
            total_size: Total size of the download in bytes

        Returns:
            int: Task ID for the download
        """
        with self._lock:
            # Mark this item as having a download in progress
            if item_id in self._download_in_progress:
                self._download_in_progress[item_id] = True

            # Update the main task status
            if item_id in self.task_map:
                task_id = self.task_map[item_id]["task_id"]
                self.progress.update(task_id, status=f"Downloading {filename}...")
                return task_id

            return 0

    def update_download(
        self, item_id: T, filename: str, advance: int = 0, finished: bool = False
    ) -> None:
        """Update the progress of a download.

        Args:
            item_id: Identifier for the parent item
            filename: Name of the file being downloaded
            advance: Number of bytes to advance the progress
            finished: Whether the download is finished
        """
        with self._lock:
            if item_id in self.task_map:
                # Update the main task status based on download state
                task_id = self.task_map[item_id]["task_id"]

                if finished:
                    # Mark download as complete
                    self._download_in_progress[item_id] = False
                    self.progress.update(task_id, status="Download completed")
                elif advance > 0 and self._download_in_progress.get(item_id, False):
                    # Only show downloading status if still in progress
                    self.progress.update(task_id, status=f"Downloading {filename}...")

    def get_summary(self) -> str:
        """Generate a summary of all tracked items.

        Returns:
            str: Summary of operations
        """
        with self._lock:
            summary = "Operation Summary\n"
            summary += "-" * 60 + "\n"
            summary += "Item                | Status      | Steps Completed\n"
            summary += "-" * 60 + "\n"

            for item_id, item in self.task_map.items():
                name = item["name"]

                # Determine status
                if item["success"] is True:
                    status = "Success"
                elif item["success"] is False:
                    status = "Failed"
                else:
                    status = "In Progress"

                # Calculate steps completed
                steps_completed = f"{len(item['completed_steps'])}/{len(item['steps'])}"

                # Add line to summary
                summary += f"{name:<19} | {status:<11} | {steps_completed}\n"

            summary += "-" * 60 + "\n"
            return summary
