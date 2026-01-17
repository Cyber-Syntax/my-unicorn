"""Tests for the async-safe logger module with QueueHandler architecture."""

import logging
from logging.handlers import QueueHandler, RotatingFileHandler
from pathlib import Path

import pytest

from my_unicorn.constants import LOG_BACKUP_COUNT, LOG_ROTATION_THRESHOLD_BYTES
from my_unicorn.logger import (
    ColoredConsoleFormatter,
    _state,
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
    """Test console handler uses HybridConsoleFormatter via QueueListener."""
    # Get root logger to ensure initialization
    _ = get_logger("my_unicorn", enable_file_logging=False)

    # Console handler should be in QueueListener
    assert _state.queue_listener is not None
    console_handlers = [
        h
        for h in _state.queue_listener.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
    ]

    assert len(console_handlers) == 1
    # Updated to HybridConsoleFormatter which provides simple format for INFO
    from my_unicorn.logger import HybridConsoleFormatter

    assert isinstance(console_handlers[0].formatter, HybridConsoleFormatter)


def test_child_logger_propagates_to_root():
    """Test child loggers propagate to root logger with QueueHandler."""
    # Get root logger
    root = get_logger("my_unicorn", enable_file_logging=False)

    # Get child logger
    child = get_logger("my_unicorn.test_child", enable_file_logging=False)

    # Root should have QueueHandler
    root_queue_handlers = [
        h for h in root.handlers if isinstance(h, QueueHandler)
    ]
    assert len(root_queue_handlers) == 1

    # Child should have no handlers (propagates to root)
    assert len(child.handlers) == 0

    # Child should propagate
    assert child.propagate is True


def test_file_handler_uses_rotating_file_handler(tmp_path):
    """Test file logging uses RotatingFileHandler via QueueListener."""
    log_file = tmp_path / "test.log"
    logger = setup_logging(
        name="my_unicorn",  # Use root logger
        log_file=log_file,
        enable_file_logging=True,
    )

    # Root logger should have QueueHandler
    queue_handlers = [
        h for h in logger.handlers if isinstance(h, QueueHandler)
    ]
    assert len(queue_handlers) == 1

    # File handler should be in QueueListener
    assert _state.queue_listener is not None
    file_handlers = [
        h
        for h in _state.queue_listener.handlers
        if isinstance(h, RotatingFileHandler)
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
    """Test console and file handlers have independent level filtering."""
    log_file = tmp_path / "level-test.log"
    logger = setup_logging(
        name="my_unicorn",  # Use root logger
        console_level="WARNING",
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Root logger should have QueueHandler
    assert any(isinstance(h, QueueHandler) for h in logger.handlers)

    # Find handlers in QueueListener
    assert _state.queue_listener is not None
    console_handler = next(
        h
        for h in _state.queue_listener.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
    )
    file_handler = next(
        h
        for h in _state.queue_listener.handlers
        if isinstance(h, RotatingFileHandler)
    )

    assert console_handler.level == logging.WARNING
    assert file_handler.level == logging.DEBUG


def test_file_rotation_configuration(tmp_path):
    """Test RotatingFileHandler is configured correctly via QueueListener."""
    log_file = tmp_path / "rotate-test.log"
    logger = setup_logging(
        name="my_unicorn",  # Use root logger
        log_file=log_file,
        enable_file_logging=True,
    )

    # Get file handler from QueueListener
    assert _state.queue_listener is not None
    file_handler = next(
        h
        for h in _state.queue_listener.handlers
        if isinstance(h, RotatingFileHandler)
    )

    # Verify rotation is configured
    assert file_handler.maxBytes == LOG_ROTATION_THRESHOLD_BYTES
    assert file_handler.backupCount == LOG_BACKUP_COUNT


def test_logging_actually_writes_to_file(tmp_path):
    """Test that logging writes messages to file via QueueListener."""
    log_file = tmp_path / "write-test.log"
    logger = setup_logging(
        name="my_unicorn",  # Use root logger
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    test_message = "Test log message 12345"
    logger.debug(test_message)

    # Flush QueueListener handlers
    if _state.queue_listener is not None:
        for handler in _state.queue_listener.handlers:
            handler.flush()

    # Read file and verify message was written
    assert log_file.exists()
    content = log_file.read_text()
    assert test_message in content


def test_clear_logger_state_removes_handlers():
    """Test clear_logger_state properly cleans up QueueListener."""
    log_file = Path("/tmp/clear-test.log")
    logger = setup_logging(
        name="my_unicorn",  # Use root logger
        log_file=log_file,
        enable_file_logging=True,
    )

    # Verify QueueHandler exists on root logger
    assert any(isinstance(h, QueueHandler) for h in logger.handlers)
    # Verify QueueListener is running
    assert _state.queue_listener is not None

    # Clear state
    clear_logger_state()

    # QueueListener should be stopped
    assert _state.queue_listener is None
    assert _state.log_queue is None
    assert _state.root_initialized is False

    # Getting a new logger should start fresh
    new_logger = get_logger("my_unicorn", enable_file_logging=False)

    # New root logger should have QueueHandler
    queue_count = sum(
        1 for h in new_logger.handlers if isinstance(h, QueueHandler)
    )
    assert queue_count == 1


def test_no_progress_context_method():
    """Test that new logger does NOT have progress_context() method."""
    logger = get_logger("no-progress-test", enable_file_logging=False)

    # Standard logger doesn't have progress_context method
    assert not hasattr(logger, "progress_context")


def test_loads_config_from_settings():
    """Test that logger loads configuration from config_manager."""
    # This test verifies _load_log_settings() is called
    # Actual config loading is tested implicitly by get_logger()

    # Get root logger
    logger = get_logger("my_unicorn", enable_file_logging=False)

    # Root logger level should be DEBUG (captures all)
    assert logger.level == logging.DEBUG

    # If config loading works, logger should be created successfully
    assert logger.name == "my_unicorn"


def test_no_file_logging_when_disabled():
    """Test that file logging is not setup when enable_file_logging=False."""
    logger = get_logger("no-file-test", enable_file_logging=False)

    # Should only have console handler
    file_handlers = [
        h for h in logger.handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(file_handlers) == 0


def test_multiple_loggers_are_independent(tmp_path):
    """Test that multiple loggers share same QueueListener in new architecture."""
    # In new architecture, all loggers share the root logger's QueueListener
    # This test verifies that child loggers still work correctly

    # Get root logger
    root = get_logger("my_unicorn", enable_file_logging=True)

    # Get child loggers
    logger1 = get_logger("my_unicorn.module1")
    logger2 = get_logger("my_unicorn.module2")

    # Verify hierarchy
    assert logger1.name == "my_unicorn.module1"
    assert logger2.name == "my_unicorn.module2"

    # Child loggers should propagate
    assert logger1.propagate is True
    assert logger2.propagate is True

    # Root has QueueHandler, children have no handlers (propagate)
    assert len(root.handlers) > 0
    assert len(logger1.handlers) == 0
    assert len(logger2.handlers) == 0


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


def test_logger_propagate_behavior():
    """Test logger propagation behavior in new architecture."""
    # Root logger doesn't propagate
    root_logger = get_logger("my_unicorn", enable_file_logging=False)
    assert root_logger.propagate is False

    # Child loggers DO propagate to root
    child_logger = get_logger("my_unicorn.child", enable_file_logging=False)
    assert child_logger.propagate is True


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


def test_update_logger_from_config(monkeypatch):
    """Test that update_logger_from_config updates handler levels."""
    from unittest.mock import MagicMock

    from my_unicorn.logger import update_logger_from_config

    # Setup root logger first
    _ = get_logger("my_unicorn", enable_file_logging=True)

    # Create a mock config_manager that returns DEBUG levels
    mock_config_manager = MagicMock()
    mock_config_manager.load_global_config.return_value = {
        "console_log_level": "ERROR",
        "log_level": "WARNING",
    }

    # Monkey patch the config_manager import
    import my_unicorn.config as config_module

    monkeypatch.setattr(config_module, "config_manager", mock_config_manager)

    # Update from config
    update_logger_from_config()

    # Verify handlers in QueueListener were updated
    assert _state.queue_listener is not None
    console_handler = next(
        h
        for h in _state.queue_listener.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, RotatingFileHandler)
    )
    file_handler = next(
        h
        for h in _state.queue_listener.handlers
        if isinstance(h, RotatingFileHandler)
    )

    assert console_handler.level == logging.ERROR
    assert file_handler.level == logging.WARNING
