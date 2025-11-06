"""Tests for manual log rotation functionality in logger module."""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from my_unicorn.constants import (
    LOG_BACKUP_COUNT,
    LOG_ROTATION_THRESHOLD_BYTES,
    LOG_ROTATION_TIMESTAMP_FORMAT,
)
from my_unicorn.logger import MyUnicornLogger, clear_logger_state

# Constants for test values
EXPECTED_ROTATION_CYCLES = 3
BACKUP_NAME_PARTS_COUNT = 4


@pytest.fixture
def logger_name():
    """Provide unique logger name for each test."""
    return f"test-rotation-{id(datetime.now())}"


@pytest.fixture
def logger_instance(logger_name):
    """Provide a fresh logger instance for each test."""
    clear_logger_state()
    return MyUnicornLogger(logger_name)


def test_rotation_not_triggered_for_small_files(tmp_path, logger_instance):
    """Test that rotation is skipped when log file is below threshold."""
    log_file = tmp_path / "my-unicorn.log"
    log_file.write_text("Small log content\n")

    # File size should be well below threshold
    assert log_file.stat().st_size < LOG_ROTATION_THRESHOLD_BYTES

    # Setup file logging - should not rotate
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Original file should still exist and no backups created
    assert log_file.exists()
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == 0


def test_rotation_triggered_at_threshold(tmp_path, logger_instance):
    """Test that rotation occurs when log file exceeds threshold."""
    log_file = tmp_path / "my-unicorn.log"

    # Create a file larger than threshold
    large_content = "x" * (LOG_ROTATION_THRESHOLD_BYTES + 1000)
    log_file.write_text(large_content)

    assert log_file.stat().st_size > LOG_ROTATION_THRESHOLD_BYTES

    # Setup file logging - should trigger rotation
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Original file should exist as new empty file
    assert log_file.exists()

    # Should have exactly one backup
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == 1

    # Backup should contain the original content
    backup = backups[0]
    assert backup.read_text() == large_content


def test_backup_limit_enforced(tmp_path, logger_instance):
    """Test that old backups are removed when limit is exceeded."""
    log_file = tmp_path / "my-unicorn.log"

    # Create LOG_BACKUP_COUNT + 2 old backup files
    for i in range(LOG_BACKUP_COUNT + 2):
        backup_name = f"my-unicorn.20240101_12000{i}.1.log"
        backup_path = tmp_path / backup_name
        backup_path.write_text(f"Old backup {i}")
        # Set different modification times to ensure proper ordering
        mtime = time.time() - (100 - i)
        os.utime(backup_path, (mtime, mtime))

    # Create a large current log file
    large_content = "x" * (LOG_ROTATION_THRESHOLD_BYTES + 1000)
    log_file.write_text(large_content)

    # Setup file logging - should rotate and enforce limit
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Should have exactly LOG_BACKUP_COUNT backups (oldest removed)
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == LOG_BACKUP_COUNT


def test_counter_based_naming(tmp_path, logger_instance):
    """Test that collision counter increments for same timestamp."""
    log_file = tmp_path / "my-unicorn.log"

    # Mock datetime to return fixed timestamp
    fixed_timestamp = "20240115_143000"

    with patch("my_unicorn.logger.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = fixed_timestamp

        # Create large log file
        large_content = "x" * (LOG_ROTATION_THRESHOLD_BYTES + 1000)
        log_file.write_text(large_content)

        # First rotation
        logger_instance.setup_file_logging(log_file, level="DEBUG")

        # Should create backup with counter 1
        expected_backup = tmp_path / f"my-unicorn.{fixed_timestamp}.1.log"
        assert expected_backup.exists()

        # Clear logger state for second rotation
        clear_logger_state()
        logger_instance = MyUnicornLogger(f"test-{id(datetime.now())}")

        # Create another large log file
        log_file.write_text(large_content)

        # Second rotation with same timestamp
        logger_instance.setup_file_logging(log_file, level="DEBUG")

        # Should create backup with counter 2
        expected_backup_2 = tmp_path / f"my-unicorn.{fixed_timestamp}.2.log"
        assert expected_backup_2.exists()


def test_uses_filehandler_not_rotating(tmp_path, logger_instance):
    """Test that setup creates FileHandler, not RotatingFileHandler."""
    log_file = tmp_path / "my-unicorn.log"
    logger_instance.setup_file_logging(log_file, level="INFO")

    # Should have a FileHandler
    file_handlers = [
        h
        for h in logger_instance.logger.handlers
        if isinstance(h, logging.FileHandler)
    ]
    assert len(file_handlers) == 1

    # Should NOT have a RotatingFileHandler
    rotating_handlers = [
        h
        for h in logger_instance.logger.handlers
        if type(h).__name__ == "RotatingFileHandler"
    ]
    assert len(rotating_handlers) == 0


def test_rotation_error_graceful(tmp_path, logger_instance):
    """Test that rotation errors don't prevent logging setup."""
    log_file = tmp_path / "my-unicorn.log"

    # Create large log file
    large_content = "x" * (LOG_ROTATION_THRESHOLD_BYTES + 1000)
    log_file.write_text(large_content)

    # Mock the rename operation to simulate rotation failure
    def failing_rename(self, target):
        raise OSError("Simulated rotation failure")

    with patch.object(Path, "rename", failing_rename):
        # Setup should succeed even if rotation fails
        logger_instance.setup_file_logging(log_file, level="DEBUG")

        # Should have file handler despite rotation failure
        file_handlers = [
            h
            for h in logger_instance.logger.handlers
            if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1


def test_rotation_nonexistent_file(tmp_path, logger_instance):
    """Test rotation with non-existent log file doesn't error."""
    log_file = tmp_path / "nonexistent.log"

    # Should not exist
    assert not log_file.exists()

    # Setup should succeed and create the file
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Should have created new log file
    assert log_file.exists()
    assert log_file.stat().st_size == 0


def test_rotation_preserves_content_integrity(tmp_path, logger_instance):
    """Test that rotated backup contains exact original content."""
    log_file = tmp_path / "my-unicorn.log"

    # Create specific content larger than threshold
    lines = []
    for i in range(200000):
        lines.append(f"Log line {i}: Important data that must be preserved\n")
    original_content = "".join(lines)

    log_file.write_text(original_content)
    assert log_file.stat().st_size > LOG_ROTATION_THRESHOLD_BYTES

    # Trigger rotation
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Find the backup
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == 1

    # Verify content matches exactly
    backup_content = backups[0].read_text()
    assert backup_content == original_content


def test_multiple_rotation_cycles(tmp_path, logger_instance):
    """Test multiple rotation cycles over time."""
    log_file = tmp_path / "my-unicorn.log"

    for cycle in range(3):
        clear_logger_state()
        logger_instance = MyUnicornLogger(f"test-cycle-{cycle}")

        # Create large log file
        content = f"Cycle {cycle}: " + "x" * LOG_ROTATION_THRESHOLD_BYTES
        log_file.write_text(content)

        # Setup triggers rotation
        logger_instance.setup_file_logging(log_file, level="DEBUG")

        # Write some new content
        logger_instance.info("New log entry for cycle %s", cycle)

    # Should have 3 backups (one per cycle)
    backups = sorted(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == EXPECTED_ROTATION_CYCLES


def test_rotation_timestamp_format(tmp_path, logger_instance):
    """Test that backup filenames use correct timestamp format."""
    log_file = tmp_path / "my-unicorn.log"

    # Create large log file
    large_content = "x" * (LOG_ROTATION_THRESHOLD_BYTES + 1000)
    log_file.write_text(large_content)

    # Trigger rotation
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Find backup
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == 1

    backup_name = backups[0].name
    # Format: my-unicorn.YYYYMMDD_HHMMSS.N.log
    parts = backup_name.split(".")
    assert len(parts) == BACKUP_NAME_PARTS_COUNT
    assert parts[0] == "my-unicorn"
    assert parts[3] == "log"

    # Validate timestamp format
    timestamp_str = parts[1]
    try:
        datetime.strptime(timestamp_str, LOG_ROTATION_TIMESTAMP_FORMAT)
    except ValueError:
        pytest.fail(f"Invalid timestamp format: {timestamp_str}")


def test_rotation_directory_creation(tmp_path, logger_instance):
    """Test that rotation works when log directory doesn't exist."""
    log_dir = tmp_path / "nested" / "logs"
    log_file = log_dir / "my-unicorn.log"

    # Directory should not exist
    assert not log_dir.exists()

    # Setup should create directory and succeed
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    assert log_dir.exists()
    assert log_file.exists()


def test_rotation_with_unicode_content(tmp_path, logger_instance):
    """Test rotation handles Unicode content correctly."""
    log_file = tmp_path / "my-unicorn.log"

    # Create large log with Unicode content
    unicode_line = "🦄 Unicode test: 日本語 Español Русский 中文\n"
    lines = [unicode_line] * 200000
    original_content = "".join(lines)

    log_file.write_text(original_content, encoding="utf-8")
    assert log_file.stat().st_size > LOG_ROTATION_THRESHOLD_BYTES

    # Trigger rotation
    logger_instance.setup_file_logging(log_file, level="DEBUG")

    # Find backup and verify Unicode content
    backups = list(tmp_path.glob("my-unicorn.*.*.log"))
    assert len(backups) == 1

    backup_content = backups[0].read_text(encoding="utf-8")
    assert backup_content == original_content
    assert "🦄" in backup_content
