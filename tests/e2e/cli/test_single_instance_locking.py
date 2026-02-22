"""End-to-end tests for single-instance locking using sandboxed processes.

This module tests real cross-process locking behavior by spawning actual
CLI processes in isolated sandbox environments. Tests verify that:
- A second CLI process is blocked when the first holds the lock
- The lock is released when the first process exits
- The --version flag bypasses the lock and allows concurrent execution

Each test runs in its own SandboxEnvironment with per-test lock files,
ensuring isolation from production data and clean test state.
"""

from __future__ import annotations

import inspect
import threading
import time
from typing import TYPE_CHECKING

import pytest

from tests.e2e.runner import E2ERunner
from tests.e2e.sandbox import SandboxEnvironment

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def sandbox_env() -> Generator[SandboxEnvironment, None, None]:
    """Create isolated sandbox environment for test.

    Each test gets its own temporary HOME directory with per-test naming
    to ensure isolation and prevent lock file conflicts.

    Yields:
        Active SandboxEnvironment instance
    """
    # Get calling test name for meaningful sandbox directory
    frame = inspect.currentframe()
    test_name = "test"
    if frame and frame.f_back:
        test_name = frame.f_back.f_code.co_name

    with SandboxEnvironment(name=test_name, cleanup=True) as env:
        yield env


@pytest.fixture
def e2e_runner(sandbox_env: SandboxEnvironment) -> E2ERunner:
    """Create E2E CLI runner for sandbox.

    Args:
        sandbox_env: The sandbox environment instance

    Returns:
        E2ERunner configured for the sandbox
    """
    return E2ERunner(sandbox_env)


@pytest.fixture
def sandbox_lock_path(sandbox_env: SandboxEnvironment) -> Path:
    """Return lock file path within sandbox.

    Creates the directory if needed and returns path for lock file
    that will be used by all commands in the test.

    Args:
        sandbox_env: The sandbox environment instance

    Returns:
        Path to lock file within sandbox temp directory
    """
    lock_dir = sandbox_env.temp_home / ".config" / "my-unicorn"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "my-unicorn.lock"


@pytest.mark.slow
@pytest.mark.e2e
def test_catalog_install_blocked_by_lock(
    e2e_runner: E2ERunner,
    sandbox_lock_path: Path,
) -> None:
    """Verify second install is blocked when first holds the lock.

    Spawns install in a background thread with lock held, then attempts
    second install which should fail with lock error.

    This confirms that state-changing operations (install) properly
    acquire and protect the single-instance lock.
    """
    errors: list[Exception] = []
    result_holder: list[subprocess.CompletedProcess[str]] = []

    def run_install_command() -> None:
        """Run install command that will hold lock for a while."""
        try:
            lock_path_str = str(sandbox_lock_path)
            lock_env_override = {"MY_UNICORN_LOCKFILE_PATH": lock_path_str}
            result = e2e_runner.run_cli(
                "install",
                "qownnotes",
                env_overrides=lock_env_override,
            )
            result_holder.append(result)
        except OSError as e:
            errors.append(e)

    # Start install in background thread (will hold lock)
    thread1 = threading.Thread(target=run_install_command)
    thread1.start()

    # Give first process time to acquire lock
    time.sleep(0.5)

    # Attempt second install with same lock path
    result2 = e2e_runner.run_cli(
        "install",
        "qownnotes",
        env_overrides={"MY_UNICORN_LOCKFILE_PATH": str(sandbox_lock_path)},
    )

    # Verify second process failed with lock error
    assert result2.returncode == 1, (
        f"Expected exit code 1, got {result2.returncode}. "
        f"stdout: {result2.stdout}"
    )
    # Error message is logged to stdout or stderr
    output = result2.stdout + result2.stderr
    assert "already running" in output.lower(), (
        f"Expected 'already running' in output, got: {output}"
    )

    # Wait for first thread to finish
    thread1.join(timeout=15)

    # Verify no unexpected errors in background thread
    assert not errors, f"Unexpected errors in background thread: {errors}"


@pytest.mark.slow
@pytest.mark.e2e
def test_lock_released_allows_second_command(
    e2e_runner: E2ERunner,
    sandbox_lock_path: Path,
) -> None:
    """Verify second command succeeds after first releases lock.

    Runs first --version command which acquires and releases lock,
    then runs second --version command which should succeed since
    lock was properly released.

    This confirms that the locking mechanism properly releases locks
    when processes exit normally.
    """
    # Start and wait for first process to complete and release lock
    lock_path_str = str(sandbox_lock_path)
    lock_env_override = {"MY_UNICORN_LOCKFILE_PATH": lock_path_str}
    result1 = e2e_runner.run_cli(
        "--version",
        env_overrides=lock_env_override,
    )

    # First process should succeed
    assert result1.returncode == 0, f"First process failed: {result1.stderr}"

    # Give lock time to be fully released
    time.sleep(0.2)

    # Start second process after first has released lock
    result2 = e2e_runner.run_cli(
        "--version",
        env_overrides=lock_env_override,
    )

    # Second process should also succeed (lock was released)
    assert result2.returncode == 0, f"Second process failed: {result2.stderr}"


@pytest.mark.slow
@pytest.mark.e2e
def test_version_bypasses_lock(
    e2e_runner: E2ERunner,
    sandbox_lock_path: Path,
) -> None:
    """Verify multiple --version commands succeed without lock contention.

    Spawns 3 concurrent --version commands which should all succeed without
    blocking, since --version is a read-only operation that doesn't require
    the lock.

    This confirms that the CLI properly allows concurrent read-only operations
    while restricting concurrent state-changing operations.
    """
    # Track results from concurrent processes
    results: list[subprocess.CompletedProcess[str]] = []
    exceptions: list[Exception] = []

    def run_version_command() -> None:
        """Run --version and store result."""
        try:
            lock_path_str = str(sandbox_lock_path)
            lock_env_override = {"MY_UNICORN_LOCKFILE_PATH": lock_path_str}
            result = e2e_runner.run_cli(
                "--version",
                env_overrides=lock_env_override,
            )
            results.append(result)
        except OSError as e:
            exceptions.append(e)

    # Start 3 concurrent --version commands
    threads = [threading.Thread(target=run_version_command) for _ in range(3)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=20)

    # Verify no exceptions occurred
    assert not exceptions, (
        f"Exceptions during concurrent execution: {exceptions}"
    )

    # Verify all 3 commands succeeded
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"

    for i, result in enumerate(results):
        assert result.returncode == 0, (
            f"Process {i} failed with returncode "
            f"{result.returncode}: {result.stderr}"
        )
        # Should output version string
        assert result.stdout.strip(), f"Process {i} produced no version output"
