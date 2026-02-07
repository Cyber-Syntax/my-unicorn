"""Public API for progress display.

This module is the canonical import path for ProgressDisplay.
Core modules should not import from this module directly;
they should depend on the ProgressReporter protocol from
core.protocols.progress.

Example:
    from my_unicorn.core.progress.display import ProgressDisplay

    progress = ProgressDisplay()
    task_id = progress.add_task("Download", ProgressType.DOWNLOAD, total=1000)
    progress.update_task(task_id, completed=500)
    progress.finish_task(task_id, success=True)

Implementation Details:
    ProgressDisplay implements the ProgressReporter protocol defined in
    my_unicorn.core.protocols.progress. It provides rich ASCII-based progress
    display with session management and background rendering.

Key features:
- Task management: Add, update, and finish tasks with metadata.
- Session handling: Context managers for progress sessions.
- Workflow helpers: Convenience methods for common operations like
    installation workflows.
- Background rendering: Asynchronous loop for periodic UI updates.

Note:
    For internal progress.py module usage - that module contains helper
    functions and type definitions used by this display implementation.
    External consumers should only import from this module.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from my_unicorn.core.protocols.progress import ProgressReporter
from my_unicorn.core.protocols.progress import ProgressType as CoreProgressType
from my_unicorn.logger import get_logger
from my_unicorn.utils.progress_utils import calculate_speed

from .ascii import AsciiProgressBackend
from .display_id import IDGenerator
from .display_logger import LoggerSuppression
from .display_registry import TaskRegistry
from .display_session import SessionManager
from .progress_types import ProgressConfig, ProgressType, TaskConfig, TaskInfo

logger = get_logger(__name__)

# Mapping from core protocol ProgressType to UI ProgressType
_CORE_TO_UI_PROGRESS_TYPE: dict[CoreProgressType, ProgressType] = {
    CoreProgressType.API: ProgressType.API_FETCHING,
    CoreProgressType.DOWNLOAD: ProgressType.DOWNLOAD,
    CoreProgressType.VERIFICATION: ProgressType.VERIFICATION,
    CoreProgressType.EXTRACTION: ProgressType.ICON_EXTRACTION,
    CoreProgressType.PROCESSING: ProgressType.ICON_EXTRACTION,  # Map to icon
    CoreProgressType.INSTALLATION: ProgressType.INSTALLATION,
    CoreProgressType.UPDATE: ProgressType.UPDATE,
}


# TODO: maybe better to move this to progress.py ?
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

    def get_task_info(self, task_id: str) -> dict[str, object]:
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
