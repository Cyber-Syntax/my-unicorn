"""Integration tests for logger with 10MB log file samples.

This module tests the complete logging flow including rotation with
realistic large log files to ensure performance and correctness.
"""

import time
from pathlib import Path

import pytest

from my_unicorn.constants import (
    LOG_BACKUP_COUNT,
    LOG_ROTATION_THRESHOLD_BYTES,
)
from my_unicorn.logger import MyUnicornLogger, clear_logger_state, get_logger

# Constants for test thresholds
SMALL_LOG_SIZE_THRESHOLD = 1000  # bytes
EXPECTED_ROTATION_CYCLES = 3
BACKUP_NAME_PARTS_COUNT = 4
MAX_LOG_ENTRY_TIME_MS = 5.0  # milliseconds
MEDIUM_LOG_SIZE_THRESHOLD = 10000  # bytes (10KB)


@pytest.fixture
def logger_name():
    """Provide unique logger name for each test."""
    return f"test-10mb-{int(time.time() * 1000000)}"


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


def test_10mb_log_rotation(tmp_path, logger_name):
    """Test rotation with realistic 10MB log file."""
    log_file = tmp_path / "my-unicorn.log"

    # Create 10MB log file
    create_10mb_log_file(log_file)

    # Verify file is at least 10MB
    file_size = log_file.stat().st_size
    assert file_size >= LOG_ROTATION_THRESHOLD_BYTES
    print(f"Created log file: {file_size / (1024 * 1024):.2f} MB")

    # Setup file logging - should trigger rotation
    clear_logger_state()
    logger_instance = MyUnicornLogger(logger_name)
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Original file should exist as new file
    assert log_file.exists()

    # Should have exactly one backup
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == 1

    # Backup should be the 10MB file
    backup = backups[0]
    backup_size = backup.stat().st_size
    assert backup_size >= LOG_ROTATION_THRESHOLD_BYTES
    print(f"Backup file created: {backup_size / (1024 * 1024):.2f} MB")

    # New log file should be small/empty
    new_size = log_file.stat().st_size
    assert new_size < SMALL_LOG_SIZE_THRESHOLD
    print(f"New log file: {new_size} bytes")


def test_multiple_10mb_rotations(tmp_path, logger_name):
    """Test multiple rotations with 10MB files."""
    log_file = tmp_path / "my-unicorn.log"

    # Create multiple rotation cycles
    for cycle in range(3):
        # Create 10MB log
        create_10mb_log_file(log_file)

        # Clear and recreate logger for each cycle
        clear_logger_state()
        logger_instance = MyUnicornLogger(f"{logger_name}-cycle{cycle}")
        logger_instance.setup_file_logging(log_file, level="DEBUG")

        # Write some new entries
        for i in range(10):
            logger_instance.info("Cycle %s: New entry %s", cycle, i)

        # Flush to ensure writes
        if logger_instance._file_handler:
            logger_instance._file_handler.flush()

    # Should have 3 backups
    backups = sorted(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == EXPECTED_ROTATION_CYCLES

    # Each backup should be approximately 10MB
    for backup in backups:
        size = backup.stat().st_size
        assert size >= LOG_ROTATION_THRESHOLD_BYTES
        print(f"Backup {backup.name}: {size / (1024 * 1024):.2f} MB")


def test_backup_limit_with_10mb_files(tmp_path, logger_name):
    """Test backup limit enforcement with large files."""
    log_file = tmp_path / "my-unicorn.log"

    # Create more rotations than backup limit
    num_cycles = LOG_BACKUP_COUNT + 3

    for cycle in range(num_cycles):
        # Create 10MB log
        create_10mb_log_file(log_file)

        # Trigger rotation
        clear_logger_state()
        logger_instance = MyUnicornLogger(f"{logger_name}-{cycle}")
        logger_instance.setup_file_logging(log_file, level="DEBUG")

        # Small delay to ensure different timestamps
        time.sleep(0.01)

    # Should have exactly LOG_BACKUP_COUNT backups
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == LOG_BACKUP_COUNT

    # Calculate total backup size
    total_backup_size = sum(b.stat().st_size for b in backups)
    expected_min_size = LOG_BACKUP_COUNT * LOG_ROTATION_THRESHOLD_BYTES
    assert total_backup_size >= expected_min_size

    print(
        f"Total backup size: {total_backup_size / (1024 * 1024):.2f} MB "
        f"({len(backups)} files)"
    )


def test_logging_performance_after_rotation(tmp_path, logger_name):
    """Test that logging performance is good after rotation."""
    log_file = tmp_path / "my-unicorn.log"

    # Create 10MB log and trigger rotation
    create_10mb_log_file(log_file)

    clear_logger_state()
    logger_instance = MyUnicornLogger(logger_name)
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Write many log entries and measure time
    start_time = time.time()
    num_entries = 1000

    for i in range(num_entries):
        logger_instance.info("Performance test entry %s", i)

    # Flush to ensure all writes complete
    if logger_instance._file_handler:
        logger_instance._file_handler.flush()

    elapsed = time.time() - start_time
    avg_time_ms = (elapsed / num_entries) * 1000

    print(f"Logged {num_entries} entries in {elapsed:.3f}s")
    print(f"Average time per entry: {avg_time_ms:.3f}ms")

    # Performance should be reasonable (< 5ms per entry)
    assert avg_time_ms < MAX_LOG_ENTRY_TIME_MS, (
        f"Logging too slow: {avg_time_ms:.3f}ms/entry"
    )


def test_full_application_flow_with_10mb(tmp_path):
    """Test complete application flow with 10MB log rotation."""
    log_file = tmp_path / "my-unicorn.log"

    # Simulate first run - create large log
    create_10mb_log_file(log_file)

    # Application startup - should rotate
    clear_logger_state()
    logger = get_logger("my-unicorn", enable_file_logging=False)
    logger.setup_file_logging(log_file, "DEBUG")

    # Verify rotation happened
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == 1

    # Simulate application operations
    logger.info("Application started")
    logger.debug("Loading configuration")
    logger.info("Installing AppImage: test-app")
    logger.warning("Rate limit approaching")
    logger.info("Installation complete")

    # Flush logs
    if logger._file_handler:
        logger._file_handler.flush()

    # New log should contain recent entries
    log_content = log_file.read_text()
    assert "Application started" in log_content
    assert "Installation complete" in log_content

    # New log should be small
    new_size = log_file.stat().st_size
    assert new_size < MEDIUM_LOG_SIZE_THRESHOLD


def test_rotation_preserves_encoding(tmp_path, logger_name):
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

    # Trigger rotation
    clear_logger_state()
    logger_instance = MyUnicornLogger(logger_name)
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Find backup
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == 1

    # Read backup with UTF-8 encoding
    backup_content = backups[0].read_text(encoding="utf-8")

    # Verify Unicode characters are preserved
    assert "🦄" in backup_content
    assert "日本語" in backup_content
    assert "Español" in backup_content
    assert "Русский" in backup_content
    assert "中文" in backup_content
    assert "🚀" in backup_content


def test_concurrent_logger_instances_with_rotation(tmp_path):
    """Test multiple logger instances with rotation."""
    log_file = tmp_path / "my-unicorn.log"

    # Create 10MB log
    create_10mb_log_file(log_file)

    clear_logger_state()

    # Create multiple loggers
    logger1 = get_logger("my-unicorn.service1", enable_file_logging=False)
    logger2 = get_logger("my-unicorn.service2", enable_file_logging=False)
    logger3 = get_logger("my-unicorn.service3", enable_file_logging=False)

    # Setup file logging for all (rotation should happen once)
    logger1.setup_file_logging(log_file, "DEBUG")
    logger2.setup_file_logging(log_file, "INFO")
    logger3.setup_file_logging(log_file, "WARNING")

    # Write from multiple loggers
    logger1.debug("Debug from service1")
    logger2.info("Info from service2")
    logger3.warning("Warning from service3")

    # Flush all handlers
    for logger in [logger1, logger2, logger3]:
        if logger._file_handler:
            logger._file_handler.flush()

    # Verify all messages are in the log
    log_content = log_file.read_text()
    assert "service1" in log_content
    assert "service2" in log_content
    assert "service3" in log_content

    # Should have one backup from rotation
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) >= 1
