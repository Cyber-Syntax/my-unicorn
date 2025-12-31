"""Logging utilities for my-unicorn AppImage installer.

This module provides structured logging with:
- Colored console output with ANSI color codes
- File rotation using standard RotatingFileHandler
- Structured format for debugging (function name, line numbers)
- Configuration-based log levels
- Thread-safe singleton pattern for logger instances
- Hierarchical logger naming (e.g., my_unicorn.install, my_unicorn.download)

Usage:
    Basic usage in any module:
        >>> from my_unicorn.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing %s", app_name)  # Use %-style formatting
        >>> logger.debug("Details: key=%s value=%s", key, value)

    Update logger configuration from config file:
        >>> from my_unicorn.logger import update_logger_from_config
        >>> update_logger_from_config()

    Temporarily adjust console output level for user-facing commands:
        >>> from my_unicorn.logger import temporary_console_level
        >>> with temporary_console_level("INFO"):
        ...     logger.info("This message will be visible to users")

Environment Variables:
    LOG_LEVEL: Override console log level for testing
        Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
        Example: LOG_LEVEL=DEBUG uv run pytest tests/test_logger.py

        Note: This is primarily for testing purposes.
        Use settings.conf for production configuration.

Important:
    - Always use %-style formatting (lazy evaluation) for better performance
    - Never use f-strings in logging calls: logger.info("Message %s", value)
    - Logger instances are thread-safe and use singleton pattern per name
    - Child loggers (e.g., my_unicorn.install) propagate to parent logger
"""

import logging
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from my_unicorn.constants import (
    DEFAULT_LOG_LEVEL,
    LOG_BACKUP_COUNT,
    LOG_COLORS,
    LOG_CONSOLE_DATE_FORMAT,
    LOG_CONSOLE_FORMAT,
    LOG_FILE_DATE_FORMAT,
    LOG_FILE_FORMAT,
    LOG_ROTATION_THRESHOLD_BYTES,
)


class _LoggerState:
    """Container for logger state (avoids module-level mutable globals)."""

    def __init__(self) -> None:
        """Initialize logger state."""
        self.instances: dict[str, logging.Logger] = {}
        self.lock = threading.Lock()
        self.root_initialized = False


# Global logger state
_state = _LoggerState()


def _load_log_settings() -> tuple[str, str, Path]:
    """Load default console level, file level, and file path.

    Returns hardcoded defaults to avoid circular imports during module init.
    Call update_logger_from_config() after initialization to use config values.

    This function is called during logger setup when no explicit configuration
    is provided. It returns safe defaults that will be overridden once the
    config module is fully initialized.

    Returns:
        Tuple of (console_level, file_level, log_path) where:
            - console_level: Log level for console output (default: WARNING)
            - file_level: Log level for file output (default: INFO)
            - log_path: Path to log file
              (default: ~/.config/my-unicorn/logs/my-unicorn.log)

    Note:
        These are bootstrap values only. The actual configuration is applied
        later via update_logger_from_config() to avoid circular dependencies.

    """
    default_console_level = "WARNING"
    default_file_level = DEFAULT_LOG_LEVEL
    default_path = (
        Path.home() / ".config" / "my-unicorn" / "logs" / "my-unicorn.log"
    )

    return default_console_level, default_file_level, default_path


def _create_console_handler(console_level: str) -> logging.StreamHandler:
    """Create and configure console handler with colored output.

    Args:
        console_level: Log level for console (e.g., "DEBUG", "INFO", "WARNING")

    Returns:
        Configured StreamHandler for console output

    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        ColoredConsoleFormatter(
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


def _create_child_logger(name: str) -> logging.Logger:
    """Create child logger that propagates to parent.

    Args:
        name: Child logger name (e.g., "my_unicorn.install")

    Returns:
        Configured child logger with propagation enabled

    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Let handlers filter
    logger.propagate = True  # Propagate to parent
    return logger


def update_logger_from_config(logger_name: str = "my_unicorn") -> None:
    """Update existing logger with settings from global config.

    This should be called after both logger and config modules are initialized
    to apply config-based log levels. Updates all child loggers as well.

    The function safely handles circular import issues by importing
    config_manager locally. If configuration loading fails, the logger
    continues with existing settings without raising an exception.

    Args:
        logger_name: Name of the root logger to update (default: "my_unicorn")

    Example:
        >>> from my_unicorn.logger import update_logger_from_config
        >>> # After config is initialized
        >>> update_logger_from_config()
        >>> # All loggers now use settings from config file

    Note:
        Silently ignores any errors during config loading to prevent
        logging configuration from breaking the application startup.

    """
    try:
        # Import here to avoid circular dependency
        from my_unicorn.config import config_manager  # noqa: PLC0415

        # Load configuration
        config = config_manager.load_global_config()

        # Extract log settings from config
        console_level_str = config.get("console_log_level", "WARNING")
        file_level_str = config.get("log_level", "INFO")

        # Convert to logging level constants
        console_level = getattr(logging, console_level_str, logging.WARNING)
        file_level = getattr(logging, file_level_str, logging.INFO)

        # Update all loggers in the my_unicorn namespace
        for name, logger_instance in logging.Logger.manager.loggerDict.items():
            # Only update loggers in our namespace
            if not isinstance(logger_instance, logging.Logger):
                continue
            # Match "my_unicorn" namespace
            if not (name == logger_name or name.startswith(f"{logger_name}.")):
                continue

            # Update handler levels for this logger
            for handler in logger_instance.handlers:
                if isinstance(
                    handler, logging.StreamHandler
                ) and not isinstance(handler, RotatingFileHandler):
                    # Console handler
                    handler.setLevel(console_level)
                elif isinstance(handler, RotatingFileHandler):
                    # File handler
                    handler.setLevel(file_level)

    except (ImportError, KeyError, AttributeError):
        # Config module not fully initialized yet - use bootstrap defaults
        # This happens during initial import before config is ready
        pass


class LoggingError(Exception):
    """Base exception for logging errors."""


class ConfigurationError(LoggingError):
    """Error in logging configuration."""


class ColoredConsoleFormatter(logging.Formatter):
    """Console formatter with ANSI color support for different log levels.

    This formatter adds color codes to log level names while preserving
    the original log record for proper formatting. Colors are applied
    temporarily during format() and then reverted.

    Colors:
        DEBUG: Cyan
        INFO: Green
        WARNING: Yellow
        ERROR: Red
        CRITICAL: Magenta

    Thread Safety:
        Safe for multi-threaded use as each format() call works on
        a separate log record instance.

    """

    def format(self, record: logging.LogRecord) -> str:
        r"""Format log record with colors for console output.

        Temporarily modifies the record's levelname with ANSI color codes,
        calls the parent formatter, then restores the original levelname.
        This ensures colors are applied without mutating the shared record.

        Args:
            record: The log record to format

        Returns:
            Formatted log message with ANSI color codes for the level name

        Example:
            Input record with levelname="ERROR" produces:
            "\033[31mERROR\033[0m - my_unicorn - Error message"

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


def setup_logging(
    name: str = "my_unicorn",
    console_level: str | None = None,
    file_level: str | None = None,
    log_file: Path | None = None,
    enable_file_logging: bool = True,  # noqa: FBT001, FBT002
) -> logging.Logger:
    """Configure logging with console and file handlers.

    Uses singleton pattern for thread-safe logger creation.

    This function implements a thread-safe singleton pattern to ensure only
    one logger instance exists per name. For hierarchical loggers (e.g.,
    "my_unicorn.install"), child loggers propagate to their parent.

    Handler Configuration:
        - Console Handler: StreamHandler with colored output to stdout
        - File Handler: RotatingFileHandler with 10MB rotation, 5 backups

    Logger Hierarchy:
        - Root logger: "my_unicorn" (handlers attached here)
        - Child loggers: "my_unicorn.install", "my_unicorn.download"
          (propagate to root)

    Thread Safety:
        Uses _logger_lock to ensure thread-safe logger creation and
        registration. Multiple threads can safely call this function
        concurrently.

    Args:
        name: Logger name, typically __name__ for module-level loggers
        console_level: Console log level (e.g., "DEBUG", "INFO", "WARNING")
        file_level: File log level (e.g., "DEBUG", "INFO")
        log_file: Path to log file
            (default: ~/.config/my-unicorn/logs/my-unicorn.log)
        enable_file_logging: Whether to enable file logging (default: True)

    Returns:
        Configured logger instance from the singleton registry

    Raises:
        ConfigurationError: If file logging setup fails
            (e.g., permission denied)

    Example:
        >>> logger = setup_logging(
        ...     name="my_unicorn.install",
        ...     console_level="INFO",
        ...     file_level="DEBUG"
        ... )
        >>> logger.info("Starting installation for %s", app_name)

    Note:
        - Logger instances are cached in _logger_instances registry
        - Child loggers are created with propagate=True
          (inherit parent handlers)
        - Root logger is created with propagate=False (terminal node)

    See Also:
        - get_logger(): Convenience wrapper for setup_logging()
        - update_logger_from_config(): Update logger settings from config file

    """
    with _state.lock:
        # Return existing logger if already configured
        if name in _state.instances:
            return _state.instances[name]

        # Handle child logger creation (propagates to parent)
        is_child_logger = (
            name != "my_unicorn"
            and "." in name
            and "my_unicorn" in _state.instances
        )
        if is_child_logger:
            logger = _create_child_logger(name)
            _state.instances[name] = logger
            return logger

        # Return cached root logger if already initialized
        if name == "my_unicorn" and _state.root_initialized:
            return _state.instances.get(name, logging.getLogger(name))

        # Load default configuration if not provided
        if console_level is None or file_level is None or log_file is None:
            cfg_console, cfg_file, cfg_path = _load_log_settings()
            console_level = console_level or cfg_console
            file_level = file_level or cfg_file
            log_file = log_file or cfg_path

        # Initialize root logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level
        logger.propagate = False  # Don't propagate to root logger

        # Remove existing handlers
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        # Add console handler
        console_handler = _create_console_handler(console_level)
        logger.addHandler(console_handler)

        # Add file handler if enabled
        if enable_file_logging and log_file:
            file_handler = _create_file_handler(log_file, file_level, name)
            logger.addHandler(file_handler)

        # Store in registry and mark as initialized
        _state.instances[name] = logger
        if name == "my_unicorn":
            _state.root_initialized = True

        return logger


@contextmanager
def temporary_console_level(
    level: str = "INFO", logger_name: str = "my_unicorn"
) -> Generator[None, None, None]:
    """Temporarily set console handler log level for user-facing output.

    This context manager is designed for commands that need to display
    information to users even when console_log_level is set to WARNING.
    It temporarily adjusts console handler levels, then restores them.

    Args:
        level: Log level to set
            ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        logger_name: Logger to modify (default: "my_unicorn")

    Example:
        >>> from my_unicorn.logger import (
        ...     get_logger,
        ...     temporary_console_level,
        ... )
        >>> logger = get_logger(__name__)
        >>>
        >>> with temporary_console_level("INFO"):
        ...     logger.info(
        ...         "Visible even if console_log_level=WARNING"
        ...     )

    Thread Safety:
        Not thread-safe. Avoid using in concurrent contexts.

    Raises:
        ValueError: If level is not a valid logging level name

    Yields:
        None

    """
    # Validate level
    if not hasattr(logging, level):
        msg = f"Invalid log level: {level}"
        raise ValueError(msg)

    console_handlers = []
    original_levels = []

    # Find all console handlers and save original levels
    root_logger = logging.getLogger(logger_name)
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, RotatingFileHandler
        ):
            console_handlers.append(handler)
            original_levels.append(handler.level)
            handler.setLevel(getattr(logging, level))

    try:
        yield
    finally:
        # Restore original levels
        for handler, orig_level in zip(
            console_handlers, original_levels, strict=False
        ):
            handler.setLevel(orig_level)


def get_logger(
    name: str = "my_unicorn",
    enable_file_logging: bool = True,  # noqa: FBT001, FBT002
) -> logging.Logger:
    """Get or create logger instance with singleton pattern.

    This is the recommended way to get a logger in my-unicorn modules.
    It wraps setup_logging() with sensible defaults and automatic
    configuration loading.

    Best Practice:
        Use __name__ as the logger name for proper hierarchical logging:
        >>> logger = get_logger(__name__)

    Args:
        name: Logger name, typically __name__ for module loggers
        enable_file_logging: Whether to enable file logging (default: True)

    Returns:
        Configured logger instance (singleton per name)

    Example:
        >>> # In my_unicorn/install.py
        >>> from my_unicorn.logger import get_logger
        >>> # Creates "my_unicorn.install" logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Installing %s version %s", app, version)

    Note:
        - First call creates and configures the logger
        - Subsequent calls return the cached instance
        - Thread-safe: safe to call from multiple threads

    See Also:
        setup_logging(): Lower-level function with more configuration options

    """
    return setup_logging(
        name=name,
        enable_file_logging=enable_file_logging,
    )


def clear_logger_state() -> None:
    """Clear global logger state for testing purposes.

    Removes all handlers, closes file handles, and clears the logger registry.
    This ensures a clean slate for test isolation.

    Thread Safety:
        Uses _logger_lock to safely clear state in multi-threaded environments.

    Warning:
        This function is intended for testing only. Do not call in production
        code as it will disrupt all active logging.

    Side Effects:
        - Closes all file handlers (flushes pending logs)
        - Removes all handlers from tracked loggers
        - Clears _logger_instances registry
        - Removes test loggers from logging.Logger.manager.loggerDict

    Example:
        >>> # In test teardown
        >>> from my_unicorn.logger import clear_logger_state
        >>> clear_logger_state()
        >>> # Next test starts with fresh logger state

    Note:
        Only clears loggers in the "my-unicorn" and "test-" namespaces
        to avoid interfering with other libraries.

    """
    with _state.lock:
        # Close and remove handlers from tracked loggers
        for logger_name in list(_state.instances.keys()):
            logger_instance = _state.instances[logger_name]
            for handler in logger_instance.handlers[:]:
                handler.close()
                logger_instance.removeHandler(handler)

        # Clear registry
        _state.instances.clear()
        _state.root_initialized = False

        # Clean up logging module's logger dict
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if logger_name.startswith("test-") or logger_name == "my-unicorn":
                log_instance = logging.getLogger(logger_name)
                for handler in log_instance.handlers[:]:
                    handler.close()
                    log_instance.removeHandler(handler)
                if logger_name in logging.Logger.manager.loggerDict:
                    del logging.Logger.manager.loggerDict[logger_name]
