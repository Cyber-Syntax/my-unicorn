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
        from my_unicorn.core.progress import (
            create_installation_workflow
        )
        verification_id, installation_id = (
            await create_installation_workflow(progress, "App")
        )
        # update/finish tasks as work proceeds

"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict, defaultdict
from contextlib import asynccontextmanager, suppress
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Any

from my_unicorn.core.progress.ascii import AsciiProgressBackend
from my_unicorn.core.progress.progress_types import (
    ID_CACHE_LIMIT,
    OPERATION_NAMES,
    ProgressConfig,
    ProgressType,
    TaskConfig,
    TaskInfo,
    TaskState,
)
from my_unicorn.core.protocols.progress import (
    ProgressReporter,
    ProgressTaskInfo,
)
from my_unicorn.core.protocols.progress import ProgressType as CoreProgressType
from my_unicorn.logger import get_logger
from my_unicorn.utils.progress_utils import calculate_speed

# Mapping from core protocol ProgressType to UI ProgressType
_CORE_TO_UI_PROGRESS_TYPE: dict[CoreProgressType, ProgressType] = {
    CoreProgressType.API: ProgressType.API_FETCHING,
    CoreProgressType.DOWNLOAD: ProgressType.DOWNLOAD,
    CoreProgressType.VERIFICATION: ProgressType.VERIFICATION,
    CoreProgressType.EXTRACTION: ProgressType.ICON_EXTRACTION,
    CoreProgressType.PROCESSING: ProgressType.ICON_EXTRACTION,
    CoreProgressType.INSTALLATION: ProgressType.INSTALLATION,
    CoreProgressType.UPDATE: ProgressType.UPDATE,
}


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator
    from typing import Self

    from my_unicorn.core.protocols.progress import ProgressTaskInfo


__all__ = [
    "ID_CACHE_LIMIT",
    "OPERATION_NAMES",
    "AsciiProgressBackend",
    "ProgressConfig",
    "ProgressDisplay",
    "ProgressType",
    "TaskInfo",
    "TaskState",
    "github_api_progress_task",
    "operation_progress_session",
    "progress_session",
]

logger = get_logger(__name__)


@asynccontextmanager
async def github_api_progress_task(
    progress: ProgressDisplay | None,
    *,
    task_name: str,
    total: int,
) -> AsyncIterator[str | None]:
    """Manage GitHub API progress task lifecycle.

    This context manager handles the complete lifecycle of a GitHub API
    progress task, including creation, updates, and cleanup on both
    success and failure.

    Args:
        progress: Progress display service (can be None)
        task_name: Name for the progress task
        total: Total number of API calls expected

    Yields:
        Task ID if progress service available, None otherwise

    Example:
        >>> async with github_api_progress_task(
        ...     progress, task_name="Fetching releases", total=5
        ... ) as task_id:
        ...     # Perform API operations
        ...     pass
    """
    if not progress:
        yield None
        return

    task_id = await create_api_fetching_task(
        progress,
        name=task_name,
        description="🌐 Fetching release information...",
    )
    await progress.update_task(task_id, total=float(total), completed=0.0)

    try:
        yield task_id
        await progress.finish_task(task_id, success=True)
    except Exception as exc:
        logger.debug("Failed to complete task: %s", exc)
        await progress.finish_task(task_id, success=False)
        raise


@asynccontextmanager
async def operation_progress_session(
    progress: ProgressDisplay | None,
    *,
    total_operations: int,
) -> AsyncIterator[ProgressDisplay | None]:
    """Manage progress session lifecycle for operations.

    This context manager handles the progress session lifecycle for
    operations that need progress tracking. It automatically handles
    the case where progress is None or total_operations is 0.

    Args:
        progress: Progress display service (can be None)
        total_operations: Total number of operations to track

    Yields:
        Progress service if available, None otherwise

    Example:
        >>> async with operation_progress_session(
        ...     progress, total_operations=10
        ... ) as prog:
        ...     if prog:
        ...         await prog.update_task(...)
    """
    if not progress or total_operations == 0:
        yield progress
        return

    async with progress.session(total_operations):
        yield progress


@asynccontextmanager
async def progress_session(
    total_operations: int = 0,
) -> AsyncGenerator[ProgressDisplay, None]:
    """Context manager for creating and managing a progress session.

    Creates a new ProgressDisplay instance for dependency injection.

    Args:
        total_operations: Total number of operations

    Yields:
        Progress display instance

    """
    service = ProgressDisplay()

    async with service.session(total_operations):
        yield service


class ProgressDisplay(ProgressReporter):
    """Progress display UI component implementing ProgressReporter protocol.

    This is the primary implementation of the ProgressReporter protocol for
    CLI usage. It provides rich ASCII-based progress display with session
    management and background rendering.

    During active progress sessions, logger.info() is automatically
    suppressed to prevent interference with progress bar rendering.
    Warning/error logs are always shown.

    Note:
        Core domain services should depend on the ProgressReporter protocol,
        not this concrete implementation directly.
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

        # Task management
        self._task_registry = TaskRegistry()

        # ID generation
        self._id_generator = IDGenerator()

        # Logger suppression
        self._logger_suppression = LoggerSuppression()

        # Session management
        self._session_manager = SessionManager(
            config=self.config,
            backend=self._backend,
            logger_suppression=self._logger_suppression,
            id_generator=self._id_generator,
        )

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
        return name if progress_type == ProgressType.DOWNLOAD else f"{name}"

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
            # pass configured history size so the deque is sized correctly
            max_speed_history=self.config.max_speed_history,
        )

    async def _render_loop(self) -> None:
        """Background loop for rendering progress updates."""
        await self._session_manager._render_loop()

    async def start_session(self, total_operations: int = 0) -> None:
        """Start a progress display session.

        Automatically suppresses logger.info() to prevent interference
        with progress bar rendering.

        Args:
            total_operations: Total number of operations (currently unused)

        """
        await self._session_manager.start_session(total_operations)

    async def stop_session(self) -> None:
        """Stop the progress display session.

        Automatically restores logger.info() output after progress
        session ends.
        """
        await self._session_manager.stop_session()

    async def add_task(
        self,
        name: str,
        progress_type: ProgressType | CoreProgressType,
        total: float | None = None,
        description: str | None = None,
        parent_task_id: str | None = None,
        phase: int = 1,
        total_phases: int = 1,
    ) -> str:
        """Add a new progress task.

        Args:
            name: Task name
            progress_type: Type of progress operation
                (UI or core protocol type)
            total: Total units for the task (None for indeterminate)
            description: Task description
            parent_task_id: Parent task ID for multi-phase operations
            phase: Current phase number
            total_phases: Total number of phases

        Returns:
            Unique namespaced task ID

        """
        # Convert core ProgressType to UI ProgressType if needed
        ui_progress_type: ProgressType
        if isinstance(progress_type, CoreProgressType):
            ui_progress_type = _CORE_TO_UI_PROGRESS_TYPE.get(
                progress_type, ProgressType.DOWNLOAD
            )
            if ui_progress_type is None:
                # a new CoreProgressType was added without updating the mapping.
                # fail loudly so it's caught during development, not in production.
                msg = f"No UI mapping found for CoreProgressType.{progress_type.name}. "
                msg += "Add it to _CORE_TO_UI_PROGRESS_TYPE."
                raise ValueError(msg)
        else:
            ui_progress_type = progress_type

        config = TaskConfig(
            name=name,
            progress_type=ui_progress_type,
            total=total or 0.0,
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
        if not self._session_manager._active:
            raise RuntimeError("Progress session not active")

        # Generate unique namespaced ID
        namespaced_id = self._id_generator.generate_namespaced_id(
            config.progress_type, config.name
        )

        # Create task info structure
        current_time = time.monotonic()
        task_info = self._create_task_info(namespaced_id, config, current_time)

        # Store task info in registry
        await self._task_registry.add_task_info(namespaced_id, task_info)

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
        # Only suppress expected rendering transients; log anything else for
        # visibility during debugging.
        try:
            await self._backend.render_once()
        except Exception as e:
            logger.debug(
                "Initial render skipped for task %s: %s", namespaced_id, e
            )

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
        # Get task info from registry
        task_info = await self._task_registry.get_task_info_full(task_id)
        if task_info is None:
            logger.warning("Task not found: %s", task_id)
            return

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

        # Prepare updates dict
        updates: dict[str, object] = {}
        if completed is not None:
            updates["completed"] = completed
        if total is not None:
            updates["total"] = total
        if description is not None:
            updates["description"] = description
        if speed_bps > 0.0 and completed is not None:
            updates["current_speed_mbps"] = speed_bps / (1024 * 1024)
            updates["last_speed_update"] = current_time

        # Apply updates to registry
        await self._task_registry.update_task(task_id, **updates)

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
        *,
        success: bool = True,
        description: str | None = None,
    ) -> None:
        """Mark a task as finished.

        Args:
            task_id: Task identifier
            success: Whether the task succeeded
            description: Final description

        """
        # Get task info to check if it exists and has total
        task_info = await self._task_registry.get_task_info_full(task_id)
        if task_info is None:
            logger.warning("Task not found: %s", task_id)
            return

        # Use registry finish_task method
        await self._task_registry.finish_task(
            task_id, success=success, description=description
        )

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
        async with self._session_manager.session(total_operations):
            yield

    def get_task_info(self, task_id: str) -> ProgressTaskInfo:
        """Get task information by ID.

        Returns task info as a dict matching the ProgressReporter protocol.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with completed, total, and description keys.
            Returns empty defaults if task not found.

        """
        return self._task_registry.get_task_info_sync(task_id)

    def get_task_info_full(self, task_id: str) -> TaskInfo | None:
        """Get full task information by ID (internal use).

        This method returns the full TaskInfo object for internal UI
        operations. Use get_task_info() for protocol-compliant access.

        Args:
            task_id: Task identifier

        Returns:
            Full TaskInfo object or None if not found

        """
        return self._task_registry.get_task_info_full_sync(task_id)

    def is_active(self) -> bool:
        """Check if progress session is active.

        Returns:
            True if active, False otherwise

        """
        return self._session_manager._active


class IDGenerator:
    """Generator for unique namespaced task IDs.

    Maintains counters per progress type for sequential ID generation.
    Caches generated IDs to return consistent values for the same inputs.
    Implements LRU eviction when cache exceeds size limits.

    Attributes:
        _id_cache: Ordered dictionary mapping (type, name) to generated ID
        _task_counters: Counter for each progress type
    """

    def __init__(self) -> None:
        """Initialize ID generator with empty cache and counters."""
        self._task_counters: dict[ProgressType, int] = defaultdict(int)
        self._id_cache: OrderedDict[tuple[ProgressType, str], str] = (
            OrderedDict()
        )

    def generate_namespaced_id(
        self, progress_type: ProgressType, name: str
    ) -> str:
        """Generate a unique namespaced ID for a task with optimized caching.

        For the same (progress_type, name) pair, returns the cached ID.
        For new combinations, generates a new ID using a counter and name.
        Implements LRU cache eviction when limit is exceeded.

        Args:
            progress_type: Type of progress operation
            name: Task name

        Returns:
            Unique namespaced ID in format: {prefix}_{counter}_{sanitized_name}

        Example:
            >>> gen = IDGenerator()
            >>> gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file.zip")
            'dl_1_file.zip'
            >>> gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file.zip")
            'dl_1_file.zip'  # Returns cached value
        """
        cache_key = (progress_type, name)

        # Return cached ID if available
        if cache_key in self._id_cache:
            with suppress(Exception):
                self._id_cache.move_to_end(cache_key)
            return self._id_cache[cache_key]

        # Increment counter for this type
        self._task_counters[progress_type] += 1
        counter = self._task_counters[progress_type]

        # Get type prefix for readable IDs
        type_prefixes = {
            ProgressType.API_FETCHING: "api",
            ProgressType.DOWNLOAD: "dl",
            ProgressType.VERIFICATION: "vf",
            ProgressType.ICON_EXTRACTION: "ic",
            ProgressType.INSTALLATION: "in",
            ProgressType.UPDATE: "up",
        }

        # get type prefix for readable IDs, default to "task" if not found
        # use .get() to guard against progress_type not in type_prefixes
        type_prefix = type_prefixes.get(progress_type, "task")

        # Sanitize name: keep only alphanumeric chars and safe symbols
        clean_name = "".join(c for c in name if c.isalnum() or c in "-_.")[:20]
        if not clean_name:
            clean_name = "unnamed"

        namespaced_id = f"{type_prefix}_{counter}_{clean_name}"

        # Cache the generated ID with LRU eviction
        self._id_cache[cache_key] = namespaced_id
        if len(self._id_cache) > ID_CACHE_LIMIT:
            with suppress(Exception):
                self._id_cache.popitem(last=False)

        return namespaced_id

    def clear_cache(self) -> None:
        """Clear the ID generation cache.

        Note: This clears only the cache, not the counters.
        Subsequent calls with the same inputs will generate new IDs.

        Example:
            >>> gen = IDGenerator()
            >>> id1 = gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file")
            >>> id2 = gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file")
            >>> id1 == id2
            True
            >>> gen.clear_cache()
            >>> id3 = gen.generate_namespaced_id(ProgressType.DOWNLOAD, "file")
            >>> id1 == id3
            False
        """
        self._id_cache.clear()


class LoggerSuppression:
    """Context manager for suppressing console logger during progress sessions.

    Temporarily raises console handler level to WARNING to prevent
    logger.info() from interfering with progress bar rendering.
    Automatically restores original levels on context exit, even if
    exceptions occur.

    Attributes:
        _original_console_levels: Dictionary mapping handlers to their
            original log levels.

    Example:
        with LoggerSuppression():
            # Handlers suppressed to WARNING
            progress.render()

        async with LoggerSuppression():
            # Works with async contexts too
            await progress.render()
    """

    def __init__(self) -> None:
        """Initialize the logger suppression context manager."""
        self._original_console_levels: dict[logging.Handler, int] = {}

    def __enter__(self) -> Self:
        """Enter context: suppress console handlers to WARNING level.

        Returns:
            Self for use in context manager.
        """
        self._suppress_console_logger()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context: restore console handlers to original levels.

        Args:
            exc_type: Exception type if exception occurred, None otherwise.
            exc_val: Exception value if exception occurred, None otherwise.
            exc_tb: Exception traceback if exception occurred, None otherwise.
        """
        self._restore_console_logger()

    async def __aenter__(self) -> Self:
        """Enter async context: suppress console handlers to WARNING level.

        Returns:
            Self for use in async context manager.
        """
        self._suppress_console_logger()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context: restore console handlers to original levels.

        Args:
            exc_type: Exception type if exception occurred, None otherwise.
            exc_val: Exception value if exception occurred, None otherwise.
            exc_tb: Exception traceback if exception occurred, None otherwise.
        """
        self._restore_console_logger()

    def _suppress_console_logger(self) -> None:
        """Suppress logger.info during progress session.

        Temporarily raises console handler level to WARNING to prevent
        logger.info() from interfering with progress bar rendering.
        Stores original levels for later restoration.
        """
        from my_unicorn.logger import _state  # noqa: PLC0415

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


class TaskRegistry:
    """Manages task storage and state for progress display.

    Provides thread-safe access to task information using async locks.
    Stores tasks in two ways:
    - Primary storage: _tasks dict for full TaskInfo objects
    - Index storage: _task_sets dicts by ProgressType for fast lookups
    """

    def __init__(self) -> None:
        """Initialize the task registry."""
        self._tasks: dict[str, TaskInfo] = {}
        self._task_lock = asyncio.Lock()

    async def add_task_info(self, task_id: str, task_info: TaskInfo) -> None:
        """Add a task to the registry.

        Args:
            task_id: Unique task identifier
            task_info: TaskInfo object with task metadata

        """
        async with self._task_lock:
            self._tasks[task_id] = task_info

    async def update_task(
        self, task_id: str, **updates: Any
    ) -> TaskInfo | None:
        """Update a task with new values.

        Args:
            task_id: Task identifier
            **updates: Field updates (e.g., completed=500.0, description="...")

        Returns:
            Updated TaskInfo or None if task not found

        """
        async with self._task_lock:
            if task_id not in self._tasks:
                return None

            task_info = self._tasks[task_id]

            if "completed" in updates:
                task_info.completed = float(updates["completed"])

            if "total" in updates:
                task_info.total = float(updates["total"])

            if "description" in updates:
                task_info.description = str(updates["description"])

            if "current_speed_mbps" in updates:
                task_info.current_speed_mbps = float(
                    updates["current_speed_mbps"]
                )

            if "last_speed_update" in updates:
                task_info.last_speed_update = float(
                    updates["last_speed_update"]
                )

            task_info.last_update = time.monotonic()

            return task_info

    async def get_task_info(self, task_id: str) -> ProgressTaskInfo:
        """Get task information by ID in protocol-compliant format.

        Returns task info as a dict matching the ProgressReporter protocol.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with completed, total, and description keys.
            Returns empty defaults if task not found.

        """
        # lock guarantees reads and writes cannot happen at the same time.
        async with self._task_lock:
            task = self._tasks.get(task_id)

            if task is None:
                return {
                    "completed": 0.0,
                    "total": None,
                    "description": "",
                }

            return {
                "completed": task.completed,
                "total": task.total,
                "description": task.description,
            }

    async def get_task_info_full(self, task_id: str) -> TaskInfo | None:
        """Get full task information by ID.

        This method returns the full TaskInfo object for internal UI
        operations.

        Args:
            task_id: Task identifier

        Returns:
            Full TaskInfo object or None if not found

        """
        async with self._task_lock:
            return self._tasks.get(task_id)

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
            description: Final description (if provided)

        """
        async with self._task_lock:
            if task_id not in self._tasks:
                return

            task_info = self._tasks[task_id]
            task_info.is_finished = True
            task_info.success = success

            if description is not None:
                task_info.description = description

            # Mark as completed if successful
            if success and task_info.total > 0:
                task_info.completed = task_info.total

    def get_task_info_sync(self, task_id: str) -> ProgressTaskInfo:
        """Get task info in protocol-compliant dict format (thread-safe sync).

        Intended for use by protocol methods that cannot be async.
        Note: reads are not lock-protected. A concurrent async writer may
        produce a stale or partially-updated result. Acceptable for display
        purposes; do not rely on this for correctness-critical decisions.

        Args:
            task_id: Task identifier

        Returns:
            Dict with completed, total, description keys

        """
        task = self._tasks.get(task_id)
        if task is None:
            return {"completed": 0.0, "total": None, "description": ""}
        return {
            "completed": task.completed,
            "total": task.total,
            "description": task.description,
        }

    def get_task_info_full_sync(self, task_id: str) -> TaskInfo | None:
        """Get full TaskInfo object (thread-safe sync read).

        Same caveats as get_task_info_sync: unprotected read, suitable
        for display/introspection only.


        Args:
            task_id: Task identifier

        Returns:
            Full TaskInfo object or None if not found

        """
        return self._tasks.get(task_id)


class SessionManager:
    """Manager for progress display session lifecycle and rendering.

    Handles starting and stopping progress sessions, managing the background
    render loop, and coordinating with logger suppression and ID cache
    cleanup.

    Attributes:
        _active: Whether a session is currently active
        _render_task: The asyncio Task for the background render loop
        _stop_rendering: Event to signal render loop to stop
        _backend: The progress backend for rendering
        _logger_suppression: Context manager for logger suppression
        _id_generator: ID generator for cache cleanup
        _config: Progress configuration

    Example:
        manager = SessionManager(config, backend, logger_suppression, id_generator)
        await manager.start_session()
        # ... work ...
        await manager.stop_session()
    """

    def __init__(
        self,
        config: ProgressConfig,
        backend: AsciiProgressBackend,
        logger_suppression: LoggerSuppression,
        id_generator: IDGenerator,
    ) -> None:
        """Initialize session manager.

        Args:
            config: Progress configuration
            backend: ASCII progress backend for rendering
            logger_suppression: Logger suppression context manager
            id_generator: ID generator for cache cleanup
        """
        self._config = config
        self._backend = backend
        self._logger_suppression = logger_suppression
        self._id_generator = id_generator

        # Session state
        self._active: bool = False
        self._render_task: asyncio.Task[None] | None = None
        self._stop_rendering: asyncio.Event = asyncio.Event()
        self._logger_suppression_active = False

    async def start_session(self, total_operations: int = 0) -> None:
        """Start a progress display session.

        Automatically suppresses logger.info() to prevent interference
        with progress bar rendering. Starts the background render loop.

        Args:
            total_operations: Total number of operations (currently unused)
        """
        if self._active:
            logger.warning("Progress session already active")
            return

        self._active = True
        self._stop_rendering.clear()

        # Enter the context manager for logger suppression
        await self._logger_suppression.__aenter__()
        self._logger_suppression_active = True

        # Start background rendering loop
        self._render_task = asyncio.create_task(self._render_loop())

        logger.debug(
            "Progress session started with %d total operations",
            total_operations,
        )

    async def stop_session(self) -> None:
        """Stop the progress display session.

        Stops the background render loop, performs final cleanup render,
        restores logger output, and clears the ID cache.
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

        # Exit the context manager for logger suppression
        if self._logger_suppression_active:
            await self._logger_suppression.__aexit__(None, None, None)
            self._logger_suppression_active = False

        # Clear cached state
        self._id_generator.clear_cache()

        logger.debug("Progress session stopped")

    async def _render_loop(self) -> None:
        """Background loop for rendering progress updates.

        Continuously renders the progress display at the configured refresh
        rate until stop_session() is called. Handles exceptions gracefully
        to ensure the loop continues running.
        """
        interval = 1.0 / self._config.refresh_per_second

        while not self._stop_rendering.is_set():
            try:
                await self._backend.render_once()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Error in render loop: %s", e)
                await asyncio.sleep(interval)  # Ensure loop yields control

    @asynccontextmanager
    async def session(
        self, total_operations: int = 0
    ) -> AsyncGenerator[None, None]:
        """Context manager for progress session.

        Automatically starts the session on entry and stops it on exit,
        ensuring proper cleanup even if exceptions occur.

        Args:
            total_operations: Total number of operations

        Yields:
            None

        Example:
            async with session_manager.session(total_operations=10):
                # Progress display is active
                pass
            # Progress display stopped, logged restored
        """
        await self.start_session(total_operations)
        try:
            yield
        finally:
            await self.stop_session()


# Workflow helper functions for progress display.


async def create_api_fetching_task(
    progress_display: ProgressDisplay,
    name: str,
    description: str | None = None,
) -> str:
    """Create an API fetching task.

    This is a convenience helper for creating a task to track API calls.

    Args:
        progress_display: ProgressDisplay instance to add task to
        name: Task name
        description: Task description (defaults to "Fetching {name}")

    Returns:
        Task ID for the created API fetching task

    Example:
        task_id = await create_api_fetching_task(
            progress, "GitHub API", description="Fetching releases"
        )
    """
    return await progress_display.add_task(
        name=name,
        progress_type=ProgressType.API_FETCHING,
        description=description or f"Fetching {name}",
    )


async def create_verification_task(
    progress_display: ProgressDisplay,
    name: str,
    description: str | None = None,
) -> str:
    """Create a verification task.

    This is a convenience helper for creating a task to track file verification
    (e.g., hash checking).

    Args:
        progress_display: ProgressDisplay instance to add task to
        name: Task name
        description: Task description (defaults to "Verifying {name}")

    Returns:
        Task ID for the created verification task

    Example:
        task_id = await create_verification_task(
            progress, "app.AppImage", description="SHA256 check"
        )
    """
    return await progress_display.add_task(
        name=name,
        progress_type=ProgressType.VERIFICATION,
        description=description or f"Verifying {name}",
    )


async def create_installation_workflow(
    progress_display: ProgressDisplay,
    name: str,
    with_verification: bool = True,
) -> tuple[str | None, str]:
    """Create a multi-phase installation workflow.

    This creates linked verification and installation tasks for the
    same application. The verification task is phase 1/2, and installation
    is phase 2/2.

    When with_verification=False, creates only the installation task
    as phase 1/1 (standalone).

    Args:
        progress_display: ProgressDisplay instance to add tasks to
        name: Application name
        with_verification: Whether to create a verification task

    Returns:
        Tuple of (verification_task_id, installation_task_id)
        verification_task_id will be None if with_verification=False

    Example:
        verify_id, install_id = await create_installation_workflow(
            progress, "MyApp", with_verification=True
        )
        # Now can update both tasks in sequence as phases complete
    """
    verification_task_id = None

    if with_verification:
        # Create verification task as phase 1/2
        verification_task_id = await progress_display.add_task(
            name=name,
            progress_type=ProgressType.VERIFICATION,
            description=f"Verifying {name}",
            phase=1,
            total_phases=2,
        )

        # Create installation task as phase 2/2
        installation_task_id = await progress_display.add_task(
            name=name,
            progress_type=ProgressType.INSTALLATION,
            description=f"Installing {name}",
            parent_task_id=verification_task_id,
            phase=2,
            total_phases=2,
        )
    else:
        # Create installation task as phase 1/1 (no verification)
        installation_task_id = await progress_display.add_task(
            name=name,
            progress_type=ProgressType.INSTALLATION,
            description=f"Installing {name}",
            phase=1,
            total_phases=1,
        )

    return verification_task_id, installation_task_id
