import logging
from unittest.mock import patch

import pytest

from my_unicorn.logger import ColoredFormatter, MyUnicornLogger, get_logger


@pytest.fixture
def logger_name():
    return "test-logger"


@pytest.fixture
def logger_instance(logger_name):
    # Always create a fresh logger for isolation
    return MyUnicornLogger(logger_name)


def test_debug_info_warning_error_critical_methods(logger_instance):
    """Test debug/info/warning/error/critical log methods call underlying logger."""
    with (
        patch.object(logger_instance.logger, "debug") as mock_debug,
        patch.object(logger_instance.logger, "info") as mock_info,
        patch.object(logger_instance.logger, "warning") as mock_warning,
        patch.object(logger_instance.logger, "error") as mock_error,
        patch.object(logger_instance.logger, "critical") as mock_critical,
    ):
        logger_instance.debug("debug message %s", 1)
        logger_instance.info("info message %s", 2)
        logger_instance.warning("warning message %s", 3)
        logger_instance.error("error message %s", 4)
        logger_instance.critical("critical message %s", 5)

        mock_debug.assert_called_once_with("debug message %s", 1)
        mock_info.assert_called_once_with("info message %s", 2)
        mock_warning.assert_called_once_with("warning message %s", 3)
        mock_error.assert_called_once_with("error message %s", 4, exc_info=True)
        mock_critical.assert_called_once_with("critical message %s", 5)


def test_exception_method_logs_exception(logger_instance):
    """Test exception method calls logger.exception."""
    with patch.object(logger_instance.logger, "exception") as mock_exception:
        logger_instance.exception("exception occurred %s", "foo")
        mock_exception.assert_called_once_with("exception occurred %s", "foo")


def test_progress_context_defers_and_flushes_messages(logger_instance):
    """Test progress_context defers INFO/WARNING and flushes after context."""
    with (
        patch.object(logger_instance.logger, "info") as mock_info,
        patch.object(logger_instance.logger, "warning") as mock_warning,
    ):
        # INFO/WARNING inside context are deferred
        with logger_instance.progress_context():
            logger_instance.info("deferred info")
            logger_instance.warning("deferred warning")
            assert not mock_info.called
            assert not mock_warning.called
        # After context, deferred messages are flushed
        assert mock_info.call_count == 1
        assert mock_warning.call_count == 1
        mock_info.assert_called_with("deferred info")
        mock_warning.assert_called_with("deferred warning")


def test_set_and_restore_console_level(logger_instance):
    """Test set_console_level_temporarily and restore_console_level."""
    # Console handler is set up in MyUnicornLogger
    logger_instance = MyUnicornLogger("unique-console-test")
    if logger_instance._console_handler is None:
        logger_instance._setup_handlers()
    handler = logger_instance._console_handler
    assert handler.level == logging.WARNING
    logger_instance.set_console_level_temporarily("DEBUG")
    assert handler.level == logging.DEBUG
    logger_instance.restore_console_level()
    assert handler.level == logging.WARNING


def test_setup_file_logging_creates_file_handler(tmp_path, logger_name):
    """Test setup_file_logging adds file handler and sets level."""
    log_file = tmp_path / "my-unicorn.log"
    logger_instance = MyUnicornLogger(logger_name)
    logger_instance.setup_file_logging(log_file, level="DEBUG")
    # Should have a file handler with correct level
    file_handlers = [
        h
        for h in logger_instance.logger.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert file_handlers
    assert file_handlers[0].level == logging.DEBUG
    # Log file should exist after logging
    logger_instance.debug("test file log")
    logger_instance.logger.handlers[1].flush()
    assert log_file.exists()


def test_get_logger_singleton_behavior():
    """Test get_logger returns same instance for same name."""
    logger1 = get_logger("singleton-test", enable_file_logging=False)
    logger2 = get_logger("singleton-test", enable_file_logging=False)
    assert logger1 is logger2
    logger3 = get_logger("another-test", enable_file_logging=False)
    assert logger1 is not logger3


def test_colored_formatter_colors_output():
    """Test ColoredFormatter adds color codes for known levels."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )
    formatter = ColoredFormatter("%(levelname)s %(message)s")
    formatted = formatter.format(record)
    # Should contain ANSI color code for green (INFO)
    assert "\033[32mINFO\033[0m" in formatted
