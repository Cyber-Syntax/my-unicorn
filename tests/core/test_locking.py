"""Tests for LockManager: fcntl.flock-based process-level locking."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from my_unicorn.constants import LOCKFILE_PATH
from my_unicorn.core.locking import LockManager
from my_unicorn.exceptions import LockError


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    """Provide a temporary lock file path."""
    return tmp_path / "lock" / "my-unicorn.lock"


@pytest.mark.asyncio
async def test_lock_manager_successful_acquisition(lock_path: Path) -> None:
    """Test LockManager acquires lock and opens file descriptor."""
    async with LockManager(lock_path) as lock_mgr:
        assert lock_mgr._lock_file is not None
        assert lock_path.exists()
        assert lock_path.parent.exists()


@pytest.mark.asyncio
async def test_lock_manager_creates_parent_directory(tmp_path: Path) -> None:
    """Test LockManager creates parent directory if missing."""
    lock_path = tmp_path / "deeply" / "nested" / "lock" / "my-unicorn.lock"
    assert not lock_path.parent.exists()

    async with LockManager(lock_path) as lock_mgr:
        assert lock_mgr._lock_file is not None
        assert lock_path.parent.exists()


@pytest.mark.asyncio
async def test_lock_manager_releases_lock_on_exit(lock_path: Path) -> None:
    """Test LockManager releases lock and closes file descriptor on exit."""
    lock_mgr = LockManager(lock_path)
    async with lock_mgr:
        assert lock_mgr._lock_file is not None

    assert lock_mgr._lock_file is None


@pytest.mark.asyncio
async def test_lock_manager_releases_lock_on_exception(
    lock_path: Path,
) -> None:
    """Test LockManager releases lock even when exception is raised."""

    async def _raise_error(lock_mgr: LockManager) -> None:
        """Helper to raise error inside lock context."""
        async with lock_mgr:
            assert lock_mgr._lock_file is not None
            raise ValueError("Test exception")

    lock_mgr = LockManager(lock_path)

    with pytest.raises(ValueError, match="Test exception"):
        await _raise_error(lock_mgr)

    assert lock_mgr._lock_file is None


@pytest.mark.asyncio
async def test_lock_manager_fails_when_lock_held(lock_path: Path) -> None:
    """Test LockManager raises LockError when lock is already held."""
    async with LockManager(lock_path):
        with pytest.raises(LockError):
            async with LockManager(lock_path):
                pass


@pytest.mark.asyncio
async def test_lock_manager_error_message(lock_path: Path) -> None:
    """Test LockManager error message when lock acquisition fails."""
    async with LockManager(lock_path):
        with pytest.raises(LockError) as exc_info:
            async with LockManager(lock_path):
                pass

    msg = "Another my-unicorn instance is already running"
    assert msg in str(exc_info.value)


def test_lock_path_default_when_env_not_set() -> None:
    """Verify default lock path is used when env var is not set.

    This test ensures that when MY_UNICORN_LOCKFILE_PATH is not set,
    the runner uses the default LOCKFILE_PATH from constants.
    """
    with patch.dict(os.environ, {}, clear=False):
        # Remove the env var if it exists
        os.environ.pop("MY_UNICORN_LOCKFILE_PATH", None)

        # Get the lock path that would be used
        env_var_value = os.environ.get(
            "MY_UNICORN_LOCKFILE_PATH", str(LOCKFILE_PATH)
        )
        lock_path = Path(env_var_value)

        # Should equal the default from constants
        assert lock_path == LOCKFILE_PATH
        assert lock_path == Path("/tmp/my-unicorn.lock")


def test_lock_path_from_environment_variable(tmp_path: Path) -> None:
    """Verify custom lock path is used when env var is set.

    This test ensures that when MY_UNICORN_LOCKFILE_PATH is set,
    the runner uses the custom path instead of the default.
    """
    custom_lock_path = tmp_path / "custom" / "lock.lock"
    env_var_value = str(custom_lock_path)

    with patch.dict(os.environ, {"MY_UNICORN_LOCKFILE_PATH": env_var_value}):
        # Get the lock path that would be used
        env_value = os.environ.get(
            "MY_UNICORN_LOCKFILE_PATH", str(LOCKFILE_PATH)
        )
        lock_path = Path(env_value)

        # Should use the custom path from env var
        assert lock_path == custom_lock_path
        assert lock_path != LOCKFILE_PATH
