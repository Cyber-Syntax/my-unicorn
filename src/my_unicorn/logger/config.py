"""Configuration loading and updating for logging system.

This module provides functions to load logger configuration from config files
and update logger settings at runtime. It handles the circular dependency
between logger and config modules by using late imports.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from my_unicorn.constants import DEFAULT_LOG_LEVEL


def load_log_settings() -> tuple[str, str, Path]:
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


def update_logger_from_config(state) -> None:
    """Update logger handler levels from global config.

    This should be called after both logger and config modules are
    initialized to apply config-based log levels. Only updates handler
    levels, never adds/removes handlers.

    Creates a local ConfigManager instance to avoid depending on the
    module-level singleton. This supports dependency injection patterns
    and prevents circular import issues.

    Args:
        state: Logger state object (from logger.state module)

    Example:
        >>> from my_unicorn.logger import update_logger_from_config
        >>> # After config is initialized
        >>> update_logger_from_config()
        >>> # All handlers now use settings from config file

    Note:
        Silently ignores any errors during config loading to prevent
        logging configuration from breaking the application startup.
        Sets state.config_applied = True on success.

    """
    try:
        # Import here to avoid circular dependency
        from my_unicorn.config import ConfigManager  # noqa: PLC0415

        # Create a local ConfigManager instance (not using singleton)
        config_mgr = ConfigManager()

        # Load configuration
        config = config_mgr.load_global_config()

        # Extract log settings from config
        console_level_str = config.get("console_log_level", "WARNING")
        file_level_str = config.get("log_level", "INFO")

        # Convert to logging level constants
        console_level = getattr(logging, console_level_str, logging.WARNING)
        file_level = getattr(logging, file_level_str, logging.INFO)

        # Update handlers in the QueueListener
        if state.queue_listener is not None:
            for handler in state.queue_listener.handlers:
                if isinstance(
                    handler, logging.StreamHandler
                ) and not isinstance(handler, RotatingFileHandler):
                    # Console handler
                    handler.setLevel(console_level)
                elif isinstance(handler, RotatingFileHandler):
                    # File handler
                    handler.setLevel(file_level)

        # Mark config as applied
        state.config_applied = True

    except (ImportError, KeyError, AttributeError):
        # Config module not fully initialized yet - use bootstrap defaults
        # This happens during initial import before config is ready
        pass
