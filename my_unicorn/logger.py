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

# Module-level imports for better performance
ConfigManager = None
try:
    from .config import ConfigManager
except ImportError:
    try:
        from my_unicorn.config import ConfigManager
    except ImportError:
        pass

# Global registry to prevent duplicate loggers
_logger_instances = {}

# Thread-local storage for progress context
_thread_local = threading.local()

# Maximum number of deferred messages to prevent memory leaks
MAX_DEFERRED_MESSAGES = 1000


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""

    __slots__ = ("_colored_levels", "_reset")

    def __init__(self, *args, **kwargs):
        """Initialize formatter with cached color codes."""
        super().__init__(*args, **kwargs)
        colors = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
        }
        self._reset = "\033[0m"
        self._colored_levels = {
            level: f"{color}{level}{self._reset}" for level, color in colors.items()
        }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        colored_level = self._colored_levels.get(record.levelname)
        if colored_level:
            original_levelname = record.levelname
            record.levelname = colored_level
            try:
                return super().format(record)
            finally:
                record.levelname = original_levelname

        return super().format(record)


def _get_progress_state():
    """Get thread-local progress state."""
    if not hasattr(_thread_local, "progress_active"):
        _thread_local.progress_active = False
        _thread_local.deferred_messages = deque(maxlen=MAX_DEFERRED_MESSAGES)
    return _thread_local.progress_active, _thread_local.deferred_messages


def _set_progress_state(active: bool):
    """Set thread-local progress state."""
    if not hasattr(_thread_local, "progress_active"):
        _thread_local.progress_active = False
        _thread_local.deferred_messages = deque(maxlen=MAX_DEFERRED_MESSAGES)
    _thread_local.progress_active = active


class MyUnicornLogger:
    """Logger manager for my-unicorn application."""

    __slots__ = ("_console_handler", "_file_handler", "_file_logging_setup", "_name", "logger")

    def __init__(self, name: str = "my-unicorn"):
        """Initialize logger with given name.

        Args:
            name: Logger name

        """
        self._name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self._file_logging_setup = False
        self._console_handler = None
        self._file_handler = None

        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up console and file handlers."""
        # Console handler with colors
        self._console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        self._console_handler.setFormatter(console_formatter)
        self._console_handler.setLevel(logging.WARNING)

        self.logger.addHandler(self._console_handler)

    def setup_file_logging(self, log_file: Path, level: str = "DEBUG") -> None:
        """Set up file logging with rotation.

        Args:
            log_file: Path to log file
            level: Logging level for file output

        """
        # Prevent duplicate file handlers
        if self._file_logging_setup:
            return

        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler: max 1MB per file, keep 3 files
        # Files will be named: my-unicorn.log, my-unicorn.log.1, my-unicorn.log.2
        self._file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1024 * 1024,  # 1MB
            backupCount=3,
            encoding="utf-8",
        )

        # File formatter without colors
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._file_handler.setFormatter(file_formatter)
        self._file_handler.setLevel(getattr(logging, level.upper()))

        self.logger.addHandler(self._file_handler)
        self._file_logging_setup = True

    def set_level(self, level: str) -> None:
        """Set logging level for file handler while keeping console at WARNING.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        """
        numeric_level = getattr(logging, level.upper(), logging.INFO)

        if self._file_handler:
            self._file_handler.setLevel(numeric_level)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message."""
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log info message."""
        if not self.logger.isEnabledFor(logging.INFO):
            return

        progress_active, deferred_messages = _get_progress_state()
        if progress_active:
            deferred_messages.append(("INFO", message, args, kwargs))
        else:
            self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message."""
        if not self.logger.isEnabledFor(logging.WARNING):
            return

        progress_active, deferred_messages = _get_progress_state()
        if progress_active:
            deferred_messages.append(("WARNING", message, args, kwargs))
        else:
            self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, exc_info: bool = False, **kwargs: Any) -> None:
        """Log error message."""
        if self.logger.isEnabledFor(logging.ERROR):
            self.logger.error(message, *args, exc_info=exc_info, **kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log critical message."""
        if self.logger.isEnabledFor(logging.CRITICAL):
            self.logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback."""
        if self.logger.isEnabledFor(logging.ERROR):
            self.logger.exception(message, *args, **kwargs)

    @contextmanager
    def progress_context(self) -> Generator[None, None, None]:
        """Context manager to defer logging during progress operations."""
        progress_active, deferred_messages = _get_progress_state()
        old_state = progress_active
        _set_progress_state(True)

        # Get fresh state after setting
        _, deferred_messages = _get_progress_state()
        deferred_messages.clear()

        try:
            yield
        finally:
            _set_progress_state(old_state)

            # Flush deferred messages
            if deferred_messages:
                for item in deferred_messages:
                    if len(item) >= 3:  # New format with args
                        level, message, args, kwargs = (
                            item[0],
                            item[1],
                            item[2],
                            item[3] if len(item) > 3 else {},
                        )
                        if level == "INFO":
                            self.logger.info(message, *args, **kwargs)
                        elif level == "WARNING":
                            self.logger.warning(message, *args, **kwargs)
                    else:  # Backward compatibility with old format
                        level, formatted_message = item
                        if level == "INFO":
                            self.logger.info(formatted_message)
                        elif level == "WARNING":
                            self.logger.warning(formatted_message)
                deferred_messages.clear()

    def set_console_level_temporarily(self, level: str) -> None:
        """Temporarily set console logging level."""
        if self._console_handler:
            numeric_level = getattr(logging, level.upper(), logging.WARNING)
            self._console_handler.setLevel(numeric_level)

    def restore_console_level(self) -> None:
        """Restore console logging level to WARNING."""
        if self._console_handler:
            self._console_handler.setLevel(logging.WARNING)


def get_logger(name: str = "my-unicorn", enable_file_logging: bool = True) -> MyUnicornLogger:
    """Get logger instance with singleton pattern.

    Args:
        name: Logger name
        enable_file_logging: Whether to enable file logging

    Returns:
        Logger instance

    """
    # Use singleton pattern to prevent duplicates
    if name in _logger_instances:
        return _logger_instances[name]

    logger_instance = MyUnicornLogger(name)

    # Setup file logging if enabled and config is available
    if enable_file_logging and ConfigManager is not None:
        try:
            config_manager = ConfigManager()
            global_config = config_manager.load_global_config()
            log_file = global_config["directory"]["logs"] / "my-unicorn.log"
            log_level = global_config.get("log_level", "INFO")
            logger_instance.setup_file_logging(log_file, log_level)
        except Exception:
            # If config loading fails, continue without file logging
            pass

    # Store in registry
    _logger_instances[name] = logger_instance
    return logger_instance


# Global logger instance
logger = get_logger(enable_file_logging=False)  # Will be enabled when config is available
