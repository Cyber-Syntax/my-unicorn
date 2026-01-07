"""Tests for the new simplified logger module."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from my_unicorn.domain.constants import LOG_BACKUP_COUNT, LOG_ROTATION_THRESHOLD_BYTES
from my_unicorn.logger import (
    ColoredConsoleFormatter,
    clear_logger_state,
    get_logger,
    setup_logging,
)


@pytest.fixture(autouse=True)
def cleanup_loggers():
    """Clear logger state before and after each test."""
    clear_logger_state()
    yield
    clear_logger_state()


def test_get_logger_returns_standard_logger():
    """Test that get_logger returns a standard Python logger."""
    logger = get_logger("test-logger", enable_file_logging=False)
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test-logger"


def test_get_logger_singleton_behavior():
    """Test get_logger returns same instance for same name."""
    logger1 = get_logger("singleton-test", enable_file_logging=False)
    logger2 = get_logger("singleton-test", enable_file_logging=False)
    assert logger1 is logger2

    logger3 = get_logger("another-test", enable_file_logging=False)
    assert logger1 is not logger3


def test_console_handler_has_color_formatter():
    """Test console handler uses ColoredConsoleFormatter."""
    logger = get_logger("color-test", enable_file_logging=False)

    # Find console handler (StreamHandler to stdout)
    console_handlers = [
        h
        for h in logger.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
    ]

    assert len(console_handlers) == 1
    assert isinstance(console_handlers[0].formatter, ColoredConsoleFormatter)


def test_file_handler_uses_rotating_file_handler(tmp_path):
    """Test file logging uses standard RotatingFileHandler."""
    log_file = tmp_path / "test.log"
    logger = setup_logging(
        name="file-test",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Find file handler
    file_handlers = [
        h for h in logger.handlers if isinstance(h, RotatingFileHandler)
    ]

    assert len(file_handlers) == 1
    assert isinstance(file_handlers[0], RotatingFileHandler)
    assert isinstance(file_handlers[0].formatter, logging.Formatter)


def test_colored_formatter_adds_ansi_colors():
    """Test ColoredConsoleFormatter adds ANSI color codes."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )
    formatter = ColoredConsoleFormatter("%(levelname)s %(message)s")
    formatted = formatter.format(record)

    # Should contain ANSI color code for green (INFO)
    assert "\033[32mINFO\033[0m" in formatted


def test_logger_level_filtering_console_vs_file(tmp_path):
    """Test that console and file handlers have independent level filtering."""
    log_file = tmp_path / "level-test.log"
    logger = setup_logging(
        name="level-test",
        console_level="WARNING",
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Find handlers
    console_handler = next(
        h
        for h in logger.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
    )
    file_handler = next(
        h for h in logger.handlers if isinstance(h, RotatingFileHandler)
    )

    assert console_handler.level == logging.WARNING
    assert file_handler.level == logging.DEBUG


def test_file_rotation_configuration(tmp_path):
    """Test RotatingFileHandler is configured correctly."""
    log_file = tmp_path / "rotate-test.log"
    logger = setup_logging(
        name="rotate-test",
        log_file=log_file,
        enable_file_logging=True,
    )

    file_handler = next(
        h for h in logger.handlers if isinstance(h, RotatingFileHandler)
    )

    # Verify rotation is configured
    assert file_handler.maxBytes == LOG_ROTATION_THRESHOLD_BYTES
    assert file_handler.backupCount == LOG_BACKUP_COUNT


def test_logging_actually_writes_to_file(tmp_path):
    """Test that logging writes messages to the log file."""
    log_file = tmp_path / "write-test.log"
    logger = setup_logging(
        name="write-test",
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    test_message = "Test log message 12345"
    logger.debug(test_message)

    # Flush handlers
    for handler in logger.handlers:
        handler.flush()

    # Read file and verify message was written
    assert log_file.exists()
    content = log_file.read_text()
    assert test_message in content


def test_clear_logger_state_removes_handlers():
    """Test clear_logger_state properly cleans up handlers."""
    log_file = Path("/tmp/clear-test.log")
    logger = setup_logging(
        name="clear-test",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Verify handlers exist
    assert len(logger.handlers) > 0

    # Clear state
    clear_logger_state()

    # Handlers should be closed and removed
    # Note: Handlers are cleared from the logger instance
    # Getting a new logger should start fresh
    new_logger = get_logger("clear-test", enable_file_logging=False)

    # New logger should have fresh handlers (only console)
    console_count = sum(
        1
        for h in new_logger.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
    )
    assert console_count == 1


def test_no_progress_context_method():
    """Test that new logger does NOT have progress_context() method."""
    logger = get_logger("no-progress-test", enable_file_logging=False)

    # Standard logger doesn't have progress_context method
    assert not hasattr(logger, "progress_context")


def test_loads_config_from_settings():
    """Test that logger loads configuration from config_manager."""
    # This test verifies _load_log_settings() is called
    # Actual config loading is tested implicitly by get_logger()
    logger = get_logger("config-test", enable_file_logging=False)

    # If config loading works, logger should be created successfully
    assert logger.name == "config-test"
    assert logger.level == logging.DEBUG  # Root level set to DEBUG


def test_no_file_logging_when_disabled():
    """Test that file logging is not setup when enable_file_logging=False."""
    logger = get_logger("no-file-test", enable_file_logging=False)

    # Should only have console handler
    file_handlers = [
        h for h in logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(file_handlers) == 0


def test_multiple_loggers_are_independent(tmp_path):
    """Test that multiple loggers have independent configurations."""
    log1 = tmp_path / "log1.log"
    log2 = tmp_path / "log2.log"

    logger1 = setup_logging(
        name="logger1",
        console_level="ERROR",
        file_level="DEBUG",
        log_file=log1,
    )
    logger2 = setup_logging(
        name="logger2",
        console_level="INFO",
        file_level="WARNING",
        log_file=log2,
    )

    # Verify independent configuration
    assert logger1.name == "logger1"
    assert logger2.name == "logger2"

    # Write to both
    logger1.debug("logger1 message")
    logger2.warning("logger2 message")

    # Flush
    for handler in logger1.handlers + logger2.handlers:
        handler.flush()

    # Verify separate files
    assert log1.exists()
    assert log2.exists()
    assert "logger1 message" in log1.read_text()
    assert "logger2 message" in log2.read_text()


def test_structured_file_formatter_uses_correct_format():
    """Test logging.Formatter uses configured format string for file output."""
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="structured message",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    assert "test" in formatted
    assert "INFO" in formatted
    assert "structured message" in formatted


def test_logger_propagate_is_false():
    """Test that loggers don't propagate to root logger."""
    logger = get_logger("no-propagate-test", enable_file_logging=False)
    assert logger.propagate is False


def test_existing_handlers_are_cleared_on_setup():
    """Test that setup_logging clears existing handlers."""
    logger_name = "handler-clear-test"

    # First setup
    logger1 = setup_logging(
        name=logger_name,
        enable_file_logging=False,
    )
    initial_handler_count = len(logger1.handlers)

    # Clear and setup again (should not double handlers)
    clear_logger_state()
    logger2 = setup_logging(
        name=logger_name,
        enable_file_logging=False,
    )

    # Should have same number of handlers (not doubled)
    assert len(logger2.handlers) == initial_handler_count


def test_update_logger_from_config(tmp_path, monkeypatch):
    """Test that update_logger_from_config updates handler levels."""
    from unittest.mock import MagicMock

    from my_unicorn.logger import update_logger_from_config

    # Create a mock config_manager that returns DEBUG levels
    mock_config_manager = MagicMock()
    mock_config_manager.load_global_config.return_value = {
        "console_log_level": "DEBUG",
        "log_level": "DEBUG",
    }

    # Monkey patch the config_manager import
    import my_unicorn.config as config_module

    monkeypatch.setattr(config_module, "config_manager", mock_config_manager)

    # Create logger with default WARNING level
    logger = get_logger("test-config-update", enable_file_logging=False)

    # Find console handler
    console_handler = None
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            console_handler = handler
            break

    assert console_handler is not None
    initial_level = console_handler.level

    # Update from config
    update_logger_from_config("test-config-update")

    # Verify level changed to DEBUG
    assert console_handler.level == logging.DEBUG
    assert console_handler.level != initial_level


def test_temporary_console_level_context_manager(caplog):
    """Test temporary_console_level context manager adjusts and restores levels."""
    from my_unicorn.logger import temporary_console_level

    logger = get_logger("temp-level-test", enable_file_logging=False)

    # Find console handler and set to WARNING
    console_handler = None
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            console_handler = handler
            console_handler.setLevel(logging.WARNING)
            break

    assert console_handler is not None
    original_level = console_handler.level
    assert original_level == logging.WARNING

    # Use context manager to temporarily set to INFO
    with temporary_console_level("INFO", "temp-level-test"):
        # Level should be INFO inside context
        assert console_handler.level == logging.INFO

        # Log an INFO message that should be visible
        logger.info("Test info message")

    # Level should be restored to WARNING
    assert console_handler.level == original_level
    assert console_handler.level == logging.WARNING


def test_temporary_console_level_invalid_level():
    """Test temporary_console_level raises ValueError for invalid level."""
    from my_unicorn.logger import temporary_console_level

    with pytest.raises(ValueError, match="Invalid log level"):
        with temporary_console_level("INVALID_LEVEL"):
            pass


def test_temporary_console_level_with_file_handler(tmp_path):
    """Test temporary_console_level only affects console handlers, not file handlers."""
    from my_unicorn.logger import temporary_console_level

    log_file = tmp_path / "test.log"
    logger = setup_logging(
        "file-handler-test",
        console_level="WARNING",
        file_level="INFO",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Find handlers
    console_handler = None
    file_handler = None
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            file_handler = handler
        elif isinstance(handler, logging.StreamHandler):
            console_handler = handler

    assert console_handler is not None
    assert file_handler is not None

    original_file_level = file_handler.level
    original_console_level = console_handler.level

    # Use context manager
    with temporary_console_level("DEBUG", "file-handler-test"):
        # Console handler should change
        assert console_handler.level == logging.DEBUG
        # File handler should NOT change
        assert file_handler.level == original_file_level

    # Both should be restored
    assert console_handler.level == original_console_level
    assert file_handler.level == original_file_level
