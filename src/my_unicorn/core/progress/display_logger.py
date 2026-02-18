"""Logger suppression context manager for progress display sessions.

This module provides a context manager for temporarily suppressing console
logger output during progress display sessions, preventing log messages from
interfering with progress bar rendering.

Example:
    with LoggerSuppression():
        # Console handlers suppressed to WARNING level
        # Log output is muted
        pass
    # Handlers restored to original levels

    async with LoggerSuppression():
        # Same for async contexts
        await progress.render_once()
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self


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
