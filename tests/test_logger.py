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
        patch.object(logger_instance.logger, "isEnabledFor", return_value=True),
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
        mock_error.assert_called_once_with("error message %s", 4, exc_info=False)
        mock_critical.assert_called_once_with("critical message %s", 5)


def test_exception_method_logs_exception(logger_instance):
    """Test exception method calls logger.exception."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=True),
        patch.object(logger_instance.logger, "exception") as mock_exception,
    ):
        logger_instance.exception("exception occurred %s", "foo")
        mock_exception.assert_called_once_with("exception occurred %s", "foo")


def test_progress_context_defers_and_flushes_messages(logger_instance):
    """Test progress_context defers INFO/WARNING and flushes after context."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=True),
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


def test_level_checking_optimization_debug_disabled(logger_instance):
    """Test that debug method doesn't call logger when DEBUG level is disabled."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=False),
        patch.object(logger_instance.logger, "debug") as mock_debug,
    ):
        logger_instance.debug("debug message")
        mock_debug.assert_not_called()


def test_level_checking_optimization_info_disabled(logger_instance):
    """Test that info method doesn't call logger when INFO level is disabled."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=False),
        patch.object(logger_instance.logger, "info") as mock_info,
    ):
        logger_instance.info("info message")
        mock_info.assert_not_called()


def test_level_checking_optimization_warning_disabled(logger_instance):
    """Test that warning method doesn't call logger when WARNING level is disabled."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=False),
        patch.object(logger_instance.logger, "warning") as mock_warning,
    ):
        logger_instance.warning("warning message")
        mock_warning.assert_not_called()


def test_level_checking_optimization_error_disabled(logger_instance):
    """Test that error method doesn't call logger when ERROR level is disabled."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=False),
        patch.object(logger_instance.logger, "error") as mock_error,
    ):
        logger_instance.error("error message")
        mock_error.assert_not_called()


def test_level_checking_optimization_critical_disabled(logger_instance):
    """Test that critical method doesn't call logger when CRITICAL level is disabled."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=False),
        patch.object(logger_instance.logger, "critical") as mock_critical,
    ):
        logger_instance.critical("critical message")
        mock_critical.assert_not_called()


def test_level_checking_optimization_exception_disabled(logger_instance):
    """Test that exception method doesn't call logger when ERROR level is disabled."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=False),
        patch.object(logger_instance.logger, "exception") as mock_exception,
    ):
        logger_instance.exception("exception message")
        mock_exception.assert_not_called()


def test_thread_local_progress_context_isolation():
    """Test that progress context is isolated per thread."""
    import threading

    results = []

    def thread_worker(thread_id: int) -> None:
        logger = get_logger(f"thread-{thread_id}", enable_file_logging=False)
        with (
            patch.object(logger.logger, "isEnabledFor", return_value=True),
            patch.object(logger.logger, "info") as mock_info,
        ):
            with logger.progress_context():
                logger.info(f"deferred message from thread {thread_id}")
                # Messages should be deferred, not called immediately
                results.append(("deferred", thread_id, mock_info.call_count))
            # After context, messages should be flushed
            results.append(("flushed", thread_id, mock_info.call_count))

    # Run multiple threads
    threads = []
    for i in range(3):
        thread = threading.Thread(target=thread_worker, args=(i,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # Each thread should have deferred (0 calls) then flushed (1 call)
    deferred_counts = [r[2] for r in results if r[0] == "deferred"]
    flushed_counts = [r[2] for r in results if r[0] == "flushed"]

    assert all(count == 0 for count in deferred_counts), "Messages should be deferred"
    assert all(count == 1 for count in flushed_counts), (
        "Messages should be flushed after context"
    )


def test_deferred_messages_bounded():
    """Test that deferred messages are bounded to prevent memory leaks."""
    from my_unicorn.logger import MAX_DEFERRED_MESSAGES

    logger = get_logger("bounded-test", enable_file_logging=False)
    with (
        patch.object(logger.logger, "isEnabledFor", return_value=True),
        patch.object(logger.logger, "info") as mock_info,
    ):
        with logger.progress_context():
            # Add more messages than the maximum
            for i in range(MAX_DEFERRED_MESSAGES + 100):
                logger.info(f"message {i}")

        # Only the most recent messages should be flushed
        assert mock_info.call_count == MAX_DEFERRED_MESSAGES


def test_set_level_updates_file_handler(logger_instance, tmp_path):
    """Test that set_level updates file handler level."""
    log_file = tmp_path / "test.log"
    logger_instance.setup_file_logging(log_file, level="INFO")

    # Initial file handler level should be INFO
    assert logger_instance._file_handler.level == logging.INFO

    # Change level to DEBUG
    logger_instance.set_level("DEBUG")
    assert logger_instance._file_handler.level == logging.DEBUG

    # Change level to ERROR
    logger_instance.set_level("ERROR")
    assert logger_instance._file_handler.level == logging.ERROR


def test_error_method_exc_info_parameter(logger_instance):
    """Test that error method respects exc_info parameter."""
    with (
        patch.object(logger_instance.logger, "isEnabledFor", return_value=True),
        patch.object(logger_instance.logger, "error") as mock_error,
    ):
        # Test default behavior (no exception info)
        logger_instance.error("error without exc_info")
        mock_error.assert_called_with("error without exc_info", exc_info=False)

        mock_error.reset_mock()

        # Test explicit exc_info=True
        logger_instance.error("error with exc_info", exc_info=True)
        mock_error.assert_called_with("error with exc_info", exc_info=True)

        mock_error.reset_mock()

        # Test explicit exc_info=False
        logger_instance.error("error explicit false", exc_info=False)
        mock_error.assert_called_with("error explicit false", exc_info=False)
