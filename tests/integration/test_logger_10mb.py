"""Integration tests for logger with 10MB log file samples.

This module tests the complete logging flow including rotation with
realistic large log files to ensure performance and correctness.
"""

import logging
import time
import uuid
from collections.abc import Callable, Generator
from pathlib import Path

import pytest

from my_unicorn.domain.constants import (
    LOG_BACKUP_COUNT,
    LOG_ROTATION_THRESHOLD_BYTES,
)
from my_unicorn.logger import (
    _state,
    clear_logger_state,
    flush_all_handlers,
    setup_logging,
)

# Constants for test thresholds
SMALL_LOG_SIZE_THRESHOLD = 1000  # bytes
EXPECTED_ROTATION_CYCLES = 3
MAX_LOG_ENTRY_TIME_MS = 5.0  # milliseconds
MEDIUM_LOG_SIZE_THRESHOLD = 10000  # bytes (10KB)


@pytest.mark.slow
def wait_until(
    predicate: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.05,
) -> bool:
    """Wait until predicate is true or timeout.

    Args:
        predicate: Function that returns bool.
        timeout: Max time to wait in seconds.
        interval: Time between checks in seconds.

    Returns:
        True if predicate became true, False if timed out.
    """
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.fixture(autouse=True)
def clean_logger_state() -> Generator[None, None, None]:
    """Ensure logger state is clean before and after each test."""
    clear_logger_state()
    yield
    clear_logger_state()


@pytest.fixture
def logger_name() -> str:
    """Provide unique logger name for each test."""
    return f"test-10mb-{uuid.uuid4().hex}"


def backup_index(path: Path) -> int:
    """Extract backup index from path suffix.

    Args:
        path: Backup file path like my-unicorn.log.1

    Returns:
        The index number.
    """
    return int(path.suffix.lstrip("."))


@pytest.mark.slow
def write_until_rotation(
    logger: logging.Logger,
    approx_entry_size: int = 60,
) -> None:
    """Write log entries until rotation threshold is exceeded.

    Args:
        logger: Logger instance to write to.
        approx_entry_size: Approximate size of each log entry in bytes.
    """
    entry_count = (LOG_ROTATION_THRESHOLD_BYTES // approx_entry_size) + 1000
    for i in range(entry_count):
        logger.info("Entry %s padding", i)


@pytest.mark.slow
def create_10mb_log_file(log_file: Path) -> None:
    """Create a realistic 10MB log file.

    Args:
        log_file: Path where to create the log file

    """
    # Create realistic log entries
    entry_template = (
        "2024-01-15 14:30:25,123 - my-unicorn - INFO - "
        "install_service:245 - Installing AppImage: "
        "appflowy version 0.4.2 from GitHub repository "
        "AppFlowy-IO/AppFlowy | Hash verification: SHA256 | "
        "Download size: 125.4 MB | Installation path: "
        "/home/user/.local/share/my-unicorn/apps/appflowy\n"
    )

    # Each entry is ~250 bytes, need ~42,000 entries for 10MB
    target_size = 10 * 1024 * 1024  # 10 MB
    entry_size = len(entry_template.encode("utf-8"))
    num_entries = (target_size // entry_size) + 1

    with log_file.open("w", encoding="utf-8") as f:
        for i in range(num_entries):
            # Vary the entries slightly for realism
            entry = entry_template.replace("0.4.2", f"0.4.{i % 100}")
            f.write(entry)


@pytest.mark.slow
def test_10mb_log_rotation(tmp_path: Path, logger_name: str) -> None:
    """Test rotation with realistic 10MB log file."""
    log_file = tmp_path / "my-unicorn.log"

    # Create 10MB log file
    create_10mb_log_file(log_file)

    # Verify file is at least 10MB
    file_size = log_file.stat().st_size
    assert file_size >= LOG_ROTATION_THRESHOLD_BYTES

    # Setup file logging - rotation happens automatically if file is large
    _ = setup_logging(
        name=logger_name,
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Original file should exist as new file
    assert log_file.exists()

    # Should have at least one backup (RotatingFileHandler creates .log.1
    # format)
    backups = list(tmp_path.glob("my-unicorn.log.*"))
    assert len(backups) >= 1

    # Backup should be the 10MB file
    backup = backups[0]
    backup_size = backup.stat().st_size
    assert backup_size >= LOG_ROTATION_THRESHOLD_BYTES

    # New log file should be small/empty
    new_size = log_file.stat().st_size
    assert new_size < SMALL_LOG_SIZE_THRESHOLD


@pytest.mark.slow
def test_multiple_10mb_rotations(tmp_path: Path, logger_name: str) -> None:
    """Test multiple rotations with 10MB files."""
    log_file = tmp_path / "my-unicorn.log"

    # Setup logger once - use "my_unicorn" as root name
    # Use "my_unicorn.test" to ensure proper hierarchy
    test_logger_name = f"my_unicorn.{logger_name}"
    logger_instance = setup_logging(
        name=test_logger_name,
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Create multiple rotation cycles by writing enough data
    for cycle in range(EXPECTED_ROTATION_CYCLES):
        write_until_rotation(logger_instance)

        # Flush QueueListener handlers
        if _state.queue_listener:
            for handler in _state.queue_listener.handlers:
                handler.flush()

        # Wait for rotation to complete
        assert wait_until(
            lambda c=cycle: (
                len(list(tmp_path.glob("my-unicorn.log.*"))) >= c + 1
            ),
            timeout=10.0,
        ), f"Rotation {cycle + 1} did not complete in time"

    # Should have at least 3 backups (one per cycle)
    # RotatingFileHandler creates backups with .1, .2, .3 suffixes
    backups = sorted(
        tmp_path.glob("my-unicorn.log.*"),
        key=backup_index,
    )
    assert len(backups) >= EXPECTED_ROTATION_CYCLES

    # Each backup should be approximately 10MB (within 1% tolerance)
    # RotatingFileHandler rotates when exceeding threshold, not at exact size
    for backup in backups[:EXPECTED_ROTATION_CYCLES]:
        size = backup.stat().st_size
        assert size >= LOG_ROTATION_THRESHOLD_BYTES * 0.99  # 99% of threshold


@pytest.mark.slow
def test_backup_limit_with_10mb_files(
    tmp_path: Path, logger_name: str
) -> None:
    """Test backup limit enforcement with large files."""
    log_file = tmp_path / "my-unicorn.log"

    # Setup logger once - use proper hierarchy
    test_logger_name = f"my_unicorn.{logger_name}"
    logger_instance = setup_logging(
        name=test_logger_name,
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Create more rotations than backup limit by writing enough data
    num_cycles = LOG_BACKUP_COUNT + 3

    for cycle in range(num_cycles):
        write_until_rotation(logger_instance)

        # Flush QueueListener handlers to ensure rotation
        if _state.queue_listener:
            for handler in _state.queue_listener.handlers:
                handler.flush()

        # Wait for rotation to complete
        assert wait_until(
            lambda c=cycle: (
                len(list(tmp_path.glob("my-unicorn.log.*")))
                >= min(c + 1, LOG_BACKUP_COUNT)
            ),
            timeout=10.0,
        ), f"Rotation {cycle + 1} did not complete in time"

    # Final wait for all logs to be written
    if _state.queue_listener:
        for handler in _state.queue_listener.handlers:
            handler.flush()

    # Should have at least LOG_BACKUP_COUNT backups
    # RotatingFileHandler creates backups with .1, .2, .3, .4, .5 suffixes
    backups = sorted(
        tmp_path.glob("my-unicorn.log.*"),
        key=backup_index,
    )
    assert len(backups) >= LOG_BACKUP_COUNT

    # Calculate total backup size (within 1% tolerance for RotatingFileHandler
    # behavior)
    total_backup_size = sum(b.stat().st_size for b in backups)
    expected_min_size = LOG_BACKUP_COUNT * LOG_ROTATION_THRESHOLD_BYTES * 0.99
    assert total_backup_size >= expected_min_size


@pytest.mark.slow
def test_logging_performance_after_rotation(
    tmp_path: Path, logger_name: str
) -> None:
    """Test that logging performance is good after rotation."""
    log_file = tmp_path / "my-unicorn.log"

    # Create 10MB log and setup logger (rotation happens automatically)
    create_10mb_log_file(log_file)

    test_logger_name = f"my_unicorn.{logger_name}"
    logger_instance = setup_logging(
        name=test_logger_name,
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Write many log entries and measure time
    start_time = time.time()
    num_entries = 1000

    for i in range(num_entries):
        logger_instance.info("Performance test entry %s", i)

    # Flush QueueListener handlers to ensure all writes complete
    if _state.queue_listener:
        for handler in _state.queue_listener.handlers:
            handler.flush()

    elapsed = time.time() - start_time
    avg_time_ms = (elapsed / num_entries) * 1000

    # Performance should be reasonable (< 15ms per entry, allowing for CI
    # variance)
    assert avg_time_ms < MAX_LOG_ENTRY_TIME_MS * 3, (
        f"Logging too slow: {avg_time_ms:.3f}ms/entry"
    )


@pytest.mark.slow
def test_full_application_flow_with_10mb(tmp_path: Path) -> None:
    """Test complete application flow with 10MB log rotation."""
    log_file = tmp_path / "my-unicorn.log"

    # Simulate first run - create large log
    create_10mb_log_file(log_file)

    # Application startup - rotation happens automatically
    logger = setup_logging(
        name="my_unicorn",
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Verify rotation happened
    backups = list(tmp_path.glob("my-unicorn.log.*"))
    assert len(backups) >= 1

    # Simulate application operations
    logger.info("Application started")
    logger.debug("Loading configuration")
    logger.info("Installing AppImage: test-app")
    logger.warning("Rate limit approaching")
    logger.info("Installation complete")

    # Ensure all logs are processed from queue and written to file
    flush_all_handlers()

    # New log should contain recent entries
    log_content = log_file.read_text()
    assert "Application started" in log_content
    assert "Installation complete" in log_content

    # New log should be small
    new_size = log_file.stat().st_size
    assert new_size < MEDIUM_LOG_SIZE_THRESHOLD


@pytest.mark.slow
def test_rotation_preserves_encoding(tmp_path: Path, logger_name: str) -> None:
    """Test that UTF-8 encoding is preserved during rotation."""
    log_file = tmp_path / "my-unicorn.log"

    # Create 10MB log with Unicode characters
    unicode_entry = (
        "2024-01-15 14:30:25 - my-unicorn - INFO - "
        "Processing: 🦄 Unicode Test 日本語 Español Русский 中文 "
        "Emoji: 🚀 🎉 ✨ 💡 🔥 Path: /home/user/.config/my-unicorn\n"
    )

    target_size = 10 * 1024 * 1024
    entry_size = len(unicode_entry.encode("utf-8"))
    num_entries = (target_size // entry_size) + 1

    with log_file.open("w", encoding="utf-8") as f:
        for _ in range(num_entries):
            f.write(unicode_entry)

    # Verify file size
    assert log_file.stat().st_size >= LOG_ROTATION_THRESHOLD_BYTES

    # Trigger rotation (happens automatically when file is large)
    test_logger_name = f"my_unicorn.{logger_name}"
    logger_instance = setup_logging(
        name=test_logger_name,
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Write a unicode log entry to the new file
    logger_instance.info("New unicode: 🦄 Test")

    # Flush to ensure written
    flush_all_handlers()

    # Find backup
    backups = list(tmp_path.glob("my-unicorn.log.*"))
    assert len(backups) >= 1

    # Read backup with UTF-8 encoding
    backup_content = backups[0].read_text(encoding="utf-8")

    # Verify Unicode characters are preserved in backup
    assert "🦄" in backup_content
    assert "Español" in backup_content
    assert "🚀" in backup_content

    # Verify Unicode characters are preserved in new log file
    new_content = log_file.read_text(encoding="utf-8")
    assert "🦄" in new_content


@pytest.mark.slow
def test_concurrent_logger_instances_with_rotation(tmp_path: Path) -> None:
    """Test multiple logger instances with rotation."""
    log_file = tmp_path / "my-unicorn.log"

    # Create 10MB log
    create_10mb_log_file(log_file)

    # Setup parent logger with file handler (rotation happens automatically)
    _ = setup_logging(
        name="my_unicorn",  # Parent logger
        file_level="DEBUG",
        log_file=log_file,
        enable_file_logging=True,
    )

    # Get child loggers (they inherit parent's handlers via propagation)
    logger1 = logging.getLogger("my_unicorn.service1")
    logger2 = logging.getLogger("my_unicorn.service2")
    logger3 = logging.getLogger("my_unicorn.service3")

    # Write from multiple loggers (they all propagate to parent's file handler)
    logger1.debug("Debug from service1")
    logger2.info("Info from service2")
    logger3.warning("Warning from service3")

    # Flush to ensure all logs are written to disk
    flush_all_handlers()

    # Verify all messages are in the log
    log_content = log_file.read_text()
    assert "service1" in log_content
    assert "service2" in log_content
    assert "service3" in log_content

    # Should have one backup from rotation
    backups = list(tmp_path.glob("my-unicorn.log.*"))
    assert len(backups) >= 1
