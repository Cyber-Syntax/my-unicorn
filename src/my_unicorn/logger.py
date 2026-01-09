"""Logging utilities for my-unicorn AppImage installer.

This module provides structured logging with:
- Colored console output with ANSI color codes
- File rotation using standard RotatingFileHandler
- Async-safe logging via QueueHandler/QueueListener
  (prevents event loop blocking)
- Structured format for debugging (function name, line numbers)
- Configuration-based log levels
- Thread-safe singleton pattern for root logger initialization
- Hierarchical logger naming (e.g., my_unicorn.install, my_unicorn.download)

Architecture:
    Application → QueueHandler → Queue → QueueListener Thread
                                              ↓
                                    Console + File Handlers

    This design prevents async code from blocking on file I/O or
    handler operations. All loggers (root + children) write to a
    shared queue, processed asynchronously.

Usage:
    Basic usage in any module:
        >>> from my_unicorn.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing %s", app_name)  # Use %-style formatting
        >>> logger.debug("Details: key=%s value=%s", key, value)

    Update logger configuration from config file:
        >>> from my_unicorn.logger import update_logger_from_config
        >>> update_logger_from_config()

Environment Variables:
    LOG_LEVEL: Override console log level for testing
        Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
        Example: LOG_LEVEL=DEBUG uv run pytest tests/test_logger.py

        Note: This is primarily for testing purposes.
        Use settings.conf for production configuration.

IMPORTANT RULES FOR CONTRIBUTORS:
    1. Always use: logger = get_logger(__name__)
    2. Never call logging.basicConfig()
    3. Never attach handlers to child loggers
       (only root has handlers)
    4. Never use f-strings in log calls:
       logger.info(f"Bad {x}")
       Always use %-formatting: logger.info("Good %s", x)
    5. Handlers are ONLY attached to root 'my_unicorn' logger
       via QueueListener
    6. Child loggers automatically propagate to parent
       (Python logging handles this)
    7. QueueHandler prevents async code from blocking on I/O

Thread Safety:
    - Logger instances are thread-safe (Python logging guarantees)
    - Root logger initialization uses threading.Lock
    - QueueListener runs in separate thread for async safety
    - Child loggers propagate to parent automatically
"""

import atexit
import contextlib
import logging
import queue
import sys
import threading
import time
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path

from my_unicorn.domain.constants import (
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
    """Container for logger state (avoids module-level mutable globals).

    Attributes:
        lock: Thread lock for singleton initialization
        root_initialized: Whether root logger has been set up
        config_applied: Whether config file settings have been loaded
        queue_listener: Background thread processing log records
        log_queue: Queue for async-safe log record processing

    """

    def __init__(self) -> None:
        """Initialize logger state."""
        self.lock = threading.Lock()
        self.root_initialized = False
        self.config_applied = False
        self.queue_listener: QueueListener | None = None
        self.log_queue: queue.Queue | None = None


# Global logger state
_state = _LoggerState()


def flush_all_handlers() -> None:
    """Flush all handlers in the QueueListener to ensure writes complete.

    This function ensures that all pending log records in the queue are
    processed and all file handlers have written their buffers to disk.
    Critical for tests and scenarios where immediate file persistence is
    required.

    The function:
    1. Waits for queue to be empty (all records dequeued)
    2. Explicitly flushes each handler's buffer to disk
    3. Gives queue listener thread time to process final records

    Thread Safety:
        Safe to call from any thread. No lock required as it only
        reads _state.queue_listener and calls thread-safe methods.

    Example:
        >>> logger.info("Important message")
        >>> flush_all_handlers()  # Ensure message is on disk
        >>> # Now safe to read log file

    Note:
        This is particularly important when using QueueListener because
        records may be dequeued but not yet written to disk.

    """
    if _state.queue_listener is not None and _state.log_queue is not None:
        # Wait for queue to be empty (all records dequeued)
        # QueueListener doesn't use task_done(), so poll the queue
        timeout = 5.0  # Maximum wait time
        start_time = time.time()
        while not _state.log_queue.empty():
            if time.time() - start_time > timeout:
                break
            time.sleep(0.01)  # Small sleep to avoid busy-waiting

        # Give queue listener thread time to process final records
        time.sleep(0.1)

        # Flush all handlers to ensure writes complete
        for handler in _state.queue_listener.handlers:
            with contextlib.suppress(OSError, ValueError):
                # Ignore flush errors (handler closed/unavailable)
                handler.flush()


def _cleanup_logging() -> None:
    """Clean up QueueListener on application exit.

    Registered with atexit to ensure proper shutdown.
    """
    if _state.queue_listener is not None:
        flush_all_handlers()
        _state.queue_listener.stop()
        _state.queue_listener = None


# Register cleanup handler
atexit.register(_cleanup_logging)


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


def _setup_root_logger(
    console_level: str,
    file_level: str,
    log_file: Path,
    enable_file_logging: bool,  # noqa: FBT001
) -> None:
    """Initialize root logger with handlers via QueueListener.

    This function is called exactly once to set up the root logger.
    All handlers are attached here and process records from the queue.

    Args:
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
    _state.log_queue = queue.Queue(-1)  # Unbounded queue
    _state.queue_listener = QueueListener(
        _state.log_queue,
        *handlers,
        respect_handler_level=True,
    )
    _state.queue_listener.start()

    # Attach QueueHandler to root logger
    queue_handler = QueueHandler(_state.log_queue)
    root_logger.addHandler(queue_handler)

    _state.root_initialized = True


def update_logger_from_config() -> None:
    """Update logger handler levels from global config.

    This should be called after both logger and config modules are
    initialized to apply config-based log levels. Only updates handler
    levels, never adds/removes handlers.

    The function safely handles circular import issues by importing
    config_manager locally. If configuration loading fails, the logger
    continues with existing settings without raising an exception.

    Example:
        >>> from my_unicorn.logger import update_logger_from_config
        >>> # After config is initialized
        >>> update_logger_from_config()
        >>> # All handlers now use settings from config file

    Note:
        Silently ignores any errors during config loading to prevent
        logging configuration from breaking the application startup.
        Sets _state.config_applied = True on success.

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

        # Update handlers in the QueueListener
        if _state.queue_listener is not None:
            for handler in _state.queue_listener.handlers:
                if isinstance(
                    handler, logging.StreamHandler
                ) and not isinstance(handler, RotatingFileHandler):
                    # Console handler
                    handler.setLevel(console_level)
                elif isinstance(handler, RotatingFileHandler):
                    # File handler
                    handler.setLevel(file_level)

        # Mark config as applied
        _state.config_applied = True

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


class SimpleConsoleFormatter(logging.Formatter):
    """Minimal console formatter that only shows the message content.

    This formatter is designed for temporary user-facing output where
    timestamp, module name, and log level information would be redundant.
    It outputs only the message content, making it ideal for commands
    that use logger.info() as a replacement for print().

    Usage:
        Used by HybridConsoleFormatter for INFO level messages to show only
        the message content. Not normally instantiated directly.

    Example Output:
        Standard formatter: "21:30:08 - my_unicorn.update - INFO - Message"
        Simple formatter:   "Message"

    Thread Safety:
        Safe for multi-threaded use as each format() call works on
        a separate log record instance.

    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record showing only the message.

        Args:
            record: The log record to format

        Returns:
            The message content only, without metadata

        """
        return record.getMessage()


class HybridConsoleFormatter(logging.Formatter):
    """Console formatter with simple format for INFO, structured for others.

    This formatter provides clean output for user-facing INFO messages while
    maintaining detailed context for warnings and errors. INFO level messages
    show only the message content, while WARNING and above show timestamp,
    module, level, and message with color coding.

    Format Selection:
        - INFO: Simple format (message only)
        - WARNING/ERROR/CRITICAL: Structured format with colors and metadata
        - DEBUG: Structured format with colors and metadata

    Example Output:
        INFO:     "🚀 Starting installation"
        WARNING:  "12:30:45 - my_unicorn - WARNING - Cache outdated"
        ERROR:    "12:30:45 - my_unicorn - ERROR - Connection failed"

    Thread Safety:
        Safe for multi-threaded use as each format() call works on
        a separate log record instance.

    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
    ) -> None:
        """Initialize hybrid formatter with structured format template.

        Args:
            fmt: Format string for structured messages (WARNING and above)
            datefmt: Date format string for timestamps

        """
        super().__init__(fmt, datefmt)
        self._simple_formatter = SimpleConsoleFormatter()
        self._colored_formatter = ColoredConsoleFormatter(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record using simple or structured format by level.

        Args:
            record: The log record to format

        Returns:
            Formatted message (simple for INFO, structured for others)

        """
        if record.levelno == logging.INFO:
            return self._simple_formatter.format(record)
        return self._colored_formatter.format(record)


def setup_logging(
    name: str = "my_unicorn",
    console_level: str | None = None,
    file_level: str | None = None,
    log_file: Path | None = None,
    enable_file_logging: bool = True,  # noqa: FBT001, FBT002
) -> logging.Logger:
    """Configure logging with async-safe QueueHandler architecture.

    This function ensures the root logger is initialized exactly once,
    then returns the appropriate logger instance. Child loggers are
    created automatically by Python's logging system and propagate to
    the root.

    Handler Configuration (via QueueListener):
        - Console Handler: StreamHandler with colored output to stdout
        - File Handler: RotatingFileHandler with 10MB rotation, 5 backups
        - Queue Handler: Non-blocking handler on all loggers

    Logger Hierarchy:
        - Root logger: "my_unicorn" (QueueHandler → Queue → Listener)
        - Child loggers: "my_unicorn.install", "my_unicorn.download"
          (auto-propagate to root)

    Thread Safety:
        Uses _state.lock to ensure thread-safe root logger initialization.
        Multiple threads can safely call this function concurrently.

    Args:
        name: Logger name, typically __name__ for module-level loggers
        console_level: Console log level ("DEBUG", "INFO", "WARNING")
        file_level: File log level ("DEBUG", "INFO")
        log_file: Path to log file
            (default: ~/.config/my-unicorn/logs/my-unicorn.log)
        enable_file_logging: Whether to enable file logging

    Returns:
        Logger instance (singleton per name via logging.getLogger)

    Raises:
        ConfigurationError: If file logging setup fails

    Example:
        >>> logger = setup_logging(
        ...     name="my_unicorn.install",
        ...     console_level="INFO",
        ...     file_level="DEBUG"
        ... )
        >>> logger.info("Starting installation for %s", app_name)

    Note:
        - Root logger initialized once, child loggers created on-demand
        - Python's logging.getLogger handles logger singleton behavior
        - QueueHandler prevents blocking on I/O in async contexts

    See Also:
        - get_logger(): Recommended convenience wrapper
        - update_logger_from_config(): Apply config file settings

    """
    with _state.lock:
        # Initialize root logger if not already done
        if not _state.root_initialized:
            # Load default configuration if not provided
            if console_level is None or file_level is None or log_file is None:
                cfg_console, cfg_file, cfg_path = _load_log_settings()
                console_level = console_level or cfg_console
                file_level = file_level or cfg_file
                log_file = log_file or cfg_path

            # Set up root logger with QueueListener
            _setup_root_logger(
                console_level, file_level, log_file, enable_file_logging
            )

    # Return the requested logger (let logging.getLogger handle it)
    # Python's logging automatically handles parent-child relationships
    return logging.getLogger(name)


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

    Stops QueueListener, removes all handlers, closes file handles,
    and resets all state flags. This ensures a clean slate for test
    isolation.

    Thread Safety:
        Uses _state.lock to safely clear state in multi-threaded
        environments.

    Warning:
        This function is intended for testing only. Do not call in
        production code as it will disrupt all active logging.

    Side Effects:
        - Stops QueueListener thread
        - Closes all file handlers (flushes pending logs)
        - Removes all handlers from my_unicorn loggers
        - Resets root_initialized and config_applied flags
        - Removes test loggers from logging.Logger.manager.loggerDict

    Example:
        >>> # In test teardown
        >>> from my_unicorn.logger import clear_logger_state
        >>> clear_logger_state()
        >>> # Next test starts with fresh logger state

    Note:
        Only clears loggers in the "my_unicorn" and "test-" namespaces
        to avoid interfering with other libraries.

    """
    with _state.lock:
        # Flush all pending logs before stopping
        if _state.queue_listener is not None:
            flush_all_handlers()

        # Stop QueueListener
        if _state.queue_listener is not None:
            _state.queue_listener.stop()
            _state.queue_listener = None

        # Clear queue
        _state.log_queue = None

        # Reset state flags
        _state.root_initialized = False
        _state.config_applied = False

        # Clean up logging module's logger dict
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if (
                logger_name.startswith(("test-", "my_unicorn"))
                or logger_name == "my_unicorn"
            ):
                log_instance = logging.getLogger(logger_name)
                for handler in log_instance.handlers[:]:
                    handler.close()
                    log_instance.removeHandler(handler)
                if logger_name in logging.Logger.manager.loggerDict:
                    del logging.Logger.manager.loggerDict[logger_name]
