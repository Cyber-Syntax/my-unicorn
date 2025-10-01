"""Logging utilities for my-unicorn AppImage installer.

This module provides structured logging functionality with configurable
levels and output formatting for the application.
"""

import logging
import logging.handlers
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from my_unicorn.config import config_manager
from my_unicorn.constants import (
    DEFAULT_LOG_LEVEL,
    LOG_BACKUP_COUNT,
    LOG_COLORS,
    LOG_CONSOLE_DATE_FORMAT,
    LOG_CONSOLE_FORMAT,
    LOG_FILE_DATE_FORMAT,
    LOG_FILE_FORMAT,
    LOG_MAX_FILE_SIZE_BYTES,
)

# Using centralized logging constants from my_unicorn.constants

# Global registry to prevent duplicate loggers across the application
_logger_instances: dict[str, "MyUnicornLogger"] = {}

# Lock for thread-safe logger operations
_logger_lock = threading.Lock()


def _load_log_settings() -> tuple[str, str, Path]:
    """Load console level, file level, and file path from configuration.

    Returns:
        Tuple of (console log level name, file log level name, log file path).

    """
    default_console_level = "WARNING"
    default_file_level = DEFAULT_LOG_LEVEL
    default_path = (
        Path.home() / ".config" / "my-unicorn" / "logs" / "my-unicorn.log"
    )

    try:
        global_config = config_manager.load_global_config()
    except (OSError, KeyError, ValueError):
        return default_console_level, default_file_level, default_path

    console_level = str(
        global_config.get("console_log_level", default_console_level)
    ).upper()
    file_level = str(
        global_config.get("log_level", default_file_level)
    ).upper()

    try:
        logs_dir = global_config["directory"]["logs"]
        log_file = Path(logs_dir) / "my-unicorn.log"
    except (KeyError, TypeError):
        log_file = default_path

    return console_level, file_level, log_file


class LoggingError(Exception):
    """Base exception for logging errors."""


class ConfigurationError(LoggingError):
    """Error in logging configuration."""


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Args:
            record: The log record to format

        Returns:
            Formatted log message with color codes

        """
        if record.levelname in LOG_COLORS:
            color = LOG_COLORS[record.levelname]
            reset = LOG_COLORS["RESET"]
            colored_level = f"{color}{record.levelname}{reset}"

            original_levelname = record.levelname
            record.levelname = colored_level
            try:
                return super().format(record)
            finally:
                record.levelname = original_levelname

        return super().format(record)


class MyUnicornLogger:
    """Logger manager for my-unicorn application."""

    def __init__(self, name: str = "my-unicorn") -> None:
        """Initialize logger with given name.

        Args:
            name: Logger name

        """
        self._name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self._file_logging_setup = False
        self._console_handler: logging.StreamHandler | None = None
        self._previous_console_level: int | None = None
        self._file_handler: logging.handlers.RotatingFileHandler | None = None
        self._progress_active = False
        self._deferred_messages: list[
            tuple[str, str, tuple[Any, ...], dict[str, Any]]
        ] = []

        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_console_handler()

    def _setup_console_handler(self) -> None:
        """Set up console handler with colors."""
        self._console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = ColoredFormatter(
            LOG_CONSOLE_FORMAT,
            datefmt=LOG_CONSOLE_DATE_FORMAT,
        )
        self._console_handler.setFormatter(console_formatter)
        self._console_handler.setLevel(logging.WARNING)
        self.logger.addHandler(self._console_handler)

    def setup_file_logging(self, log_file: Path, level: str = "DEBUG") -> None:
        """Set up file logging with rotation.

        Args:
            log_file: Path to log file
            level: Logging level for file output

        Raises:
            ConfigurationError: If file logging setup fails

        """
        with _logger_lock:
            if self._file_logging_setup and self._file_handler:
                return

            try:
                self._remove_existing_file_handlers()
                # Ensure log directory exists
                log_file.parent.mkdir(parents=True, exist_ok=True)

                # Create file handler directly
                self._file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=LOG_MAX_FILE_SIZE_BYTES,
                    backupCount=LOG_BACKUP_COUNT,
                    encoding="utf-8",
                    delay=False,
                )
                formatter = logging.Formatter(
                    LOG_FILE_FORMAT, datefmt=LOG_FILE_DATE_FORMAT
                )
                self._file_handler.setFormatter(formatter)

                # Set level
                numeric_level = getattr(logging, level.upper(), logging.INFO)
                self._file_handler.setLevel(numeric_level)

                # Add the handler to this logger instance
                self.logger.addHandler(self._file_handler)
                self._file_logging_setup = True
            except OSError as e:
                raise ConfigurationError(
                    f"Failed to setup file logging: {e}"
                ) from e

    def _remove_existing_file_handlers(self) -> None:
        """Remove any existing file handlers to avoid duplicates."""
        handlers_to_remove = [
            handler
            for handler in self.logger.handlers
            if isinstance(handler, logging.handlers.RotatingFileHandler)
        ]

        for handler in handlers_to_remove:
            self.logger.removeHandler(handler)
            # Don't close shared handlers - other loggers may be using them

    def set_level(self, level: str) -> None:
        """Set logging level for file handler while keeping console at WARNING.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        """
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        if self._file_handler:
            self._file_handler.setLevel(numeric_level)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message.

        Args:
            message: Log message
            *args: Message arguments
            **kwargs: Message keyword arguments

        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log info message.

        Args:
            message: Log message
            *args: Message arguments
            **kwargs: Message keyword arguments

        """
        if not self.logger.isEnabledFor(logging.INFO):
            return

        if self._progress_active:
            self._deferred_messages.append(("INFO", message, args, kwargs))
        else:
            self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message.

        Args:
            message: Log message
            *args: Message arguments
            **kwargs: Message keyword arguments

        """
        if not self.logger.isEnabledFor(logging.WARNING):
            return

        if self._progress_active:
            self._deferred_messages.append(("WARNING", message, args, kwargs))
        else:
            self.logger.warning(message, *args, **kwargs)

    def error(
        self, message: str, *args: Any, exc_info: bool = False, **kwargs: Any
    ) -> None:
        """Log error message.

        Args:
            message: Log message
            *args: Message arguments
            exc_info: Include exception info
            **kwargs: Message keyword arguments

        """
        if self.logger.isEnabledFor(logging.ERROR):
            self.logger.error(message, *args, exc_info=exc_info, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log critical message.

        Args:
            message: Log message
            *args: Message arguments
            **kwargs: Message keyword arguments

        """
        if self.logger.isEnabledFor(logging.CRITICAL):
            self.logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback.

        Args:
            message: Log message
            *args: Message arguments
            **kwargs: Message keyword arguments

        """
        if self.logger.isEnabledFor(logging.ERROR):
            self.logger.exception(message, *args, **kwargs)

    @contextmanager
    def progress_context(self) -> Generator[None, None, None]:
        """Context manager to defer logging during progress operations.

        Yields:
            None

        """
        old_state = self._progress_active
        self._progress_active = True
        self._deferred_messages.clear()

        try:
            yield
        finally:
            self._progress_active = old_state
            # Process deferred messages
            for level, message, args, kwargs in self._deferred_messages:
                if level == "INFO":
                    self.logger.info(message, *args, **kwargs)
                elif level == "WARNING":
                    self.logger.warning(message, *args, **kwargs)
            self._deferred_messages.clear()

    def set_console_level(self, level: str) -> None:
        """Set console logging level.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        """
        if self._console_handler:
            numeric_level = getattr(logging, level.upper(), logging.WARNING)
            self._console_handler.setLevel(numeric_level)

    def set_console_level_temporarily(self, level: str) -> None:
        """Temporarily adjust console logging level.

        Stores the current console level so it can be restored later.

        Args:
            level: Temporary logging level name.

        """
        if not self._console_handler:
            return

        if self._previous_console_level is None:
            self._previous_console_level = self._console_handler.level

        self.set_console_level(level)

    def restore_console_level(self) -> None:
        """Restore the console logging level after a temporary change."""
        if not self._console_handler:
            return

        if self._previous_console_level is not None:
            self._console_handler.setLevel(self._previous_console_level)

        self._previous_console_level = None


def clear_logger_state() -> None:
    """Clear global logger state for testing purposes.

    Note:
        This is a temporary workaround for testing.

    """
    with _logger_lock:
        _logger_instances.clear()
        # Clear existing loggers to ensure fresh state
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if logger_name.startswith("test-") or logger_name == "my-unicorn":
                log_instance = logging.getLogger(logger_name)
                for handler in log_instance.handlers[:]:
                    log_instance.removeHandler(handler)
                # Remove from manager to ensure fresh logger creation
                if logger_name in logging.Logger.manager.loggerDict:
                    del logging.Logger.manager.loggerDict[logger_name]


def get_logger(
    name: str = "my-unicorn", enable_file_logging: bool = True
) -> MyUnicornLogger:
    """Get logger instance with singleton pattern.

    Args:
        name: Logger name
        enable_file_logging: Whether to enable file logging

    Returns:
        Logger instance

    """
    # Use singleton pattern to prevent duplicate logger instances
    if name in _logger_instances:
        return _logger_instances[name]

    # Create logger instance
    logger_instance = MyUnicornLogger(name)

    # Apply configuration-derived logging levels
    console_level, file_level, log_file = _load_log_settings()
    logger_instance.set_console_level(console_level)

    if enable_file_logging:
        logger_instance.setup_file_logging(log_file, file_level)
    else:
        # Ensure file handler adopts level if enabled later
        logger_instance.set_level(file_level)

    # Store in registry for singleton pattern
    _logger_instances[name] = logger_instance
    return logger_instance


# Global logger instance - file logging enabled later when config is available
logger = get_logger(enable_file_logging=False)
