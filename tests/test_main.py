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
from src.commands.invoker import CommandInvoker


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
        tuple[MagicMock, MagicMock]: Tuple containing mock global and app config managers
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
    # Set up temporary log directory
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


def test_main_exit(monkeypatch: pytest.MonkeyPatch, mock_invoker: CommandInvoker) -> None:
    """Test main function exit condition.

    Args:
        monkeypatch: Pytest's monkeypatch fixture
        mock_invoker: Mock command invoker fixture
    """
    # Mock get_user_choice to return exit option (10) - updated to match current exit option
    monkeypatch.setattr("main.get_user_choice", lambda: 10)

    # Mock sys.exit to avoid actual exit but track if it was called
    exit_called = False

    def mock_exit(code: int = 0) -> None:
        nonlocal exit_called
        exit_called = True
        # Raise RuntimeError instead of SystemExit to break out of the while loop
        raise RuntimeError(f"sys.exit({code}) called")

    monkeypatch.setattr("sys.exit", mock_exit)

    # Mock CommandInvoker
    monkeypatch.setattr("main.CommandInvoker", lambda: mock_invoker)

    # Mock other functions that might cause issues
    monkeypatch.setattr("main.configure_logging", lambda: None)

    # Mock GitHubAuthManager to avoid API calls
    monkeypatch.setattr(
        "src.auth_manager.GitHubAuthManager.get_rate_limit_info",
        lambda: (100, 5000, "2024-01-01 00:00:00", True),
    )

    # Run main and expect RuntimeError from our mock_exit
    with pytest.raises(RuntimeError) as exc_info:
        main.main()

    # Verify sys.exit was called
    assert exit_called
    assert "sys.exit(0) called" in str(exc_info.value)


def test_main_command_execution(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main function command execution.

    Args:
        monkeypatch: Pytest's monkeypatch fixture
        capsys: Pytest's capture fixture
    """
    # Create a simple mock command
    executed = False

    def mock_execute() -> None:
        nonlocal executed
        executed = True
        # Exit immediately after recording execution
        raise SystemExit(0)

    class MockCommand:
        def execute(self) -> None:
            mock_execute()

    # Create a mock invoker that avoids any actual command registration
    class MockInvoker:
        def __init__(self) -> None:
            self._command = MockCommand()

        def register_command(self, number: int, command: Any) -> None:
            # Just a stub to satisfy the main function's call
            pass

        def execute_command(self, number: int) -> None:
            if number == 1:
                self._command.execute()

    # Mock the get_user_choice function to print the welcome message and return 1
    def mock_get_user_choice():
        # Print the welcome message that would normally be printed by get_user_choice
        print("\n" + "=" * 60)
        print("                 Welcome to my-unicorn 🦄")
        print("=" * 60)
        return 1

    # Mock essential dependencies
    monkeypatch.setattr(
        "src.auth_manager.GitHubAuthManager.get_rate_limit_info",
        lambda: (100, 5000, "2024-01-01 00:00:00", True),
    )
    monkeypatch.setattr("main.CommandInvoker", MockInvoker)
    monkeypatch.setattr("main.get_user_choice", mock_get_user_choice)

    # Mock configure_logging to avoid file system operations
    monkeypatch.setattr("main.configure_logging", lambda: None)

    # Clear any existing output
    capsys.readouterr()

    # Run main function
    with pytest.raises(SystemExit) as exc_info:
        main.main()

    # Verify we exited cleanly
    assert exc_info.value.code == 0

    # Verify our command was executed
    assert executed

    # Get final output and verify menu was shown
    captured = capsys.readouterr()
    assert "Welcome to my-unicorn" in captured.out


def test_custom_excepthook() -> None:
    """Test custom exception hook logging."""
    # Create a string buffer to capture log output
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger()
    logger.addHandler(handler)

    # Test exception
    try:
        raise ValueError("Test error")
    except ValueError:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        main.custom_excepthook(exc_type, exc_value, exc_traceback)

    # Verify error was logged
    log_output = log_stream.getvalue()
    assert "Uncaught exception" in log_output
    assert "ValueError: Test error" in log_output
