"""Logging utilities for my-unicorn AppImage installer.

This package provides structured logging with:
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

from my_unicorn.logger.config import (
    update_logger_from_config as _update_config,
)
from my_unicorn.logger.formatters import (
    ColoredConsoleFormatter,
    HybridConsoleFormatter,
    SimpleConsoleFormatter,
)
from my_unicorn.logger.handlers import ConfigurationError

# Re-export public API from main logger module
from my_unicorn.logger.logger import (
    clear_logger_state,
    flush_all_handlers,
    get_logger,
    setup_logging,
)
from my_unicorn.logger.state import _state, get_state

__all__ = [
    "ColoredConsoleFormatter",
    "ConfigurationError",
    "HybridConsoleFormatter",
    "SimpleConsoleFormatter",
    "_state",  # For testing only
    "clear_logger_state",
    "flush_all_handlers",
    "get_logger",
    "setup_logging",
    "update_logger_from_config",
]


def update_logger_from_config() -> None:
    """Update logger handler levels from global config.

    This is a convenience wrapper that calls the internal _update_config
    with the global state singleton.

    Example:
        >>> from my_unicorn.logger import update_logger_from_config
        >>> # After config is initialized
        >>> update_logger_from_config()
        >>> # All handlers now use settings from config file

    Note:
        Silently ignores any errors during config loading to prevent
        logging configuration from breaking the application startup.

    """
    _update_config(get_state())
