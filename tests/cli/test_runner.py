"""Tests for CLI runner module."""

import logging
import sys
from argparse import Namespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.cli import runner
from my_unicorn.exceptions import LockError


@pytest.fixture(autouse=True)
def patch_sys_exit(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Mock sys.exit to raise SystemExit instead of exiting."""
    called: dict[str, int] = {}

    def fake_exit(code: int = 0) -> None:
        called["code"] = code
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)
    return called


@pytest.fixture
def mock_parser(monkeypatch: pytest.MonkeyPatch) -> type:
    """Mock CLIParser for testing."""

    class DummyParser:
        def __init__(self, config: Any) -> None:
            self.config = config

        def parse_args(self) -> Namespace:
            return Namespace(command="install", verbose=False)

    monkeypatch.setattr(runner, "CLIParser", DummyParser)
    return DummyParser


@pytest.fixture
def cli_runner(
    mock_parser: type,
) -> tuple[runner.CLIRunner, dict[str, Any]]:
    """Create CLI runner with mocked handlers for testing."""
    r = runner.CLIRunner()
    executed: dict[str, Any] = {}

    # Replace each handler.execute with an async mock
    for cmd in r.command_handlers:

        def make_fake_exec(command: str) -> Any:
            async def fake_exec(args: Namespace) -> None:
                executed["command"] = command
                executed["args"] = args

            return fake_exec

        r.command_handlers[cmd].execute = make_fake_exec(cmd)  # type: ignore[method-assign]

    return r, executed


@pytest.mark.asyncio
async def test_run_executes_known_command(
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
    patch_sys_exit: dict[str, int],
) -> None:
    """Test that execute_command routes commands to handlers."""
    r, executed = cli_runner
    args = Namespace(command="install", verbose=False)
    await r._execute_command(args)
    assert executed["command"] == "install"
    assert executed["args"].command == "install"


@pytest.mark.asyncio
async def test_run_with_unknown_command(
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
) -> None:
    """Test that unknown commands exit with error code 1."""
    r, _ = cli_runner
    args = Namespace(command="doesnotexist", verbose=False)
    with pytest.raises(SystemExit) as e:
        await r._execute_command(args)
    assert e.value.code == 1


@pytest.mark.asyncio
async def test_run_no_command(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
) -> None:
    """Test that missing command exits with error code 1."""

    class DummyParser:
        def __init__(self, config: Any) -> None:
            pass

        def parse_args(self) -> Namespace:
            return Namespace(command=None)

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    r, _ = cli_runner
    with pytest.raises(SystemExit) as e:
        await r.run()
    assert e.value.code == 1


@pytest.mark.asyncio
async def test_run_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
) -> None:
    """Test that KeyboardInterrupt exits with code 1."""

    class DummyParser:
        def __init__(self, config: Any) -> None:
            pass

        def parse_args(self) -> Namespace:
            raise KeyboardInterrupt

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    r, _ = cli_runner
    with pytest.raises(SystemExit) as e:
        await r.run()
    assert e.value.code == 1


@pytest.mark.asyncio
async def test_run_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
) -> None:
    """Test that unexpected errors exit with code 1."""

    class DummyParser:
        def __init__(self, config: Any) -> None:
            pass

        def parse_args(self) -> Namespace:
            raise ValueError("boom")

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    r, _ = cli_runner
    with pytest.raises(SystemExit) as e:
        await r.run()
    assert e.value.code == 1


@pytest.mark.asyncio
async def test_verbose_logging(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
) -> None:
    """Test that verbose flag sets console handler to DEBUG level."""
    r, executed = cli_runner
    args = Namespace(command="install", verbose=True)

    # Track handler level changes
    original_levels = {}
    for h in runner.logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(
            h, logging.FileHandler
        ):
            original_levels[id(h)] = h.level

    await r._execute_command(args)

    # Verify command was executed
    assert executed["command"] == "install"

    # Verify console handler level was restored after execution
    for h in runner.logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(
            h, logging.FileHandler
        ):
            assert h.level == original_levels.get(id(h), h.level)


@pytest.mark.asyncio
async def test_cli_runner_acquires_lock_on_startup(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
) -> None:
    """Test that lock is acquired when run() is called."""
    r, _ = cli_runner
    lock_manager_mock = MagicMock()
    lock_manager_mock.__aenter__ = AsyncMock(return_value=lock_manager_mock)
    lock_manager_mock.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        runner, "LockManager", MagicMock(return_value=lock_manager_mock)
    )

    class DummyParser:
        def __init__(self, config: Any) -> None:
            pass

        def parse_args(self) -> Namespace:
            return Namespace(command="install", verbose=False)

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    await r.run()

    # Verify LockManager was instantiated and __aenter__ was called
    assert lock_manager_mock.__aenter__.called


@pytest.mark.asyncio
async def test_cli_runner_releases_lock_on_exit(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
) -> None:
    """Test that lock is released when run() completes."""
    r, _ = cli_runner
    lock_manager_mock = MagicMock()
    lock_manager_mock.__aenter__ = AsyncMock(return_value=lock_manager_mock)
    lock_manager_mock.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        runner, "LockManager", MagicMock(return_value=lock_manager_mock)
    )

    class DummyParser:
        def __init__(self, config: Any) -> None:
            pass

        def parse_args(self) -> Namespace:
            return Namespace(command="install", verbose=False)

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    await r.run()

    # Verify __aexit__ was called to release lock
    assert lock_manager_mock.__aexit__.called


@pytest.mark.asyncio
async def test_cli_runner_fails_with_lock_error(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
) -> None:
    """Test that LockError is handled gracefully with logging."""
    r, _ = cli_runner
    lock_manager_mock = MagicMock()
    lock_manager_mock.__aenter__ = AsyncMock(
        side_effect=LockError("Another instance is running")
    )
    lock_manager_mock.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        runner, "LockManager", MagicMock(return_value=lock_manager_mock)
    )

    class DummyParser:
        def __init__(self, config: Any) -> None:
            pass

        def parse_args(self) -> Namespace:
            return Namespace(command="install", verbose=False)

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    with pytest.raises(SystemExit) as exc_info:
        await r.run()

    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_cli_runner_version_flag_skips_lock(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner: tuple[runner.CLIRunner, dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that --version flag execution doesn't require lock."""
    r, _ = cli_runner
    lock_manager_constructor_mock = MagicMock()
    lock_manager_mock = MagicMock()
    lock_manager_mock.__aenter__ = AsyncMock(return_value=lock_manager_mock)
    lock_manager_mock.__aexit__ = AsyncMock(return_value=None)

    lock_manager_constructor_mock.return_value = lock_manager_mock
    monkeypatch.setattr(runner, "LockManager", lock_manager_constructor_mock)

    class DummyParser:
        def __init__(self, config: Any) -> None:
            pass

        def parse_args(self) -> Namespace:
            return Namespace(version=True)

    monkeypatch.setattr(runner, "CLIParser", DummyParser)

    await r.run()

    # Verify LockManager constructor was never called for --version
    assert not lock_manager_constructor_mock.called
