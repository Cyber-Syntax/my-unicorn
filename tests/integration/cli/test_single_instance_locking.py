"""Integration tests for single-instance locking.

Tests LockManager and CLIRunner integration with real file I/O
but without spawning real subprocesses. These tests verify:
- LockManager properly integrates with CLIRunner
- Lock files are created and cleaned up correctly
- Error handling and logging work as expected
- Integration with file system operations
"""

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.cli.runner import CLIRunner
from my_unicorn.core.locking import LockManager
from my_unicorn.exceptions import LockError


@pytest.fixture
def integration_lock_path(tmp_path: Path) -> Path:
    """Provide a temporary lock file path for integration tests."""
    return tmp_path / "integration" / "my-unicorn.lock"


@pytest.mark.asyncio
async def test_lock_manager_acquired_in_cli_runner(
    integration_lock_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that LockManager is acquired when CLIRunner.run() is called.

    Verifies integration between CLIRunner and LockManager by checking
    that the lock manager is properly instantiated and used as a context
    manager in the run() method.
    """
    lock_manager_instance = MagicMock()
    lock_manager_instance.__aenter__ = AsyncMock(
        return_value=lock_manager_instance
    )
    lock_manager_instance.__aexit__ = AsyncMock(return_value=None)

    # Mock LockManager constructor to return our mock instance
    lock_manager_constructor = MagicMock(return_value=lock_manager_instance)

    # Patch at module level where it's imported
    with patch("my_unicorn.cli.runner.LockManager", lock_manager_constructor):
        # Mock parser to avoid actual CLI parsing
        class DummyParser:
            def __init__(self, config):  # type: ignore[no-untyped-def]
                self.config = config

            def parse_args(self):  # type: ignore[no-untyped-def]
                import sys  # noqa: PLC0415
                from argparse import Namespace  # noqa: PLC0415

                # Mock sys.argv to avoid interfering with pytest
                original_argv = sys.argv
                sys.argv = ["my-unicorn", "catalog"]
                try:
                    return Namespace(command="catalog", verbose=False)
                finally:
                    sys.argv = original_argv

        monkeypatch.setattr("my_unicorn.cli.runner.CLIParser", DummyParser)

        # Create runner and execute
        runner = CLIRunner()
        # Mock the handler to avoid actual execution
        runner.command_handlers["catalog"].execute = AsyncMock()  # type: ignore[method-assign]

        await runner.run()

    # Verify LockManager was instantiated with correct path
    assert lock_manager_constructor.called
    # Verify __aenter__ was called (lock acquired)
    assert lock_manager_instance.__aenter__.called
    # Verify __aexit__ was called (lock released)
    assert lock_manager_instance.__aexit__.called


@pytest.mark.asyncio
async def test_lock_error_logged_and_exits(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that LockError is properly logged and causes exit code 1.

    Verifies that when LockManager raises a LockError, the CLIRunner
    properly catches it, logs an appropriate error message, and exits
    with code 1.
    """
    # Create a mock LockManager that raises LockError on __aenter__
    lock_manager_instance = MagicMock()
    lock_manager_instance.__aenter__ = AsyncMock(
        side_effect=LockError("Another my-unicorn instance is already running")
    )
    lock_manager_instance.__aexit__ = AsyncMock(return_value=None)

    lock_manager_constructor = MagicMock(return_value=lock_manager_instance)

    with patch("my_unicorn.cli.runner.LockManager", lock_manager_constructor):
        # Mock parser
        class DummyParser:
            def __init__(self, config):  # type: ignore[no-untyped-def]
                self.config = config

            def parse_args(self):  # type: ignore[no-untyped-def]
                import sys  # noqa: PLC0415
                from argparse import Namespace  # noqa: PLC0415

                original_argv = sys.argv
                sys.argv = ["my-unicorn", "catalog"]
                try:
                    return Namespace(command="catalog", verbose=False)
                finally:
                    sys.argv = original_argv

        monkeypatch.setattr("my_unicorn.cli.runner.CLIParser", DummyParser)

        # Mock sys.exit to capture the exit code
        exit_code = None

        def fake_exit(code: int = 0) -> None:
            nonlocal exit_code
            exit_code = code
            raise SystemExit(code)

        monkeypatch.setattr("sys.exit", fake_exit)

        # Create runner
        runner = CLIRunner()

        # Capture logs
        with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
            await runner.run()

        # Verify exit code is 1
        assert exit_code == 1

        # Verify error message was logged
        assert any(
            "already running" in record.message.lower()
            for record in caplog.records
        )


@pytest.mark.asyncio
async def test_version_flag_skips_lock_manager(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that --version flag doesn't instantiate LockManager.

    Verifies that the --version flag is handled early in CLIRunner.run()
    before any attempt to acquire the lock, allowing multiple concurrent
    --version invocations without lock contention.
    """
    # Track if LockManager constructor was called
    lock_manager_called = False

    def fake_lock_manager(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal lock_manager_called
        lock_manager_called = True
        return MagicMock()

    with patch("my_unicorn.cli.runner.LockManager", fake_lock_manager):
        # Mock parser to return --version flag
        class DummyParser:
            def __init__(self, config):  # type: ignore[no-untyped-def]
                self.config = config

            def parse_args(self):  # type: ignore[no-untyped-def]
                import sys  # noqa: PLC0415
                from argparse import Namespace  # noqa: PLC0415

                original_argv = sys.argv
                sys.argv = ["my-unicorn", "--version"]
                try:
                    return Namespace(version=True)
                finally:
                    sys.argv = original_argv

        monkeypatch.setattr("my_unicorn.cli.runner.CLIParser", DummyParser)

        # Create runner and execute
        runner = CLIRunner()
        await runner.run()

        # Verify LockManager was never instantiated
        assert not lock_manager_called

        # Verify version was printed
        captured = capsys.readouterr()
        assert captured.out.strip()  # Version string should be printed


@pytest.mark.asyncio
async def test_lock_manager_context_manager_protocol(
    integration_lock_path: Path,
) -> None:
    """Test that LockManager properly implements context manager protocol.

    Verifies that __aenter__ and __aexit__ are called correctly,
    and that the lock file is created and cleaned up as expected.
    """
    # Track calls to __aenter__ and __aexit__
    aenter_called = False
    aexit_called = False

    async with LockManager(integration_lock_path) as lock_mgr:
        aenter_called = True
        # Verify lock file was created
        assert integration_lock_path.exists()
        # Verify file descriptor is open
        assert lock_mgr._lock_file is not None
        assert not lock_mgr._lock_file.closed

    aexit_called = True
    # Verify file descriptor was closed
    assert lock_mgr._lock_file is None or lock_mgr._lock_file.closed

    # Verify both methods were called
    assert aenter_called
    assert aexit_called


@pytest.mark.asyncio
async def test_lock_manager_concurrent_acquisition_fails(
    integration_lock_path: Path,
) -> None:
    """Test that concurrent lock acquisition fails with LockError.

    Verifies that attempting to acquire the same lock from two different
    LockManager instances results in a LockError for the second instance.
    """
    # First lock manager acquires lock
    lock_mgr1 = LockManager(integration_lock_path)

    async with lock_mgr1:
        # Second lock manager should fail to acquire lock
        lock_mgr2 = LockManager(integration_lock_path)

        with pytest.raises(LockError) as exc_info:
            async with lock_mgr2:
                pass

        # Verify error message
        assert "already running" in str(exc_info.value).lower()

    # After first lock is released, second should succeed
    async with lock_mgr2:
        assert lock_mgr2._lock_file is not None


@pytest.mark.asyncio
async def test_lock_manager_with_nested_directory_creation(
    tmp_path: Path,
) -> None:
    """Test that LockManager creates nested directories if needed.

    Verifies that the lock manager can handle deeply nested paths
    that don't exist yet, creating all necessary parent directories.
    """
    nested_lock_path = (
        tmp_path / "level1" / "level2" / "level3" / "my-unicorn.lock"
    )

    # Verify parent directories don't exist yet
    assert not nested_lock_path.parent.exists()

    async with LockManager(nested_lock_path) as lock_mgr:
        # Verify all parent directories were created
        assert nested_lock_path.parent.exists()
        assert nested_lock_path.exists()
        assert lock_mgr._lock_file is not None

    # Verify cleanup
    assert lock_mgr._lock_file is None or lock_mgr._lock_file.closed


@pytest.mark.asyncio
async def test_lock_manager_releases_lock_on_exception(
    integration_lock_path: Path,
) -> None:
    """Test that lock is released even when exception occurs in context.

    Verifies that __aexit__ is called and the lock is properly released
    even when an exception is raised inside the lock context.
    """
    lock_mgr = LockManager(integration_lock_path)

    with pytest.raises(ValueError, match="Test error"):
        async with lock_mgr:
            # Verify lock was acquired
            assert lock_mgr._lock_file is not None
            raise ValueError("Test error")

    # Verify lock was released despite exception
    assert lock_mgr._lock_file is None or lock_mgr._lock_file.closed

    # Verify we can acquire the lock again (it was properly released)
    async with lock_mgr:
        assert lock_mgr._lock_file is not None


@pytest.mark.asyncio
async def test_lock_manager_multiple_sequential_acquisitions(
    integration_lock_path: Path,
) -> None:
    """Test that lock can be acquired multiple times sequentially.

    Verifies that after releasing the lock, it can be acquired again
    by the same or different LockManager instances.
    """
    # First acquisition
    async with LockManager(integration_lock_path) as lock_mgr1:
        assert lock_mgr1._lock_file is not None

    # Second acquisition (same instance)
    async with LockManager(integration_lock_path) as lock_mgr2:
        assert lock_mgr2._lock_file is not None

    # Third acquisition (different instance)
    async with LockManager(integration_lock_path) as lock_mgr3:
        assert lock_mgr3._lock_file is not None


@pytest.mark.asyncio
async def test_concurrent_lock_attempts_with_asyncio_tasks(
    integration_lock_path: Path,
) -> None:
    """Test concurrent lock acquisition attempts using asyncio tasks.

    Verifies that when multiple asyncio tasks attempt to acquire the
    lock concurrently, only one succeeds and the others fail with LockError.
    """
    acquired_count = 0
    failed_count = 0

    async def try_acquire_lock() -> None:
        nonlocal acquired_count, failed_count
        try:
            async with LockManager(integration_lock_path):
                acquired_count += 1
                # Hold lock for a bit
                await asyncio.sleep(0.2)
        except LockError:
            failed_count += 1

    # Create 5 concurrent tasks trying to acquire the lock
    tasks = [try_acquire_lock() for _ in range(5)]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Verify only one acquired and others failed
    # Since fcntl.flock is non-blocking (LOCK_NB), concurrent attempts
    # fail immediately
    assert acquired_count == 1  # Only first task acquires lock
    assert failed_count == 4  # Other 4 tasks fail with LockError
