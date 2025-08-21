"""Progress service using Rich library for unified progress display.

This module provides a centralized progress management service that handles
different types of operations with rich visual feedback using the Rich library.
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskID,
    TextColumn,
)
from rich.table import Table
from rich.text import Text

from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class SpeedColumn(ProgressColumn):
    """Custom column to display download speed."""

    def render(self, task) -> Text:
        """Render the speed for a task."""
        # Get the speed from task fields if available
        speed = task.fields.get("speed", 0.0)
        if speed is not None and speed > 0:
            if speed >= 1.0:
                return Text(f"{speed:.1f} MB/s", style="cyan")
            else:
                return Text(f"{speed * 1024:.0f} KB/s", style="cyan")
        else:
            return Text("-- MB/s", style="dim")


class ProgressType(Enum):
    """Types of progress operations."""

    DOWNLOAD = auto()
    VERIFICATION = auto()
    ICON_EXTRACTION = auto()
    INSTALLATION = auto()
    UPDATE = auto()


@dataclass(slots=True)
class ProgressTask:
    """Represents a progress task with its metadata."""

    task_id: TaskID
    namespaced_id: str
    name: str
    progress_type: ProgressType
    total: float = 0.0
    completed: float = 0.0
    description: str = ""
    success: bool | None = None
    last_update: float = 0.0
    created_at: float = 0.0
    is_finished: bool = False
    # Speed tracking for downloads
    last_completed: float = 0.0
    last_speed_update: float = 0.0
    current_speed_mbps: float = 0.0
    avg_speed_mbps: float = 0.0


@dataclass(slots=True, frozen=True)
class ProgressConfig:
    """Configuration for progress display."""

    refresh_per_second: int = 4
    show_overall: bool = False
    show_downloads: bool = True
    show_post_processing: bool = True


class ProgressService:
    """Centralized progress management service with proper task isolation."""

    def __init__(
        self,
        console: Console | None = None,
        config: ProgressConfig | None = None,
    ) -> None:
        """Initialize progress service.

        Args:
            console: Rich console instance, creates new if None
            config: Progress configuration, uses defaults if None

        """
        self.console = console or Console()
        self.config = config or ProgressConfig()

        # Progress instances for different operation types with complete isolation
        self._download_progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("{task.completed:.1f}/{task.total:.1f} MB"),
            SpeedColumn(),
            console=self.console,
        )

        # Combined post-processing progress for verification, icon extraction, and installation
        self._post_processing_progress = Progress(
            TextColumn("{task.description}"),
            SpinnerColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

        # Overall progress
        self._overall_progress = Progress(
            TextColumn("[bold green]Overall Progress"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

        # State management with proper isolation
        self._live: Live | None = None
        self._overall_task_id: TaskID | None = None
        self._tasks: dict[str, ProgressTask] = {}  # Use namespaced IDs as keys
        self._active: bool = False
        self._lock = asyncio.Lock()

        # Task ID tracking to prevent collisions
        self._task_counters: dict[ProgressType, int] = {
            ProgressType.DOWNLOAD: 0,
            ProgressType.VERIFICATION: 0,
            ProgressType.ICON_EXTRACTION: 0,
            ProgressType.INSTALLATION: 0,
            ProgressType.UPDATE: 0,
        }

        # Keep track of which tasks belong to which Progress instance
        self._download_task_ids: set[str] = set()
        self._post_processing_task_ids: set[str] = set()

    def _generate_namespaced_id(self, progress_type: ProgressType, name: str) -> str:
        """Generate a unique namespaced ID for a task.

        Args:
            progress_type: Type of progress operation
            name: Task name

        Returns:
            Unique namespaced ID

        """
        self._task_counters[progress_type] += 1
        counter = self._task_counters[progress_type]

        # Create predictable, unique IDs
        type_prefix = {
            ProgressType.DOWNLOAD: "dl",
            ProgressType.VERIFICATION: "vf",
            ProgressType.ICON_EXTRACTION: "ic",
            ProgressType.INSTALLATION: "in",
            ProgressType.UPDATE: "up",
        }[progress_type]

        # Sanitize name for use in ID
        clean_name = "".join(c for c in name if c.isalnum() or c in "-_.")[:20]
        return f"{type_prefix}_{counter}_{clean_name}"

    def _get_progress_for_type(self, progress_type: ProgressType) -> Progress:
        """Get the appropriate Progress instance for the given type.

        Args:
            progress_type: Type of progress operation

        Returns:
            Progress instance for the specified type

        """
        if progress_type == ProgressType.DOWNLOAD:
            return self._download_progress
        else:
            # All other types (VERIFICATION, ICON_EXTRACTION, INSTALLATION, UPDATE)
            # use the combined post-processing progress
            return self._post_processing_progress

    def _create_layout(self) -> Table:
        """Create the Rich layout for all progress displays.

        Returns:
            Table containing all progress panels

        """
        layout = Table.grid(padding=1)
        layout.add_column()

        if self.config.show_overall:
            layout.add_row(
                Panel.fit(
                    self._overall_progress,
                    title="[bold green]📊 Overall Progress",
                    border_style="green",
                    padding=(1, 2),
                )
            )

        if self.config.show_downloads:
            layout.add_row(
                Panel.fit(
                    self._download_progress,
                    title="[bold blue]📦 Downloads",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

        # Show combined post-processing panel
        if self.config.show_post_processing:
            layout.add_row(
                Panel.fit(
                    self._post_processing_progress,
                    title="[bold yellow]⚙️ Post-Processing",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )

        return layout

    async def start_session(self, total_operations: int = 0) -> None:
        """Start a progress display session.

        Args:
            total_operations: Total number of operations for overall progress

        """
        async with self._lock:
            if self._active:
                logger.warning("Progress session already active")
                return

            if total_operations > 0:
                self._overall_task_id = self._overall_progress.add_task(
                    "Processing...",
                    total=total_operations,
                    completed=0,
                )

            layout = self._create_layout()
            self._live = Live(
                layout,
                refresh_per_second=self.config.refresh_per_second,
                console=self.console,
            )
            self._live.start()
            self._active = True

            logger.debug("Progress session started with %d total operations", total_operations)

    async def stop_session(self) -> None:
        """Stop the progress display session."""
        async with self._lock:
            if not self._active:
                return

            if self._live:
                self._live.stop()
                self._live = None

            self._active = False
            self._overall_task_id = None

            logger.debug("Progress session stopped")

    async def add_task(
        self,
        name: str,
        progress_type: ProgressType,
        total: float = 0.0,
        description: str | None = None,
    ) -> str:
        """Add a new progress task with proper isolation.

        Args:
            name: Task name
            progress_type: Type of progress operation
            total: Total value for progress tracking
            description: Optional task description

        Returns:
            Namespaced task ID

        """
        # Pre-validate to fail fast
        if not self._active:
            raise RuntimeError("Progress session not active")

        # Prepare task creation data outside the lock
        if description is None:
            if progress_type == ProgressType.DOWNLOAD:
                description = f"📦 {name}"
            else:
                description = f"⚙️ {name}"

        # Step 1: Generate ID and prepare task data (under lock)
        namespaced_id = None
        task_creation_data = None

        async with self._lock:
            # Generate unique namespaced ID
            namespaced_id = self._generate_namespaced_id(progress_type, name)

            # Prepare task creation data for UI update outside lock
            task_creation_data = {
                "namespaced_id": namespaced_id,
                "name": name,
                "progress_type": progress_type,
                "total": total,
                "description": description,
            }

        # Step 2: Create Rich task outside the lock to prevent blocking
        if task_creation_data:
            progress_instance = self._get_progress_for_type(
                task_creation_data["progress_type"]
            )

            try:
                # Add task with proper field initialization for speed tracking
                add_task_kwargs = {
                    "description": task_creation_data["description"],
                    "total": task_creation_data["total"],
                    "completed": 0,
                }

                # Initialize speed field for download tasks
                if task_creation_data["progress_type"] == ProgressType.DOWNLOAD:
                    add_task_kwargs["speed"] = 0.0

                rich_task_id = progress_instance.add_task(**add_task_kwargs)
            except Exception as e:
                logger.error(
                    "Error creating progress task %s: %s", task_creation_data["name"], e
                )
                raise RuntimeError(f"Failed to create progress task: {e}") from e

            # Step 3: Store task metadata (under lock)
            async with self._lock:
                current_time = time.time()
                task = ProgressTask(
                    task_id=rich_task_id,
                    namespaced_id=task_creation_data["namespaced_id"],
                    name=task_creation_data["name"],
                    progress_type=task_creation_data["progress_type"],
                    total=task_creation_data["total"],
                    description=task_creation_data["description"],
                    last_update=current_time,
                    created_at=current_time,
                )

                self._tasks[task_creation_data["namespaced_id"]] = task

                # Track which Progress instance owns this task with proper validation
                if task_creation_data["progress_type"] == ProgressType.DOWNLOAD:
                    self._download_task_ids.add(task_creation_data["namespaced_id"])
                    # Ensure this task isn't in the other set (defensive programming)
                    self._post_processing_task_ids.discard(task_creation_data["namespaced_id"])
                else:
                    self._post_processing_task_ids.add(task_creation_data["namespaced_id"])
                    # Ensure this task isn't in the other set (defensive programming)
                    self._download_task_ids.discard(task_creation_data["namespaced_id"])

            logger.debug(
                "Added %s task: %s (total: %.1f)",
                task_creation_data["progress_type"].name,
                task_creation_data["name"],
                task_creation_data["total"],
            )

        return namespaced_id

    async def update_task(
        self,
        namespaced_id: str,
        completed: float | None = None,
        advance: float | None = None,
        description: str | None = None,
    ) -> None:
        """Update a progress task with strict type validation and speed calculation.

        Args:
            namespaced_id: Namespaced task ID to update
            completed: Set absolute completion value
            advance: Advance by relative amount
            description: Update task description

        """
        # Pre-validate without lock to fail fast
        if not self._active:
            logger.warning("Cannot update task %s: Progress session not active", namespaced_id)
            return

        # Step 1: Quick state validation and preparation (under lock)
        task_update_data = None
        async with self._lock:
            if namespaced_id not in self._tasks:
                logger.warning("Task ID %s not found", namespaced_id)
                return

            task = self._tasks[namespaced_id]

            # Don't update finished tasks
            if task.is_finished:
                logger.debug("Ignoring update for finished task: %s", task.name)
                return

            # Validate task type integrity
            expected_section = (
                "Downloads"
                if task.progress_type == ProgressType.DOWNLOAD
                else "Post-Processing"
            )
            if (
                task.progress_type == ProgressType.DOWNLOAD
                and namespaced_id not in self._download_task_ids
            ):
                logger.error(
                    "Task type integrity violation: Download task %s not in download set!",
                    task.name,
                )
                return
            elif (
                task.progress_type != ProgressType.DOWNLOAD
                and namespaced_id not in self._post_processing_task_ids
            ):
                logger.error(
                    "Task type integrity violation: Post-processing task %s not in post-processing set!",
                    task.name,
                )
                return

            # Prepare update parameters
            update_kwargs = {}
            current_time = time.time()
            old_completed = task.completed

            if completed is not None:
                # Ensure completed value is not negative and doesn't exceed total
                completed = max(0.0, min(completed, task.total))
                update_kwargs["completed"] = completed
                task.completed = completed

            if advance is not None:
                new_completed = task.completed + advance
                # Ensure new completion value is within bounds
                new_completed = max(0.0, min(new_completed, task.total))
                actual_advance = new_completed - task.completed
                update_kwargs["advance"] = actual_advance
                task.completed = new_completed

            if description is not None:
                update_kwargs["description"] = description
                task.description = description

            # Calculate speed for download tasks and include in update
            if task.progress_type == ProgressType.DOWNLOAD and task.completed != old_completed:
                self._calculate_speed(task, current_time, old_completed)
                # Add speed to the update kwargs for download tasks
                update_kwargs["speed"] = task.current_speed_mbps

            # Update last_update timestamp
            task.last_update = current_time

            # Prepare data for UI update outside the lock
            task_update_data = {
                "task_id": task.task_id,
                "progress_type": task.progress_type,
                "name": task.name,
                "expected_section": expected_section,
                "completed": task.completed,
                "total": task.total,
                "update_kwargs": update_kwargs,
            }

        # Step 2: Update Rich UI outside the lock to prevent blocking other operations
        if task_update_data and task_update_data["update_kwargs"]:
            progress_instance = self._get_progress_for_type(task_update_data["progress_type"])

            try:
                # Update progress with all parameters at once
                progress_instance.update(
                    task_update_data["task_id"], **task_update_data["update_kwargs"]
                )

                logger.debug(
                    "Updated %s task %s in %s section: %.1f/%.1f",
                    task_update_data["progress_type"].name,
                    task_update_data["name"],
                    task_update_data["expected_section"],
                    task_update_data["completed"],
                    task_update_data["total"],
                )
            except Exception as e:
                logger.error(
                    "Error updating progress for task %s: %s", task_update_data["name"], e
                )
                # Log the full exception for better debugging
                logger.exception("Full traceback for progress update error:")

    def _calculate_speed(
        self, task: ProgressTask, current_time: float, old_completed: float
    ) -> None:
        """Calculate current and average download speed for a task.

        Args:
            task: The task to calculate speed for
            current_time: Current timestamp
            old_completed: Previous completed value

        """
        if task.last_speed_update == 0.0:
            # First speed calculation
            task.last_speed_update = current_time
            task.last_completed = old_completed
            return

        time_diff = current_time - task.last_speed_update
        completed_diff = task.completed - task.last_completed

        # Only calculate speed if enough time has passed (avoid division by very small numbers)
        MIN_TIME_DIFF = 0.1  # At least 100ms
        if time_diff > MIN_TIME_DIFF and completed_diff > 0:
            # Current speed in MB/s
            task.current_speed_mbps = completed_diff / time_diff

            # Calculate average speed since task started
            total_time = current_time - task.created_at
            if total_time > 0:
                task.avg_speed_mbps = task.completed / total_time

            # Update tracking values
            task.last_speed_update = current_time
            task.last_completed = task.completed

            # Smooth the current speed with a simple moving average
            # This prevents wild fluctuations in speed display
            if task.avg_speed_mbps > 0:
                task.current_speed_mbps = (
                    task.current_speed_mbps * 0.7 + task.avg_speed_mbps * 0.3
                )

    async def update_task_total(
        self,
        namespaced_id: str,
        new_total: float,
        completed: float | None = None,
    ) -> None:
        """Update a task's total value and optionally its completion.

        This is useful when the actual size differs from the initially estimated size,
        such as when Content-Length headers don't match actual download sizes.

        Args:
            namespaced_id: Namespaced task ID to update
            new_total: New total value for the task
            completed: Optional new completion value

        """
        # Step 1: Prepare task total update data (under lock)
        task_total_update_data = None

        async with self._lock:
            if namespaced_id not in self._tasks:
                logger.warning("Task ID %s not found", namespaced_id)
                return

            task = self._tasks[namespaced_id]

            # Don't update finished tasks
            if task.is_finished:
                logger.debug("Ignoring total update for finished task: %s", task.name)
                return

            # Update task metadata with validation
            new_total = max(0.0, new_total)
            task.total = new_total
            task.last_update = time.time()

            # Adjust completion if needed
            final_completed = completed
            if completed is not None:
                # Ensure completed doesn't exceed new total
                final_completed = max(0.0, min(completed, new_total))
                task.completed = final_completed
            elif task.completed > new_total:
                # Adjust current completion if it now exceeds the new total
                final_completed = new_total
                task.completed = new_total

            # Prepare data for UI update outside the lock
            task_total_update_data = {
                "task_id": task.task_id,
                "progress_type": task.progress_type,
                "name": task.name,
                "new_total": new_total,
                "final_completed": final_completed,
            }

        # Step 2: Update Rich UI outside the lock
        if task_total_update_data:
            progress_instance = self._get_progress_for_type(
                task_total_update_data["progress_type"]
            )

            try:
                # Update the progress instance with new total
                progress_instance.update(
                    task_total_update_data["task_id"],
                    total=task_total_update_data["new_total"],
                )

                if task_total_update_data["final_completed"] is not None:
                    progress_instance.update(
                        task_total_update_data["task_id"],
                        completed=task_total_update_data["final_completed"],
                    )
            except Exception as e:
                logger.error(
                    "Error updating task total for %s: %s", task_total_update_data["name"], e
                )

    async def finish_task(
        self,
        namespaced_id: str,
        success: bool = True,
        final_description: str | None = None,
        final_total: float | None = None,
    ) -> None:
        """Mark a task as finished with proper section isolation.

        Args:
            namespaced_id: Namespaced task ID to finish
            success: Whether the task completed successfully
            final_description: Optional final description
            final_total: Optional final total to ensure 100% completion

        """
        # Step 1: Prepare task completion data (under lock)
        task_finish_data = None
        should_advance_overall = False

        async with self._lock:
            if namespaced_id not in self._tasks:
                logger.warning("Task ID %s not found", namespaced_id)
                return

            task = self._tasks[namespaced_id]

            # Don't finish tasks that are already finished
            if task.is_finished:
                logger.debug("Task %s is already finished", task.name)
                return

            # Update task state
            task.success = success
            task.is_finished = True

            # If final_total is provided, update the total to match actual completion
            if final_total is not None and final_total > 0:
                task.total = final_total
                task.completed = final_total
            else:
                task.completed = task.total

            # Generate final description if not provided
            if final_description is None:
                status_icon = "✅" if success else "❌"
                status_text = "completed" if success else "failed"
                final_description = f"{status_icon} {task.name} {status_text}"

            task.description = final_description
            task.last_update = time.time()

            # Prepare data for UI update outside the lock
            task_finish_data = {
                "task_id": task.task_id,
                "progress_type": task.progress_type,
                "name": task.name,
                "total": task.total,
                "completed": task.completed,
                "final_description": final_description,
                "final_total": final_total,
                "success": success,
            }

            # Determine if overall progress should be advanced
            should_advance_overall = success

        # Step 2: Update Rich UI outside the lock to prevent blocking other operations
        if task_finish_data:
            progress_instance = self._get_progress_for_type(task_finish_data["progress_type"])

            try:
                # Update total first if needed
                if (
                    task_finish_data["final_total"] is not None
                    and task_finish_data["final_total"] > 0
                ):
                    progress_instance.update(
                        task_finish_data["task_id"], total=task_finish_data["final_total"]
                    )

                # Then update completion and description in a single call
                progress_instance.update(
                    task_finish_data["task_id"],
                    completed=task_finish_data["completed"],
                    description=task_finish_data["final_description"],
                )

                # Small delay to allow Rich to properly render the completion
                # This is now outside the lock, so it won't block other operations
                await asyncio.sleep(0.05)

            except Exception as e:
                logger.error(
                    "Error updating progress for task %s: %s", task_finish_data["name"], e
                )

            # Advance overall progress if task completed successfully
            # This no longer requires the main lock
            if should_advance_overall:
                await self._advance_overall_progress()

            section_name = (
                "Downloads"
                if task_finish_data["progress_type"] == ProgressType.DOWNLOAD
                else "Post-Processing"
            )
            logger.info(
                "Finished %s task: %s (success: %s) in %s section",
                task_finish_data["progress_type"].name,
                task_finish_data["name"],
                task_finish_data["success"],
                section_name,
            )

    async def _advance_overall_progress(self) -> None:
        """Advance the overall progress counter."""
        # Use a quick check to avoid unnecessary work
        if self._overall_task_id is not None and self._active:
            try:
                self._overall_progress.advance(self._overall_task_id, 1)
            except Exception as e:
                logger.debug("Error advancing overall progress: %s", e)

    @asynccontextmanager
    async def session(self, total_operations: int = 0) -> AsyncGenerator[None, None]:
        """Context manager for progress session.

        Args:
            total_operations: Total number of operations for overall progress

        Yields:
            None

        """
        await self.start_session(total_operations)
        try:
            yield
        finally:
            await self.stop_session()

    def get_task_info(self, namespaced_id: str) -> ProgressTask | None:
        """Get task information by namespaced ID.

        Args:
            namespaced_id: Namespaced task ID

        Returns:
            Task information or None if not found

        """
        return self._tasks.get(namespaced_id)

    def is_active(self) -> bool:
        """Check if progress session is active.

        Returns:
            True if session is active

        """
        return self._active

    async def create_download_task(self, filename: str, size_mb: float) -> str:
        """Create a download task with guaranteed Downloads section placement.

        Args:
            filename: Name of file being downloaded
            size_mb: File size in megabytes

        Returns:
            Namespaced task ID for the download

        """
        return await self.add_task(
            name=Path(filename).name,
            progress_type=ProgressType.DOWNLOAD,
            total=size_mb,
        )

    async def create_verification_task(self, filename: str) -> str:
        """Create a verification task with guaranteed Post-Processing section placement.

        Args:
            filename: Name of file being verified

        Returns:
            Namespaced task ID for the verification

        """
        return await self.add_task(
            name=f"Verifying {Path(filename).name}",
            progress_type=ProgressType.VERIFICATION,
            total=100.0,
            description=f"🔍 Verifying {Path(filename).name}...",
        )

    async def create_icon_extraction_task(self, app_name: str) -> str:
        """Create an icon extraction task.

        Args:
            app_name: Name of the application

        Returns:
            Namespaced task ID for the icon extraction

        """
        return await self.add_task(
            name=f"{app_name} icon extraction",
            progress_type=ProgressType.ICON_EXTRACTION,
            total=100.0,
            description=f"🎨 Extracting {app_name} icon...",
        )

    async def create_installation_task(self, app_name: str) -> str:
        """Create an installation task.

        Args:
            app_name: Name of the application

        Returns:
            Namespaced task ID for the installation

        """
        return await self.add_task(
            name=f"Installing {app_name}",
            progress_type=ProgressType.INSTALLATION,
            total=100.0,
            description=f"📁 Installing {app_name}...",
        )

    async def create_update_task(self, app_name: str) -> str:
        """Create an update task.

        Args:
            app_name: Name of the application being updated

        Returns:
            Namespaced task ID for the update

        """
        return await self.add_task(
            name=f"Updating {app_name}",
            progress_type=ProgressType.UPDATE,
            total=100.0,
            description=f"🔄 Updating {app_name}...",
        )

    async def cleanup_stuck_tasks(self, timeout_seconds: float = 300.0) -> list[str]:
        """Clean up tasks that haven't been updated recently.

        Args:
            timeout_seconds: Time in seconds after which a task is considered stuck

        Returns:
            List of cleaned up namespaced task IDs

        """
        if not self._active:
            return []

        current_time = time.time()
        stuck_tasks = []

        for namespaced_id, task in list(self._tasks.items()):
            # Skip tasks that are already finished
            if task.success is not None or task.is_finished:
                continue

            time_since_update = current_time - task.last_update
            time_since_creation = current_time - task.created_at

            # Consider a task stuck if:
            # 1. No updates for timeout_seconds
            # 2. It's been alive for more than timeout_seconds
            # 3. Progress is less than 100%
            if (
                time_since_update > timeout_seconds
                and time_since_creation > timeout_seconds
                and task.completed < task.total
            ):
                section_name = (
                    "Downloads"
                    if task.progress_type == ProgressType.DOWNLOAD
                    else "Post-Processing"
                )
                logger.warning(
                    "🧹 Cleaning up stuck task: %s in %s (no update for %.1fs)",
                    task.name,
                    section_name,
                    time_since_update,
                )

                # Mark as failed and finish
                await self.finish_task(
                    namespaced_id, success=False, final_description=f"❌ {task.name} timed out"
                )
                stuck_tasks.append(namespaced_id)

        return stuck_tasks


# Global progress service instance
_global_progress_service: ProgressService | None = None


def get_progress_service() -> ProgressService:
    """Get or create the global progress service instance.

    Returns:
        Global progress service instance

    """
    global _global_progress_service
    if _global_progress_service is None:
        _global_progress_service = ProgressService()
    return _global_progress_service


def set_progress_service(service: ProgressService) -> None:
    """Set the global progress service instance.

    Args:
        service: Progress service instance to set as global

    """
    global _global_progress_service
    _global_progress_service = service


@asynccontextmanager
async def progress_session(
    total_operations: int = 0,
    console: Console | None = None,
    config: ProgressConfig | None = None,
) -> AsyncGenerator[ProgressService, None]:
    """Context manager for isolated progress session.

    Args:
        total_operations: Total number of operations for overall progress
        console: Rich console instance, creates new if None
        config: Progress configuration, uses defaults if None

    Yields:
        Progress service instance

    """
    global _global_progress_service
    service = ProgressService(console=console, config=config)
    old_service = _global_progress_service
    _global_progress_service = service

    try:
        async with service.session(total_operations):
            yield service
    finally:
        _global_progress_service = old_service
