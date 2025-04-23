#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic progress management for concurrent operations with Rich library integration.

This module provides customizable progress tracking for both synchronous and asynchronous
operations with support for nested progress bars and dynamic styling based on context.
"""

from typing import Dict, Any, Generic, TypeVar, Optional, List, Tuple, Set, Union
from contextlib import contextmanager
import time
from datetime import datetime

from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TaskID,
    SpinnerColumn,
    TimeElapsedColumn,
)
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.console import Group

# Type variable for item IDs
T = TypeVar("T")


class CustomProgressColumn(BarColumn):
    """Custom progress column that can adapt its appearance based on context."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bar_width = kwargs.get("bar_width", 40)


class NestedProgress(Progress):
    """
    A progress class that supports nested progress bars with dynamic styling.

    This class extends Rich's Progress to allow tasks to have different column layouts
    and styling based on their context or task type.
    """

    def get_renderables(self) -> List[Any]:
        """
        Generate renderables for each task based on its progress_type.

        Different tasks can have different column layouts and styles.

        Returns:
            List of renderables for each task
        """
        renderables = []

        for task in self.tasks:
            # Get the progress type from task fields
            progress_type = task.fields.get("progress_type", "default")

            # Create a temporary columns configuration based on progress_type
            if progress_type == "download":
                temp_columns = [
                    TextColumn("[bold blue]{task.description}[/]"),
                    BarColumn(bar_width=None),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                ]
            elif progress_type == "process":
                temp_columns = [
                    SpinnerColumn(),
                    TextColumn("[bold green]{task.description}[/]"),
                    BarColumn(bar_width=50),
                    TextColumn("[bold]{task.fields[status]}[/]"),
                    TimeElapsedColumn(),
                ]
            elif progress_type == "verify":
                temp_columns = [
                    TextColumn("[bold yellow]{task.description}[/]"),
                    BarColumn(bar_width=30, style="yellow"),
                    TextColumn("[bold]{task.percentage:>3.0f}%[/]"),
                ]
            else:
                # Default columns
                temp_columns = self.columns

            # Create a table with just this task
            table = self.make_tasks_table(temp_columns, [task])
            renderables.append(table)

        return renderables


class DynamicProgressManager(Generic[T]):
    """
    Manages dynamic progress display for concurrent operations.

    This class handles progress tracking for multiple concurrent operations,
    with support for nested progress bars, different progress styles, and
    both synchronous and asynchronous operation.

    Attributes:
        console (Console): Rich console for output
        progress (Progress): The main progress instance
        download_progress (Optional[Progress]): Separate progress for downloads
        task_map (Dict): Mapping of item IDs to task IDs
        task_stats (Dict): Statistics about tasks
        _live (Optional[Live]): Rich Live display when active
    """

    def __init__(self) -> None:
        """Initialize the progress manager."""
        self.console = Console()

        # Main progress for overall operations
        self.progress = NestedProgress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}[/]"),
            BarColumn(bar_width=40),
            TextColumn("[bold]{task.fields[status]}[/]"),
            TimeElapsedColumn(),
            expand=True,
        )

        # Download progress for file downloads
        self.download_progress = None

        # Tracking mappings
        self.task_map: Dict[T, Dict[str, Any]] = {}
        self.task_stats: Dict[str, Any] = {
            "start_time": None,
            "items": 0,
            "completed": 0,
            "failed": 0,
        }

        # Live display
        self._live: Optional[Live] = None
        self._layout: Optional[Layout] = None

        # Track if a task has a download in progress
        self._download_in_progress: Dict[T, bool] = {}

    @contextmanager
    def start_progress(self, total_items: int, title: str = "Processing") -> None:
        """
        Start progress tracking with a live display.

        Args:
            total_items: Total number of items to process
            title: Title for the progress display

        Yields:
            self: The progress manager instance
        """
        try:
            self.task_stats["start_time"] = time.time()
            self.task_stats["items"] = total_items

            # Create layout
            self._layout = Layout()
            self._layout.split(
                Layout(name="header", size=3),
                Layout(name="progress"),
                Layout(name="footer", size=3),
            )

            # Set header content
            start_time_str = datetime.now().strftime("%H:%M:%S")
            header_text = f"[bold blue]{title} - Started at {start_time_str}[/]\n"
            header_text += f"[bold cyan]Processing {total_items} items[/]"
            self._layout["header"].update(Panel(header_text))

            # Set progress content
            self._layout["progress"].update(self.progress)

            # Set footer content
            self._layout["footer"].update(Panel("[bold]Press Ctrl+C to cancel[/]"))

            # Start the live display
            self._live = Live(self._layout, console=self.console, refresh_per_second=4)
            self._live.start()

            yield self

        finally:
            # Update footer with completion info
            if self._live and self._layout:
                elapsed = time.time() - self.task_stats["start_time"]
                completed = self.task_stats["completed"]
                failed = self.task_stats["failed"]
                in_progress = self.task_stats["items"] - completed - failed

                footer_text = (
                    f"[bold]Completed in {elapsed:.1f}s - {completed} succeeded, {failed} failed"
                )
                if in_progress:
                    footer_text += f", {in_progress} interrupted"
                footer_text += "[/]"

                self._layout["footer"].update(Panel(footer_text))
                self._live.refresh()

            # Stop the live display
            if self._live:
                self._live.stop()

            # Reset progress displays
            self.task_map.clear()
            self._download_in_progress.clear()
            if self.download_progress:
                self.download_progress = None

    def add_item(self, item_id: T, name: str, steps: List[str]) -> None:
        """
        Add an item to track in the progress display.

        Args:
            item_id: Unique identifier for the item
            name: Display name for the item
            steps: List of step names for this item
        """
        description = f"{name}"
        task_id = self.progress.add_task(
            description,
            total=len(steps),
            status="Starting...",
            completed=0,
            progress_type="process",  # Set the progress type for styling
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
        """
        Mark a step as started for an item.

        Args:
            item_id: Item identifier
            step: Name of the step being started
        """
        if item_id in self.task_map:
            self.task_map[item_id]["current_step"] = step
            self.progress.update(
                self.task_map[item_id]["task_id"], status=f"[yellow]Working on {step}...[/]"
            )

    def update_item_step(self, item_id: T, step: str, completed: bool = False) -> None:
        """
        Update the status of a step for an item.

        Args:
            item_id: Item identifier
            step: Name of the step to update
            completed: Whether the step is completed
        """
        if item_id in self.task_map and step in self.task_map[item_id]["steps"]:
            if completed:
                self.task_map[item_id]["completed_steps"].add(step)
                # Update progress based on completed steps
                progress_value = len(self.task_map[item_id]["completed_steps"])
                self.progress.update(
                    self.task_map[item_id]["task_id"],
                    completed=progress_value,
                    status=f"[green]Completed {step}[/]",
                )

    def complete_item(self, item_id: T, success: bool = True) -> None:
        """
        Mark an item as completed.

        Args:
            item_id: Item identifier
            success: Whether the item completed successfully
        """
        if item_id in self.task_map:
            self.task_map[item_id]["success"] = success
            status = "[bold green]✓ Success[/]" if success else "[bold red]✗ Failed[/]"

            # Update task in progress display
            self.progress.update(
                self.task_map[item_id]["task_id"],
                completed=len(self.task_map[item_id]["steps"]),
                status=status,
            )

            # Update statistics
            if success:
                self.task_stats["completed"] += 1
            else:
                self.task_stats["failed"] += 1

            # Clean up download tracking
            if item_id in self._download_in_progress:
                self._download_in_progress[item_id] = False

    def start_download(self, item_id: T, filename: str, total_size: int) -> TaskID:
        """
        Start tracking a file download.

        Args:
            item_id: Identifier for the parent item
            filename: Name of the file being downloaded
            total_size: Total size of the download in bytes

        Returns:
            TaskID: Task ID for the download
        """
        # Mark this item as having a download in progress
        if item_id in self._download_in_progress:
            self._download_in_progress[item_id] = True

        # Update the main task status
        if item_id in self.task_map:
            main_task_id = self.task_map[item_id]["task_id"]
            self.progress.update(main_task_id, status=f"[blue]Downloading {filename}[/]")

            # Since we're now using the external download progress manager,
            # we'll return a placeholder task ID
            # The actual progress tracking will happen in the DownloadManager
            return main_task_id

        # Return a default task ID if item not found
        return 0

    def update_download(
        self, item_id: T, filename: str, advance: int = 0, finished: bool = False
    ) -> None:
        """
        Update the progress of a download.

        Args:
            item_id: Identifier for the parent item
            filename: Name of the file being downloaded
            advance: Number of bytes to advance the progress
            finished: Whether the download is finished
        """
        if item_id in self.task_map:
            # Update the main task status based on download state
            main_task_id = self.task_map[item_id]["task_id"]

            if finished:
                # Mark download as complete
                self._download_in_progress[item_id] = False
                self.progress.update(main_task_id, status=f"[green]Download completed[/]")
            elif advance > 0 and self._download_in_progress.get(item_id, False):
                # Only show downloading status if still in progress
                self.progress.update(main_task_id, status=f"[blue]Downloading {filename}...[/]")

    def get_summary(self) -> Table:
        """
        Generate a summary table of all tracked items.

        Returns:
            Table: Rich Table with summary information
        """
        table = Table(title="Operation Summary")
        table.add_column("Item", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Steps Completed", style="blue")

        for item_id, item in self.task_map.items():
            status = (
                "[green]Success[/]"
                if item["success"] is True
                else "[red]Failed[/]"
                if item["success"] is False
                else "[yellow]In Progress[/]"
            )

            steps_completed = f"{len(item['completed_steps'])}/{len(item['steps'])}"

            table.add_row(item["name"], status, steps_completed)

        return table
