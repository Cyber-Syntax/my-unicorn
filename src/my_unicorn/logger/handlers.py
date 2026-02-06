"""Handler creation and management for logging system.

This module provides functions for creating and configuring logging handlers:
- Console handlers with hybrid formatting (simple INFO, structured warnings/errors)
- Rotating file handlers with automatic log rotation
- Root logger setup with QueueListener for async-safe logging

The QueueListener architecture ensures async code never blocks on I/O operations.
"""

import logging
import queue
import sys
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path

from my_unicorn.constants import (
    LOG_BACKUP_COUNT,
    LOG_CONSOLE_DATE_FORMAT,
    LOG_CONSOLE_FORMAT,
    LOG_FILE_DATE_FORMAT,
    LOG_FILE_FORMAT,
    LOG_ROTATION_THRESHOLD_BYTES,
)
from my_unicorn.logger.formatters import HybridConsoleFormatter


class ConfigurationError(Exception):
    """Error in logging configuration."""


def _create_console_handler(console_level: str) -> logging.StreamHandler:
    """Create and configure console handler with hybrid formatting.

    Uses HybridConsoleFormatter which shows simple format (message only)
    for INFO level and structured format with colors for WARNING and above.

    Args:
        console_level: Log level for console (e.g., "DEBUG", "INFO", "WARNING")

    Returns:
        Configured StreamHandler for console output

    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        HybridConsoleFormatter(
            LOG_CONSOLE_FORMAT,
            datefmt=LOG_CONSOLE_DATE_FORMAT,
        )
    )
    console_handler.setLevel(getattr(logging, console_level, logging.WARNING))
    return console_handler


def _create_file_handler(
    log_file: Path, file_level: str, logger_name: str
) -> RotatingFileHandler:
    """Create and configure rotating file handler.

    Args:
        log_file: Path to log file
        file_level: Log level for file (e.g., "DEBUG", "INFO")
        logger_name: Logger name for dummy record creation

    Returns:
        Configured RotatingFileHandler

    Raises:
        ConfigurationError: If file handler creation fails

    """
    try:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=LOG_ROTATION_THRESHOLD_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter(
                LOG_FILE_FORMAT,
                datefmt=LOG_FILE_DATE_FORMAT,
            )
        )
        file_handler.setLevel(getattr(logging, file_level, logging.INFO))

        # Rotate existing oversized log file
        if (
            log_file.exists()
            and log_file.stat().st_size >= LOG_ROTATION_THRESHOLD_BYTES
        ):
            dummy_record = logging.LogRecord(
                name=logger_name,
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="",
                args=(),
                exc_info=None,
            )
            if file_handler.shouldRollover(dummy_record):
                file_handler.doRollover()

    except OSError as e:
        msg = f"Failed to setup file logging: {e}"
        raise ConfigurationError(msg) from e
    else:
        return file_handler


def setup_root_logger(
    state,
    console_level: str,
    file_level: str,
    log_file: Path,
    enable_file_logging: bool,  # noqa: FBT001
) -> None:
    """Initialize root logger with handlers via QueueListener.

    This function is called exactly once to set up the root logger.
    All handlers are attached here and process records from the queue.

    Args:
        state: Logger state object (from logger.state module)
        console_level: Console log level (e.g., "INFO", "WARNING")
        file_level: File log level (e.g., "DEBUG", "INFO")
        log_file: Path to log file
        enable_file_logging: Whether to enable file logging

    Raises:
        ConfigurationError: If handler setup fails

    """
    # Get root logger
    root_logger = logging.getLogger("my_unicorn")
    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handlers
    root_logger.propagate = False  # Terminal node

    # Remove any existing handlers (for test isolation)
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)

    # Create handlers that will process records from queue
    handlers = []

    # Console handler
    console_handler = _create_console_handler(console_level)
    handlers.append(console_handler)

    # File handler (if enabled)
    if enable_file_logging:
        file_handler = _create_file_handler(log_file, file_level, "my_unicorn")
        handlers.append(file_handler)

    # Create queue and listener
    state.log_queue = queue.Queue(-1)  # Unbounded queue
    state.queue_listener = QueueListener(
        state.log_queue,
        *handlers,
        respect_handler_level=True,
    )
    state.queue_listener.start()

    # Attach QueueHandler to root logger
    queue_handler = QueueHandler(state.log_queue)
    root_logger.addHandler(queue_handler)

    state.root_initialized = True
