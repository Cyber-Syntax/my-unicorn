"""Logging utilities for my-unicorn AppImage installer.

This module provides structured logging functionality with configurable
levels and output formatting for the application.
"""

import logging
import logging.handlers
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Global registry to prevent duplicate loggers
_logger_instances = {}

# Progress context state
_progress_active = False
_deferred_messages = []


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"

        return super().format(record)


class MyUnicornLogger:
    """Logger manager for my-unicorn application."""

    def __init__(self, name: str = "my-unicorn"):
        """Initialize logger with given name.

        Args:
            name: Logger name

        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self._file_logging_setup = False
        self._console_handler = None

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
        file_handler = logging.handlers.RotatingFileHandler(
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
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(getattr(logging, level.upper()))

        self.logger.addHandler(file_handler)
        self._file_logging_setup = True

    def set_level(self, level: str) -> None:
        """Set logging level.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        """
        numeric_level = getattr(logging, level.upper(), logging.INFO)

        # Keep console handler at WARNING level, don't change it
        # This ensures INFO messages only go to log file, not console

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log info message."""
        global _progress_active, _deferred_messages
        if _progress_active:
            # Defer INFO messages during progress operations
            _deferred_messages.append(("INFO", message % args if args else message))
        else:
            self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message."""
        global _progress_active, _deferred_messages
        if _progress_active:
            _deferred_messages.append(("WARNING", message % args if args else message))
        else:
            self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(message, *args, **kwargs, exc_info=True)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log critical message."""
        self.logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, *args, **kwargs)

    @contextmanager
    def progress_context(self) -> Generator[None, None, None]:
        """Context manager to defer logging during progress operations."""
        global _progress_active, _deferred_messages
        old_state = _progress_active
        _progress_active = True
        _deferred_messages.clear()

        try:
            yield
        finally:
            _progress_active = old_state

            # Flush deferred messages
            if _deferred_messages:
                for level, message in _deferred_messages:
                    if level == "INFO":
                        self.logger.info(message)
                    elif level == "WARNING":
                        self.logger.warning(message)
                _deferred_messages.clear()

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

    # Setup file logging if enabled
    if enable_file_logging:
        try:
            from .config import ConfigManager
        except ImportError:
            # Fallback for direct execution
            try:
                from config import ConfigManager
            except ImportError:
                # If config not available, skip file logging
                _logger_instances[name] = logger_instance
                return logger_instance

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
