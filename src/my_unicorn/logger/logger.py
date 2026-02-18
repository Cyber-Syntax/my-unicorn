"""Main logger module providing public API functions.

This module contains the core public API for the my-unicorn logging system:
- setup_logging(): Configure logging with async-safe QueueHandler architecture
- get_logger(): Get or create logger instance with singleton pattern
- flush_all_handlers(): Ensure all pending log records are written to disk
- clear_logger_state(): Clear global logger state for testing

These functions maintain the singleton logger pattern and ensure proper
initialization and cleanup of the logging system.
"""

import atexit
import contextlib
import logging
import time
from pathlib import Path

from my_unicorn.logger.config import load_log_settings
from my_unicorn.logger.handlers import setup_root_logger
from my_unicorn.logger.state import get_state


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
        reads state.queue_listener and calls thread-safe methods.

    Example:
        >>> logger.info("Important message")
        >>> flush_all_handlers()  # Ensure message is on disk
        >>> # Now safe to read log file

    Note:
        This is particularly important when using QueueListener because
        records may be dequeued but not yet written to disk.

    """
    state = get_state()
    if state.queue_listener is not None and state.log_queue is not None:
        # Wait for queue to be empty (all records dequeued)
        # QueueListener doesn't use task_done(), so poll the queue
        timeout = 5.0  # Maximum wait time
        start_time = time.time()
        while not state.log_queue.empty():
            if time.time() - start_time > timeout:
                break
            time.sleep(0.01)  # Small sleep to avoid busy-waiting

        # Give queue listener thread time to process final records
        time.sleep(0.1)

        # Flush all handlers to ensure writes complete
        for handler in state.queue_listener.handlers:
            with contextlib.suppress(OSError, ValueError):
                # Ignore flush errors (handler closed/unavailable)
                handler.flush()


def _cleanup_logging() -> None:
    """Clean up QueueListener on application exit.

    Registered with atexit to ensure proper shutdown.
    """
    state = get_state()
    if state.queue_listener is not None:
        flush_all_handlers()
        state.queue_listener.stop()
        state.queue_listener = None


# Register cleanup handler
atexit.register(_cleanup_logging)


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
        Uses state.lock to ensure thread-safe root logger initialization.
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
    state = get_state()
    with state.lock:
        # Initialize root logger if not already done
        if not state.root_initialized:
            # Load default configuration if not provided
            if console_level is None or file_level is None or log_file is None:
                cfg_console, cfg_file, cfg_path = load_log_settings()
                console_level = console_level or cfg_console
                file_level = file_level or cfg_file
                log_file = log_file or cfg_path

            # Set up root logger with QueueListener
            setup_root_logger(
                state,
                console_level,
                file_level,
                log_file,
                enable_file_logging,
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
        Uses state.lock to safely clear state in multi-threaded
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
    state = get_state()
    with state.lock:
        # Flush all pending logs before stopping
        if state.queue_listener is not None:
            flush_all_handlers()

        # Stop QueueListener
        if state.queue_listener is not None:
            state.queue_listener.stop()
            state.queue_listener = None

        # Clear queue
        state.log_queue = None

        # Reset state flags
        state.root_initialized = False
        state.config_applied = False

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
