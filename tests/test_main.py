"""Tests for the main module functionality.

This module contains tests for the main CLI interface, including menu handling,
logging configuration, and command execution.
"""

# Standard library imports
import logging
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Generator, Any
from unittest.mock import patch, MagicMock

# Third-party imports
import pytest

# Ensure main module is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Local imports
import main
from my_unicorn.commands.invoker import CommandInvoker


@pytest.fixture
def mock_command() -> MagicMock:
    """Create a mock command for testing.

    Returns:
        MagicMock: A mock command object with execute method
    """
    command = MagicMock()
    command.execute = MagicMock()
    return command


@pytest.fixture
def mock_invoker(mock_command: MagicMock) -> CommandInvoker:
    """Create a CommandInvoker with mock commands.

    Args:
        mock_command: The mock command to register

    Returns:
        CommandInvoker: An invoker instance with registered mock commands
    """
    invoker = CommandInvoker()
    for i in range(1, 9):
        invoker.register_command(i, mock_command)
    return invoker


@pytest.fixture
def temp_log_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary directory for log files.

    Args:
        tmp_path: Pytest's temporary path fixture

    Yields:
        Path: Path to temporary log directory
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    with patch("main.log_dir", str(log_dir)):
        yield log_dir


@pytest.fixture
def mock_config_managers(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    """Mock global and app config managers.

    Args:
        monkeypatch: Pytest's monkeypatch fixture

    Returns:
        tuple[MagicMock, MagicMock]: tuple containing mock global and app config managers
    """
    mock_global_config = MagicMock()
    mock_app_config = MagicMock()

    monkeypatch.setattr("main.GlobalConfigManager", lambda: mock_global_config)
    monkeypatch.setattr("main.AppConfigManager", lambda: mock_app_config)

    return mock_global_config, mock_app_config


@pytest.fixture
def mock_rate_limit() -> tuple[int, int, str, bool]:
    """Mock GitHubAuthManager rate limit info.

    Returns:
        tuple[int, int, str, bool]: Mock rate limit values (remaining, limit, reset_time, is_authenticated)
    """
    return (100, 5000, "2024-01-01 00:00:00", True)


def test_get_user_choice_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_user_choice with valid input.

    Args:
        monkeypatch: Pytest's monkeypatch fixture
    """
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert main.get_user_choice() == 1


def test_get_user_choice_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_user_choice with invalid input.

    Args:
        monkeypatch: Pytest's monkeypatch fixture
    """
    monkeypatch.setattr("builtins.input", lambda _: "invalid")
    with pytest.raises(SystemExit) as exc_info:
        main.get_user_choice()
    assert exc_info.value.code == 1


def test_get_user_choice_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_user_choice with keyboard interrupt.

    Args:
        monkeypatch: Pytest's monkeypatch fixture
    """

    def mock_input(_: str) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", mock_input)
    with pytest.raises(SystemExit) as exc_info:
        main.get_user_choice()
    assert exc_info.value.code == 0


def test_configure_logging(tmp_path: Path) -> None:
    """Test logging configuration.

    Args:
        tmp_path: Pytest's temporary path fixture
    """
    # set up temporary log directory
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)

    # Save original handlers to restore later
    original_handlers = logging.getLogger().handlers.copy()

    try:
        # Patch __file__ to point to our temp directory
        with patch("main.__file__", str(tmp_path / "main.py")):
            # Call the function under test
            main.configure_logging()

            # Get the root logger
            logger = logging.getLogger()

            # Verify logger level
            assert logger.level == logging.DEBUG

            # Make sure we have exactly two new handlers
            assert len(logger.handlers) >= 2

            # Verify we have a RotatingFileHandler with DEBUG level
            file_handlers = [
                h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
            ]
            assert len(file_handlers) >= 1
            assert file_handlers[0].level == logging.DEBUG

            # Verify we have a non-rotating StreamHandler with ERROR level
            stream_handlers = [
                h
                for h in logger.handlers
                if isinstance(h, logging.StreamHandler)
                and not isinstance(h, logging.handlers.RotatingFileHandler)
            ]
            assert len(stream_handlers) >= 1
            assert stream_handlers[0].level == logging.ERROR
    finally:
        # Clean up by removing all handlers and restoring original ones
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Restore original handlers
        for handler in original_handlers:
            logger.addHandler(handler)
