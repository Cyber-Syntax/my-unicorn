"""Logging formatters for console and file output.

This module provides custom formatters for the my-unicorn logging system:
- ColoredConsoleFormatter: Adds ANSI color codes to log levels
- SimpleConsoleFormatter: Shows only message content (no metadata)
- HybridConsoleFormatter: Uses simple format for INFO, structured for others

The hybrid formatter provides clean output for user-facing INFO messages
while maintaining detailed context for warnings and errors.
"""

import logging

from my_unicorn.constants import LOG_COLORS


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
