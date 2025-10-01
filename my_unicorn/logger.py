"""Logging utilities for my-unicorn AppImage installer.

This module provides structured logging functionality with configurable
levels and output formatting for the application.
"""

import logging
import logging.handlers
import sys
import threading
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from my_unicorn.config import config_manager

# Logging configuration constants
MAX_DEFERRED_MESSAGES = 1000
MAX_FILE_SIZE_BYTES = 1024 * 1024  # 1 MB prevents excessive disk usage
BACKUP_COUNT = 3

# Format strings
CONSOLE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S"
FILE_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - "
    "%(funcName)s:%(lineno)d - %(message)s"
)
FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",
}

# Global registry to prevent duplicate loggers across the application
_logger_instances: dict[str, "MyUnicornLogger"] = {}

# Lock for thread-safe logger setup - prevents race conditions during init
_setup_lock = threading.Lock()

# Global shared handler registry
_shared_file_handlers: dict[Path, logging.handlers.RotatingFileHandler] = {}
_handler_lock = threading.Lock()


def _get_shared_file_handler(
    log_file: Path, level: str
) -> logging.handlers.RotatingFileHandler:
    """Get or create a shared file handler for the given log file."""
    with _handler_lock:
        if log_file not in _shared_file_handlers:
            # Ensure log directory exists before creating handler
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Create the handler only once
            handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=MAX_FILE_SIZE_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
                delay=False,
            )
            formatter = logging.Formatter(
                FILE_FORMAT, datefmt=FILE_DATE_FORMAT
            )
            handler.setFormatter(formatter)
            _shared_file_handlers[log_file] = handler

        # Update level if needed
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        _shared_file_handlers[log_file].setLevel(numeric_level)
        return _shared_file_handlers[log_file]


def _load_log_settings() -> tuple[str, str, Path]:
    """Load console level, file level, and file path from configuration.

    Returns:
        Tuple of (console log level name, file log level name, log file path).

    """
    default_console_level = "WARNING"
    default_file_level = "INFO"
    default_path = (
        Path.home() / ".config" / "my-unicorn" / "logs" / "my-unicorn.log"
    )

    try:
        global_config = config_manager.load_global_config()
    except Exception:
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
    except Exception:
        log_file = default_path

    return console_level, file_level, log_file


class LoggingError(Exception):
    """Base exception for logging errors."""


class FileRotationError(LoggingError):
    """Error during file rotation operations."""


class ConfigurationError(LoggingError):
    """Error in logging configuration."""


class ProgressManager:
    """Manages deferred logging during progress operations."""

    def __init__(self, max_messages: int | None = None) -> None:
        """Initialize progress manager.

        Args:
            max_messages: Maximum number of deferred messages to store

        """
        self._thread_local = threading.local()
        self._max_messages = max_messages or MAX_DEFERRED_MESSAGES

    def _ensure_state(self) -> None:
        """Ensure thread-local state is initialized."""
        if not hasattr(self._thread_local, "progress_active"):
            self._thread_local.progress_active = False
            self._thread_local.deferred_messages = deque(
                maxlen=self._max_messages
            )

    @property
    def _progress_active(self) -> bool:
        """Get progress active state."""
        self._ensure_state()
        return bool(self._thread_local.progress_active)

    @_progress_active.setter
    def _progress_active(self, value: bool) -> None:
        """Set progress active state."""
        self._ensure_state()
        self._thread_local.progress_active = value

    @property
    def _deferred_messages(self) -> Any:
        """Get deferred messages deque."""
        self._ensure_state()
        return self._thread_local.deferred_messages

    def is_progress_active(self) -> bool:
        """Check if progress is currently active.

        Returns:
            True if progress is active

        """
        return self._progress_active

    def defer_message(
        self,
        level: str,
        message: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        """Defer a log message during progress operations.

        Args:
            level: Log level (INFO, WARNING, etc.)
            message: Log message
            args: Message arguments
            kwargs: Message keyword arguments

        """
        self._deferred_messages.append((level, message, args, kwargs))

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

    def get_deferred_messages(
        self,
    ) -> list[tuple[str, str, tuple[Any, ...], dict[str, Any]]]:
        """Get and clear deferred messages.

        Returns:
            List of deferred messages as (level, message, args, kwargs) tuples

        """
        messages = list(self._deferred_messages)
        self._deferred_messages.clear()
        return messages


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""

    __slots__ = ("_colored_levels", "_reset")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize formatter with cached color codes.

        Args:
            *args: Arguments passed to parent formatter
            **kwargs: Keyword arguments passed to parent formatter

        """
        super().__init__(*args, **kwargs)

        # Cache color codes for performance - avoids dict lookups per format
        self._reset = COLORS["RESET"]
        self._colored_levels = {
            level: f"{color}{level}{self._reset}"
            for level, color in COLORS.items()
            if level != "RESET"
        }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Args:
            record: The log record to format

        Returns:
            Formatted log message with color codes

        """
        colored_level = self._colored_levels.get(record.levelname)
        if not colored_level:
            return super().format(record)

        original_levelname = record.levelname
        record.levelname = colored_level
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


class MyUnicornLogger:
    """Logger manager for my-unicorn application."""

    def __init__(
        self,
        name: str = "my-unicorn",
        progress_manager: ProgressManager | None = None,
    ) -> None:
        """Initialize logger with given name.

        Args:
            name: Logger name
            progress_manager: Progress manager for deferred logging

        """
        self._name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self._file_logging_setup = False
        self._console_handler: logging.StreamHandler | None = None
        self._previous_console_level: int | None = None
        self._file_handler: logging.handlers.RotatingFileHandler | None = None
        self._progress_manager = progress_manager or ProgressManager()

        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_console_handler()

    def _setup_console_handler(self) -> None:
        """Set up console handler with colors."""
        self._console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = ColoredFormatter(
            CONSOLE_FORMAT,
            datefmt=CONSOLE_DATE_FORMAT,
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
        with _setup_lock:
            if self._file_logging_setup and self._file_handler:
                return

            try:
                self._remove_existing_file_handlers()
                # Get shared handler and ensure log directory exists
                log_file.parent.mkdir(parents=True, exist_ok=True)
                self._file_handler = _get_shared_file_handler(log_file, level)

                # Critical: Add the handler to this logger instance
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

        if self._progress_manager.is_progress_active():
            self._progress_manager.defer_message("INFO", message, args, kwargs)
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

        if self._progress_manager.is_progress_active():
            self._progress_manager.defer_message(
                "WARNING", message, args, kwargs
            )
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
        with self._progress_manager.progress_context():
            try:
                yield
            finally:
                # Process deferred messages
                deferred_messages = (
                    self._progress_manager.get_deferred_messages()
                )
                for level, message, args, kwargs in deferred_messages:
                    if level == "INFO":
                        self.logger.info(message, *args, **kwargs)
                    elif level == "WARNING":
                        self.logger.warning(message, *args, **kwargs)

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
    with _setup_lock:
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

    # Create progress manager and logger instance
    progress_manager = ProgressManager()
    logger_instance = MyUnicornLogger(name, progress_manager)

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
