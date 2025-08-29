"""Progress service using Rich library for unified progress display.

This module provides a centralized progress management service that handles
different types of operations with rich visual feedback using the Rich library.
"""

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache
from pathlib import Path
from typing import Any

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

    def __init__(self) -> None:
        """Initialize speed column with cache."""
        super().__init__()
        self._speed_cache: dict[float, Text] = {}

    def render(self, task) -> Text:
        """Render the speed for a task."""
        speed = task.fields.get("speed", 0.0)
        if speed is None or speed <= 0:
            return Text("-- MB/s", style="dim")

        # Return cached result if available
        if speed in self._speed_cache:
            return self._speed_cache[speed]

        if speed >= 1.0:
            text = Text(f"{speed:.1f} MB/s", style="cyan")
        else:
            text = Text(f"{speed * 1024:.0f} KB/s", style="cyan")

        # Cache result with size limit to prevent unbounded growth
        if len(self._speed_cache) < 100:
            self._speed_cache[speed] = text

        return text


class ProgressType(Enum):
    """Types of progress operations."""

    API_FETCHING = auto()
    DOWNLOAD = auto()
    VERIFICATION = auto()
    ICON_EXTRACTION = auto()
    INSTALLATION = auto()
    UPDATE = auto()


@dataclass(frozen=True)
class ProgressConfig:
    """Configuration for progress display."""

    refresh_per_second: int = 4
    show_overall: bool = False
    show_api_fetching: bool = True
    show_downloads: bool = True
    show_post_processing: bool = True
    batch_ui_updates: bool = True
    ui_update_interval: float = 0.25  # Seconds between batched UI updates
    speed_calculation_interval: float = 0.5  # Minimum interval for speed recalculation
    max_speed_history: int = 10  # Number of speed measurements to retain


@dataclass
class TaskInfo:
    """Task information with all metadata in one structure."""

    # Core task data
    task_id: TaskID
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
    speed_history: deque[tuple[float, float]] | None = None  # (timestamp, speed) pairs

    def __post_init__(self) -> None:
        """Initialize speed history deque."""
        if self.speed_history is None:
            self.speed_history = deque(maxlen=10)


class ProgressService:
    """Centralized progress management service with proper task isolation."""

    def __init__(
        self,
        console: Console | None = None,
        config: ProgressConfig | None = None,
    ) -> None:
        """Initialize progress service."""
        self.console = console or Console()
        self.config = config or ProgressConfig()

        # Reuse single speed column instance across progress bars
        self._speed_column_cache = SpeedColumn()

        # Progress instances for different operation types with complete isolation
        self._api_progress = Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=30),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

        self._download_progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("{task.completed:.1f}/{task.total:.1f} MB"),
            self._speed_column_cache,  # Reuse single instance
            console=self.console,
        )

        self._post_processing_progress = Progress(
            TextColumn("{task.description}"),
            SpinnerColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

        self._overall_progress = Progress(
            TextColumn("[bold green]Overall Progress"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

        # State management with separate locks for better concurrency
        self._live: Live | None = None
        self._overall_task_id: TaskID | None = None
        self._tasks: dict[str, TaskInfo] = {}  # Use namespaced IDs as keys
        self._active: bool = False
        self._ui_visible: bool = False
        self._tasks_added: bool = False

        # Split locks for better performance
        self._task_lock = asyncio.Lock()  # For task data operations
        self._ui_lock = asyncio.Lock()  # For UI-related operations

        # Task ID tracking to prevent collisions
        self._task_counters: dict[ProgressType, int] = defaultdict(int)

        # Keep track of which tasks belong to which Progress instance
        self._task_sets: dict[ProgressType, set[str]] = {
            ProgressType.API_FETCHING: set(),
            ProgressType.DOWNLOAD: set(),
            ProgressType.VERIFICATION: set(),
            ProgressType.ICON_EXTRACTION: set(),
            ProgressType.INSTALLATION: set(),
            ProgressType.UPDATE: set(),
        }

        # Legacy attributes for backward compatibility
        self._api_task_ids = self._task_sets[ProgressType.API_FETCHING]
        self._download_task_ids = self._task_sets[ProgressType.DOWNLOAD]
        self._post_processing_task_ids = set()  # Combined for all post-processing types

        # UI state management
        self._layout_cache: Table | None = None
        self._pending_ui_updates: bool = False
        self._ui_update_task: asyncio.Task | None = None

    @lru_cache(maxsize=1000)
    def _generate_namespaced_id(self, progress_type: ProgressType, name: str) -> str:
        """Generate a unique namespaced ID for a task."""
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
        return f"{type_prefix}_{counter}_{clean_name}"

    def _get_progress_for_type(self, progress_type: ProgressType) -> Progress:
        """Get the appropriate Progress instance for a task type."""
        if progress_type == ProgressType.API_FETCHING:
            return self._api_progress
        elif progress_type == ProgressType.DOWNLOAD:
            return self._download_progress
        # Verification, icon extraction, installation, and update use post-processing
        return self._post_processing_progress

    def _count_active_post_processing_tasks(self) -> int:
        """Count active post-processing tasks for dynamic panel height calculation."""
        post_processing_types = {
            ProgressType.VERIFICATION,
            ProgressType.ICON_EXTRACTION,
            ProgressType.INSTALLATION,
            ProgressType.UPDATE,
        }
        # Group tasks by app and count apps that have active tasks
        app_has_active_task = set()
        for task in self._tasks.values():
            if task.progress_type in post_processing_types and not task.is_finished:
                app_name = self._extract_app_name_from_task(task)
                app_has_active_task.add(app_name)
        return len(app_has_active_task)

    def _create_filtered_post_processing_display(self, max_visible_tasks: int = 3) -> Progress:
        """Create a Progress display showing one line per app (most recent task per app)."""
        # Create a new Progress instance for filtered display
        # Handle case where console might be None or mocked during testing
        console_arg = self.console if hasattr(self.console, "get_time") else None
        filtered_progress = Progress(
            TextColumn("{task.description}"),
            SpinnerColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console_arg,
        )

        # Get all post-processing tasks (verification, icon extraction, installation, update)
        post_processing_types = {
            ProgressType.VERIFICATION,
            ProgressType.ICON_EXTRACTION,
            ProgressType.INSTALLATION,
            ProgressType.UPDATE,
        }

        relevant_tasks = [
            (namespaced_id, task)
            for namespaced_id, task in self._tasks.items()
            if task.progress_type in post_processing_types
        ]

        # Group tasks by app name (extract app name from task name/description)
        app_tasks = {}
        for namespaced_id, task in relevant_tasks:
            app_name = self._extract_app_name_from_task(task)
            if app_name not in app_tasks:
                app_tasks[app_name] = []
            app_tasks[app_name].append((namespaced_id, task))

        # For each app, find the most recent task (by last_update time)
        app_current_tasks = []
        for app_name, tasks in app_tasks.items():
            # Sort by last_update descending to get most recent first
            tasks.sort(key=lambda x: x[1].last_update, reverse=True)
            most_recent_task = tasks[0]  # Most recent task for this app
            app_current_tasks.append((app_name, most_recent_task[0], most_recent_task[1]))

        # Sort apps by priority: active tasks first, then by last update descending
        app_current_tasks.sort(key=lambda x: (x[2].is_finished, -x[2].last_update))

        # Add the most relevant app tasks to the filtered display (limit by max_visible_tasks)
        for app_name, namespaced_id, task in app_current_tasks[:max_visible_tasks]:
            # Create appropriate description with status indicator
            if task.is_finished:
                if task.success:
                    status_icon = "✅"
                else:
                    status_icon = "❌"
                # For finished tasks, show clean status
                description = f"{status_icon} {app_name}"
            else:
                # Use original description for active tasks
                description = task.description

            # Add task to filtered progress with current state
            task_id = filtered_progress.add_task(
                description=description,
                total=task.total,
                completed=task.completed,
                visible=True,
            )

            # Update the task to reflect current state
            if task.is_finished:
                filtered_progress.update(task_id, completed=task.total)

        return filtered_progress

    def _extract_app_name_from_task(self, task: TaskInfo) -> str:
        """Extract app name from task name or description for grouping."""
        # Task name patterns:
        # "Verifying filename.AppImage" -> extract filename
        # "app_name icon extraction" -> extract app_name
        # "Installing app_name" -> extract app_name
        # "Updating app_name" -> extract app_name
        # "app_name post-processing" -> extract app_name

        if "icon extraction" in task.name:
            return task.name.replace(" icon extraction", "")
        elif task.name.startswith("Installing "):
            return task.name.replace("Installing ", "")
        elif task.name.startswith("Updating "):
            return task.name.replace("Updating ", "")
        elif task.name.startswith("Verifying "):
            # Extract filename without extension
            filename = task.name.replace("Verifying ", "")
            # Remove common extensions
            for ext in [".AppImage", ".tar.gz", ".tar.xz", ".zip", ".deb", ".rpm"]:
                if filename.endswith(ext):
                    filename = filename[: -len(ext)]
            return filename
        elif " post-processing" in task.name:
            return task.name.replace(" post-processing", "")
        else:
            # Fallback: use task name as-is
            return task.name

    def _create_layout(self) -> Table:
        """Create the Rich layout for all progress displays with optimized caching."""
        # Return cached layout if no updates pending
        if self._layout_cache is not None and not self._pending_ui_updates:
            return self._layout_cache

        # Pre-create static panels only once and cache them
        if not hasattr(self, "_cached_panels"):
            self._cached_panels = {
                "overall": Panel.fit(
                    self._overall_progress,
                    title="[bold green]📊 Overall Progress",
                    border_style="green",
                    padding=(0, 1),
                )
                if self.config.show_overall
                else None,
                "api": Panel.fit(
                    self._api_progress,
                    title="[bold cyan]🌐 API Requests",
                    border_style="cyan",
                    padding=(0, 1),
                )
                if self.config.show_api_fetching
                else None,
                "downloads": Panel.fit(
                    self._download_progress,
                    title="[bold blue]📦 Downloads",
                    border_style="blue",
                    padding=(0, 1),
                )
                if self.config.show_downloads
                else None,
            }

        # Create post-processing panel dynamically with filtered task display
        if self.config.show_post_processing:
            # Calculate how many tasks can fit in the panel height
            panel_height = max(5, self._count_active_post_processing_tasks() + 3)
            max_visible_tasks = max(1, panel_height - 2)  # Account for top and bottom borders

            # Create filtered progress display showing most recent tasks
            filtered_display = self._create_filtered_post_processing_display(max_visible_tasks)

            processing_panel = Panel(
                filtered_display,
                title="[bold yellow]⚙️ Post-Processing",
                border_style="yellow",
                padding=(0, 1),
                width=45,
                height=panel_height,
            )
        else:
            processing_panel = None

        layout = Table.grid(padding=0)
        layout.add_column()
        # Add API and Post-Processing panels in a single row using a nested Table for tight layout
        api_panel = self._cached_panels.get("api")
        downloads_panel = self._cached_panels.get("downloads")
        overall_panel = self._cached_panels.get("overall")

        # Create a nested row for API + Post-Processing with no space
        if api_panel and processing_panel:
            row = Table.grid(padding=0)
            row.add_column()
            row.add_column()
            row.add_row(api_panel, processing_panel)
            layout.add_row(row)
        elif api_panel:
            layout.add_row(api_panel)
        elif processing_panel:
            layout.add_row(processing_panel)

        # Downloads panel below
        if downloads_panel:
            layout.add_row(downloads_panel)
        # Overall panel at the end if enabled
        if overall_panel:
            layout.add_row(overall_panel)

        # Cache layout and clear pending updates flag
        self._layout_cache = layout
        self._pending_ui_updates = False
        return layout

    async def _batched_ui_update_loop(self) -> None:
        """Background task to batch UI updates for better performance."""
        while self._active:
            await asyncio.sleep(self.config.ui_update_interval)
            if self._pending_ui_updates and self._live and self._live.is_started:
                try:
                    updated_layout = self._create_layout()
                    self._live.update(updated_layout)
                    self._live.refresh()
                except Exception as e:
                    logger.debug("Error in batched UI update: %s", e)

    def _schedule_ui_update(self) -> None:
        """Schedule a UI update based on configuration."""
        if self.config.batch_ui_updates:
            self._pending_ui_updates = True
        else:
            self._refresh_live_display()

    def _refresh_live_display(self) -> None:
        """Refresh the Live display with current progress state."""
        if self._live and self._live.is_started:
            try:
                # Clear cache to force layout recreation
                self._layout_cache = None
                updated_layout = self._create_layout()
                self._live.update(updated_layout)
                self._live.refresh()
            except Exception as e:
                logger.debug("Error refreshing live display: %s", e)

    async def start_session(self, total_operations: int = 0) -> None:
        """Start a progress display session."""
        async with self._ui_lock:
            if self._active:
                logger.warning("Progress session already active")
                return

            if total_operations > 0:
                self._overall_task_id = self._overall_progress.add_task(
                    "Processing...",
                    total=total_operations,
                    completed=0,
                )

            # Create and start Live display
            layout = self._create_layout()
            self._live = Live(
                layout,
                refresh_per_second=self.config.refresh_per_second,
                console=self.console,
            )
            self._live.start()
            self._active = True
            self._ui_visible = True
            self._tasks_added = True

            # Start background UI update task if batching enabled
            if self.config.batch_ui_updates:
                self._ui_update_task = asyncio.create_task(self._batched_ui_update_loop())

            logger.debug("Progress session started with %d total operations", total_operations)

    async def stop_session(self) -> None:
        """Stop the progress display session."""
        async with self._ui_lock:
            if not self._active:
                return

            self._active = False

            # Cancel background UI update task
            if self._ui_update_task and not self._ui_update_task.done():
                self._ui_update_task.cancel()
                try:
                    await self._ui_update_task
                except asyncio.CancelledError:
                    pass
                self._ui_update_task = None

            if self._live:
                self._live.stop()
                self._live = None

            self._ui_visible = False
            self._tasks_added = False
            self._overall_task_id = None

            # Clean up cached state
            self._layout_cache = None
            if hasattr(self, "_cached_panels"):
                delattr(self, "_cached_panels")
            self._generate_namespaced_id.cache_clear()

            logger.debug("Progress session stopped")

    async def add_task(
        self,
        name: str,
        progress_type: ProgressType,
        total: float = 0.0,
        description: str | None = None,
    ) -> str:
        """Add a new progress task with proper isolation."""
        if not self._active:
            raise RuntimeError("Progress session not active")

        # Generate description if not provided
        if description is None:
            description = (
                f"📦 {name}" if progress_type == ProgressType.DOWNLOAD else f"⚙️ {name}"
            )

        # Generate unique namespaced ID
        namespaced_id = self._generate_namespaced_id(progress_type, name)

        # Get progress instance
        progress_instance = self._get_progress_for_type(progress_type)

        # Prepare task creation arguments
        add_task_kwargs = {
            "description": description,
            "total": total,
            "completed": 0,
        }

        # Initialize speed field for download tasks
        if progress_type == ProgressType.DOWNLOAD:
            add_task_kwargs["speed"] = 0.0

        try:
            rich_task_id = progress_instance.add_task(**add_task_kwargs)
        except Exception as e:
            logger.error("Error creating progress task %s: %s", name, e)
            raise RuntimeError(f"Failed to create progress task: {e}") from e

        # Create task info structure
        current_time = time.time()
        task_info = TaskInfo(
            task_id=rich_task_id,
            namespaced_id=namespaced_id,
            name=name,
            progress_type=progress_type,
            total=total,
            description=description,
            created_at=current_time,
            last_update=current_time,
        )

        async with self._task_lock:
            # Store task info in consolidated structure
            self._tasks[namespaced_id] = task_info

            # Add to appropriate task set for fast lookup
            self._task_sets[progress_type].add(namespaced_id)

            # Update legacy compatibility sets
            if progress_type in {
                ProgressType.VERIFICATION,
                ProgressType.ICON_EXTRACTION,
                ProgressType.INSTALLATION,
                ProgressType.UPDATE,
            }:
                self._post_processing_task_ids.add(namespaced_id)

        # Schedule UI update
        self._schedule_ui_update()

        logger.debug(
            "Added %s task: %s (total: %.1f)",
            progress_type.name,
            name,
            total,
        )

        return namespaced_id

    def _calculate_speed_optimized(self, task: TaskInfo, current_time: float) -> None:
        """Calculate current download speed using optimized historical data algorithm."""
        if current_time - task.last_speed_update < self.config.speed_calculation_interval:
            return  # Skip if insufficient time has passed

        # Ensure speed_history is initialized
        if task.speed_history is None:
            task.speed_history = deque(maxlen=10)

        # Add current measurement to history
        task.speed_history.append((current_time, task.completed))
        task.last_speed_update = current_time

        # Calculate speed from oldest and newest measurements with minimum history
        MIN_HISTORY_SIZE = 2
        if len(task.speed_history) >= MIN_HISTORY_SIZE:
            old_time, old_completed = task.speed_history[0]
            new_time, new_completed = task.speed_history[-1]

            time_diff = new_time - old_time
            completed_diff = new_completed - old_completed

            if time_diff > 0 and completed_diff > 0:
                # Use exponential moving average for smoother speed display
                new_speed = completed_diff / time_diff
                if task.current_speed_mbps > 0:
                    # Smooth the speed with EMA (alpha = 0.3 for responsiveness)
                    task.current_speed_mbps = 0.3 * new_speed + 0.7 * task.current_speed_mbps
                else:
                    task.current_speed_mbps = new_speed
            else:
                task.current_speed_mbps = 0.0

    async def update_task(
        self,
        namespaced_id: str,
        completed: float | None = None,
        advance: float | None = None,
        description: str | None = None,
    ) -> None:
        """Update a progress task with strict type validation and speed calculation."""
        if not self._active:
            logger.warning("Cannot update task %s: Progress session not active", namespaced_id)
            return

        async with self._task_lock:
            task = self._tasks.get(namespaced_id)
            if not task or task.is_finished:
                return

            # Update task data
            current_time = time.time()
            old_completed = task.completed

            if completed is not None:
                task.completed = max(0.0, min(completed, task.total))

            if advance is not None:
                new_completed = task.completed + advance
                task.completed = max(0.0, min(new_completed, task.total))

            if description is not None:
                task.description = description

            task.last_update = current_time

            # Calculate speed for download tasks
            update_kwargs: dict[str, Any] = {}
            if task.progress_type == ProgressType.DOWNLOAD and task.completed != old_completed:
                self._calculate_speed_optimized(task, current_time)
                update_kwargs["speed"] = task.current_speed_mbps

            # Prepare update parameters
            if completed is not None:
                update_kwargs["completed"] = task.completed
            if advance is not None and task.completed != old_completed:
                update_kwargs["advance"] = task.completed - old_completed
            if description is not None:
                update_kwargs["description"] = task.description

        # Update Rich UI outside the lock
        if update_kwargs:
            progress_instance = self._get_progress_for_type(task.progress_type)
            try:
                progress_instance.update(task.task_id, **update_kwargs)
                self._schedule_ui_update()
            except Exception as e:
                logger.error("Error updating progress for task %s: %s", task.name, e)

    async def update_task_total(
        self,
        namespaced_id: str,
        new_total: float,
        completed: float | None = None,
    ) -> None:
        """Update a task's total value and optionally its completion."""
        async with self._task_lock:
            task = self._tasks.get(namespaced_id)
            if not task or task.is_finished:
                return

            task.total = max(0.0, new_total)
            task.last_update = time.time()

            if completed is not None:
                task.completed = max(0.0, min(completed, new_total))
            elif task.completed > new_total:
                task.completed = new_total

        # Update UI
        progress_instance = self._get_progress_for_type(task.progress_type)
        try:
            progress_instance.update(task.task_id, total=task.total)
            if completed is not None:
                progress_instance.update(task.task_id, completed=task.completed)
            self._schedule_ui_update()
        except Exception as e:
            logger.error("Error updating task total for %s: %s", task.name, e)

    async def finish_task(
        self,
        namespaced_id: str,
        success: bool = True,
        final_description: str | None = None,
        final_total: float | None = None,
    ) -> None:
        """Mark a task as finished with proper section isolation."""
        should_advance_overall = False

        async with self._task_lock:
            task = self._tasks.get(namespaced_id)
            if not task or task.is_finished:
                return

            # Update task state
            task.success = success
            task.is_finished = True
            task.last_update = time.time()

            if final_total is not None and final_total > 0:
                task.total = final_total
                task.completed = final_total
            else:
                task.completed = task.total

            # Generate final description if not provided
            if final_description is None:
                status_icon = "✅" if success else "❌"
                final_description = f"{status_icon} {task.name}"

            task.description = final_description
            should_advance_overall = success

        # Update UI
        progress_instance = self._get_progress_for_type(task.progress_type)
        try:
            if final_total is not None and final_total > 0:
                progress_instance.update(task.task_id, total=final_total)

            progress_instance.update(
                task.task_id,
                completed=task.completed,
                description=task.description,
            )

            self._schedule_ui_update()

            # Small delay to allow Rich to properly render the completion
            await asyncio.sleep(0.02)

        except Exception as e:
            logger.error("Error updating progress for task %s: %s", task.name, e)

        # Advance overall progress
        if should_advance_overall:
            await self._advance_overall_progress()

        logger.info(
            "Finished %s task: %s (success: %s)",
            task.progress_type.name,
            task.name,
            success,
        )

    async def _advance_overall_progress(self) -> None:
        """Advance the overall progress counter."""
        if self._overall_task_id is not None and self._active:
            try:
                self._overall_progress.advance(self._overall_task_id, 1)
            except Exception as e:
                logger.debug("Error advancing overall progress: %s", e)

    @asynccontextmanager
    async def session(self, total_operations: int = 0) -> AsyncGenerator[None, None]:
        """Context manager for progress session."""
        try:
            await self.start_session(total_operations)
            yield
        finally:
            await self.stop_session()

    def get_task_info(self, namespaced_id: str) -> TaskInfo | None:
        """Get task information by namespaced ID."""
        return self._tasks.get(namespaced_id)

    def is_active(self) -> bool:
        """Check if progress session is active."""
        return self._active

    async def create_api_fetching_task(self, endpoint: str, total_requests: int = 100) -> str:
        """Create an API fetching task."""
        # Simplify endpoint display - extract meaningful part
        display_name = endpoint.split("/")[-1].split("?")[0] if "/" in endpoint else endpoint

        return await self.add_task(
            name=f"Fetching {display_name}",
            progress_type=ProgressType.API_FETCHING,
            total=float(total_requests),
            description=f"🌐 Fetching from API: {display_name}...",
        )

    async def create_download_task(self, filename: str, size_mb: float) -> str:
        """Create a download task with guaranteed Downloads section placement."""
        return await self.add_task(
            name=Path(filename).name,
            progress_type=ProgressType.DOWNLOAD,
            total=size_mb,
        )

    async def create_verification_task(self, filename: str) -> str:
        """Create a verification task."""
        filename_only = Path(filename).name
        return await self.add_task(
            name=f"Verifying {filename_only}",
            progress_type=ProgressType.VERIFICATION,
            total=100.0,
            description=f"🔍 Verifying {filename_only}...",
        )

    async def create_icon_extraction_task(self, app_name: str) -> str:
        """Create an icon extraction task."""
        return await self.add_task(
            name=f"{app_name} icon extraction",
            progress_type=ProgressType.ICON_EXTRACTION,
            total=100.0,
            description=f"🎨 Extracting {app_name} icon...",
        )

    async def create_installation_task(self, app_name: str) -> str:
        """Create an installation task."""
        return await self.add_task(
            name=f"Installing {app_name}",
            progress_type=ProgressType.INSTALLATION,
            total=100.0,
            description=f"📁 Installing {app_name}...",
        )

    async def create_verification_task(self, filename: str) -> str:
        """Create a verification task."""
        filename_only = Path(filename).name
        return await self.add_task(
            name=f"Verifying {filename_only}",
            progress_type=ProgressType.VERIFICATION,
            total=100.0,
            description=f"🔍 Verifying {filename_only}...",
        )

    async def create_icon_extraction_task(self, app_name: str) -> str:
        """Create an icon extraction task."""
        return await self.add_task(
            name=f"{app_name} icon extraction",
            progress_type=ProgressType.ICON_EXTRACTION,
            total=100.0,
            description=f"🎨 Extracting {app_name} icon...",
        )

    async def create_installation_task(self, app_name: str) -> str:
        """Create an installation task."""
        return await self.add_task(
            name=f"Installing {app_name}",
            progress_type=ProgressType.INSTALLATION,
            total=100.0,
            description=f"📁 Installing {app_name}...",
        )

    async def create_update_task(self, app_name: str) -> str:
        """Create an update task."""
        return await self.add_task(
            name=f"Updating {app_name}",
            progress_type=ProgressType.UPDATE,
            total=100.0,
            description=f"⬆️ Updating {app_name}...",
        )

    async def create_post_processing_task(self, app_name: str) -> str:
        """Create a combined post-processing task for an AppImage.

        This combines verification, icon extraction, and installation into a single progress bar.

        Args:
            app_name: Name of the application being processed

        Returns:
            Task ID for the combined post-processing task

        """
        return await self.add_task(
            name=f"{app_name} post-processing",
            progress_type=ProgressType.INSTALLATION,  # Use INSTALLATION as the primary type
            total=100.0,
            description=f"⚙️ Processing {app_name}...",
        )

    async def cleanup_finished_tasks(self, max_finished_tasks: int = 50) -> int:
        """Clean up finished tasks to prevent memory accumulation."""
        if not self._active:
            return 0

        async with self._task_lock:
            finished_tasks = [
                (namespaced_id, task)
                for namespaced_id, task in self._tasks.items()
                if task.is_finished and task.success is not None
            ]

            # Keep only recent finished tasks
            if len(finished_tasks) <= max_finished_tasks:
                return 0

            # Remove oldest finished tasks
            finished_tasks.sort(key=lambda x: x[1].last_update)
            tasks_to_remove = finished_tasks[:-max_finished_tasks]

            removed_count = 0
            for namespaced_id, task in tasks_to_remove:
                # Remove from all tracking structures
                if namespaced_id in self._tasks:
                    del self._tasks[namespaced_id]

                # Remove from task sets
                self._task_sets[task.progress_type].discard(namespaced_id)

                # Remove from legacy sets
                if task.progress_type in {
                    ProgressType.VERIFICATION,
                    ProgressType.ICON_EXTRACTION,
                    ProgressType.INSTALLATION,
                    ProgressType.UPDATE,
                }:
                    self._post_processing_task_ids.discard(namespaced_id)

                removed_count += 1

            if removed_count > 0:
                logger.debug("Cleaned up %d finished tasks", removed_count)

            return removed_count

    async def get_memory_usage_info(self) -> dict[str, int]:
        """Get memory usage information for monitoring."""
        async with self._task_lock:
            cache_info = getattr(self._generate_namespaced_id, "cache_info", lambda: None)()
            cache_entries = (cache_info and cache_info.currsize) or 0

            return {
                "total_tasks": len(self._tasks),
                "active_tasks": sum(
                    1 for task in self._tasks.values() if not task.is_finished
                ),
                "finished_tasks": sum(1 for task in self._tasks.values() if task.is_finished),
                "api_tasks": len(self._task_sets[ProgressType.API_FETCHING]),
                "download_tasks": len(self._task_sets[ProgressType.DOWNLOAD]),
                "processing_tasks": len(self._post_processing_task_ids),
                "cache_entries": cache_entries,
            }

    async def cleanup_stuck_tasks(self, timeout_seconds: float = 300.0) -> list[str]:
        """Clean up tasks that haven't been updated recently."""
        if not self._active:
            return []

        current_time = time.time()
        stuck_tasks = []

        # Create snapshot to avoid modification during iteration
        tasks_snapshot = list(self._tasks.items())

        for namespaced_id, task in tasks_snapshot:
            if task.is_finished or task.success is not None:
                continue

            time_since_update = current_time - task.last_update
            time_since_creation = current_time - task.created_at

            if (
                time_since_update > timeout_seconds
                and time_since_creation > timeout_seconds
                and task.completed < task.total
            ):
                logger.warning(
                    "🧹 Cleaning up stuck task: %s (no update for %.1fs)",
                    task.name,
                    time_since_update,
                )

                await self.finish_task(
                    namespaced_id, success=False, final_description=f"❌ {task.name} timed out"
                )
                stuck_tasks.append(namespaced_id)

        return stuck_tasks


# Global progress service instance
_global_progress_service: ProgressService | None = None


def get_progress_service() -> ProgressService:
    """Get or create the global progress service instance."""
    global _global_progress_service
    if _global_progress_service is None:
        _global_progress_service = ProgressService()
    return _global_progress_service


def set_progress_service(service: ProgressService) -> None:
    """Set the global progress service instance."""
    global _global_progress_service
    _global_progress_service = service


@asynccontextmanager
async def progress_session(
    total_operations: int = 0,
    console: Console | None = None,
    config: ProgressConfig | None = None,
) -> AsyncGenerator[ProgressService, None]:
    """Context manager for isolated progress session."""
    global _global_progress_service
    service = ProgressService(console=console, config=config)
    old_service = _global_progress_service
    _global_progress_service = service

    try:
        async with service.session(total_operations):
            yield service
    finally:
        _global_progress_service = old_service
