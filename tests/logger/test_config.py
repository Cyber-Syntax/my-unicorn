"""Tests for logger configuration module."""

from pathlib import Path

from pytest import MonkeyPatch

from my_unicorn.logger.config import load_log_settings


def test_load_log_settings_with_env_var(monkeypatch: MonkeyPatch) -> None:
    """Test load_log_settings returns test dir when env var is set."""
    test_log_dir = "/tmp/pytest-test-logs"
    monkeypatch.setenv("MY_UNICORN_LOG_DIR", test_log_dir)

    console_level, file_level, log_path = load_log_settings()

    assert console_level == "WARNING"
    assert file_level == "INFO"  # DEFAULT_LOG_LEVEL from constants
    assert log_path == Path(test_log_dir) / "my-unicorn.log"


def test_load_log_settings_without_env_var(monkeypatch: MonkeyPatch) -> None:
    """Test load_log_settings returns default path when env var is not set."""
    monkeypatch.delenv("MY_UNICORN_LOG_DIR", raising=False)

    console_level, file_level, log_path = load_log_settings()

    assert console_level == "WARNING"
    assert file_level == "INFO"  # DEFAULT_LOG_LEVEL from constants
    expected_path = (
        Path.home() / ".config" / "my-unicorn" / "logs" / "my-unicorn.log"
    )
    assert log_path == expected_path


def test_load_log_settings_with_tilde_in_env_var(
    monkeypatch: MonkeyPatch,
) -> None:
    """Test load_log_settings expands tilde in MY_UNICORN_LOG_DIR."""
    monkeypatch.setenv("MY_UNICORN_LOG_DIR", "~/custom-logs")

    console_level, file_level, log_path = load_log_settings()

    assert console_level == "WARNING"
    assert file_level == "INFO"
    assert log_path == Path.home() / "custom-logs" / "my-unicorn.log"
    # Verify tilde was expanded
    assert "~" not in str(log_path)
