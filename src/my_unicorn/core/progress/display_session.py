"""Session management for progress display.

Handles session lifecycle (start/stop) and background render loop for
ProgressDisplay, separating session concerns from the main display logic.

Example:
    session_manager = SessionManager(
        config=config,
        backend=backend,
        logger_suppression=logger_suppression,
        id_generator=id_generator,
    )

    await session_manager.start_session()
    # ... do work ...
    await session_manager.stop_session()

    # Or use context manager:
    async with session_manager.session():
        # ... do work ...
        pass
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from my_unicorn.core.progress.ascii import AsciiProgressBackend
    from my_unicorn.core.progress.display_id import IDGenerator
    from my_unicorn.core.progress.display_logger import LoggerSuppression
    from my_unicorn.core.progress.progress_types import ProgressConfig

logger = get_logger(__name__)


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
        await self._logger_suppression.__aexit__(None, None, None)

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
