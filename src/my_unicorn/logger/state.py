"""Logger state management module.

This module provides the global logger state singleton used throughout
the my-unicorn application. The singleton pattern is critical for ensuring
a single root logger instance across the entire application.

CRITICAL: This module uses a module-level singleton pattern.
DO NOT modify without understanding threading and singleton implications.
"""

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import queue
    from logging.handlers import QueueListener


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


# CRITICAL: Global logger state singleton
# This is the single source of truth for logger state across the application
_state = _LoggerState()


def get_state() -> _LoggerState:
    """Get the global logger state singleton.

    Returns:
        The global logger state instance

    """
    return _state
