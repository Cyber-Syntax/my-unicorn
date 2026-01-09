"""Progress display UI component using ASCII backend.

This module provides the high-level interface for managing progress sessions
and tasks. It orchestrates task lifecycle, speed calculations, and background
rendering, delegating low-level rendering to the ASCII backend.

Key features:
- Task management: Add, update, and finish tasks with metadata.
- Session handling: Context managers for progress sessions.
- Workflow helpers: Convenience methods for common operations like
    installation workflows.
- Background rendering: Asynchronous loop for periodic UI updates.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict, defaultdict
from contextlib import asynccontextmanager, suppress
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from my_unicorn.logger import get_logger
from my_unicorn.utils.progress_utils import calculate_speed

from . import progress_types
from .ascii import AsciiProgressBackend
from .progress_types import ProgressConfig, ProgressType, TaskConfig, TaskInfo

logger = get_logger(__name__)


class ProgressDisplay:
    """Progress display UI component using ASCII backend.

    During active progress sessions, logger.info() is automatically
    suppressed to prevent interference with progress bar rendering.
    Warning/error logs are always shown.
    """

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

        # Logger suppression state
        self._original_console_levels: dict[logging.Handler, int] = {}

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
            with suppress(Exception):
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
        if len(self._id_cache) > progress_types.ID_CACHE_LIMIT:
            with suppress(Exception):
                self._id_cache.popitem(last=False)

        return namespaced_id

    def _clear_id_cache(self) -> None:
        """Clear the ID generation cache."""
        self._id_cache.clear()

    def _generate_default_description(
        self, name: str, progress_type: ProgressType
    ) -> str:
        """Generate default description based on progress type.

        Args:
            name: Task name
            progress_type: Type of progress operation

        Returns:
            Default description string

        """
        return (
            f"📦 {name}"
            if progress_type == ProgressType.DOWNLOAD
            else f"⚙️ {name}"
        )

    def _create_task_info(
        self, namespaced_id: str, config: TaskConfig, current_time: float
    ) -> TaskInfo:
        """Create a TaskInfo instance from TaskConfig.

        Args:
            namespaced_id: Generated unique ID for the task
            config: Task configuration
            current_time: Current monotonic time

        Returns:
            TaskInfo instance

        """
        return TaskInfo(
            task_id=namespaced_id,
            namespaced_id=namespaced_id,
            name=config.name,
            progress_type=config.progress_type,
            total=config.total,
            description=(
                config.description
                or self._generate_default_description(
                    config.name, config.progress_type
                )
            ),
            created_at=current_time,
            last_update=current_time,
            last_speed_update=current_time,
            parent_task_id=config.parent_task_id,
            phase=config.phase,
            total_phases=config.total_phases,
        )

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

    def _suppress_console_logger(self) -> None:
        """Suppress logger.info during progress session.

        Temporarily raises console handler level to WARNING to prevent
        logger.info() from interfering with progress bar rendering.
        Stores original levels for later restoration.
        """
        from my_unicorn.logger import _state

        if _state.queue_listener is not None:
            for handler in _state.queue_listener.handlers:
                if isinstance(
                    handler, logging.StreamHandler
                ) and not isinstance(handler, RotatingFileHandler):
                    # Store original level
                    self._original_console_levels[handler] = handler.level
                    # Suppress INFO level during progress
                    handler.setLevel(logging.WARNING)

    def _restore_console_logger(self) -> None:
        """Restore console logger to original levels after progress session."""
        for handler, original_level in self._original_console_levels.items():
            handler.setLevel(original_level)
        self._original_console_levels.clear()

    async def start_session(self, total_operations: int = 0) -> None:
        """Start a progress display session.

        Automatically suppresses logger.info() to prevent interference
        with progress bar rendering.

        Args:
            total_operations: Total number of operations (currently unused)

        """
        if self._active:
            logger.warning("Progress session already active")
            return

        self._active = True
        self._stop_rendering.clear()

        # Suppress logger.info during progress
        self._suppress_console_logger()

        # Start background rendering loop
        self._render_task = asyncio.create_task(self._render_loop())

        logger.debug(
            "Progress session started with %d total operations",
            total_operations,
        )

    async def stop_session(self) -> None:
        """Stop the progress display session.

        Automatically restores logger.info() output after progress
        session ends.
        """
        if not self._active:
            return

        self._active = False
        self._stop_rendering.set()

        # Stop rendering task
        if self._render_task:
            self._render_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._render_task
            self._render_task = None

        # Final cleanup render
        await self._backend.cleanup()

        # Restore logger.info after progress
        self._restore_console_logger()

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
        config = TaskConfig(
            name=name,
            progress_type=progress_type,
            total=total,
            description=description,
            parent_task_id=parent_task_id,
            phase=phase,
            total_phases=total_phases,
        )
        return await self.add_task_from_config(config)

    async def add_task_from_config(self, config: TaskConfig) -> str:
        """Add a new progress task from configuration.

        Args:
            config: Task configuration

        Returns:
            Unique namespaced task ID

        """
        if not self._active:
            raise RuntimeError("Progress session not active")

        # Generate unique namespaced ID
        namespaced_id = self._generate_namespaced_id(
            config.progress_type, config.name
        )

        # Create task info structure
        current_time = time.monotonic()
        task_info = self._create_task_info(namespaced_id, config, current_time)

        async with self._task_lock:
            # Store task info in consolidated structure
            self._tasks[namespaced_id] = task_info

            # Add to appropriate task set for fast lookup
            self._task_sets[config.progress_type].add(namespaced_id)

        # Add task to backend
        self._backend.add_task(
            task_id=namespaced_id,
            name=config.name,
            progress_type=config.progress_type,
            total=config.total,
            parent_task_id=config.parent_task_id,
            phase=config.phase,
            total_phases=config.total_phases,
        )

        # Perform an immediate render to make short-lived phases visible.
        # Awaiting the render here ensures the UI is updated before callers
        # may immediately finish the next phase (common in fast unit tests
        # or synchronous flows).
        with suppress(Exception):
            await self._backend.render_once()

        logger.debug(
            "Added %s task: %s (total: %.1f)",
            config.progress_type.name,
            config.name,
            config.total,
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
