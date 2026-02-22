"""Process-level locking utilities using fcntl.flock.

This module provides LockManager for ensuring only one instance of my-unicorn
runs at a time using fcntl.flock on a lock file.
"""

from __future__ import annotations

import asyncio
import fcntl
from pathlib import (
    Path,  # noqa: TC003 - Path used at runtime for file operations
)
from typing import IO, TYPE_CHECKING, Self

from my_unicorn.exceptions import LockError

if TYPE_CHECKING:
    import types


class LockManager:
    """Async context manager for process-level file locking using fcntl.flock.

    Uses a lock file with non-blocking exclusive lock (LOCK_EX | LOCK_NB) to
    ensure fail-fast behavior when another instance holds the lock.

    Attributes:
        _lock_path: Path to the lock file.
        _lock_file: Open file descriptor for lock file (None when unlocked).

    Example:
        >>> from pathlib import Path
        >>> from my_unicorn.core.locking import LockManager
        >>> lock_path = Path("/tmp/my-unicorn.lock")
        >>> async with LockManager(lock_path):
        ...     # Exclusive lock held for this block
        ...     pass

    """

    def __init__(self, lock_path: Path) -> None:
        """Initialize LockManager with lock file path.

        Args:
            lock_path: Path to the lock file to be created/used.

        """
        self._lock_path = lock_path
        self._lock_file: IO[str] | None = None

    async def __aenter__(self) -> Self:
        """Acquire lock when entering context.

        Creates parent directory if needed, opens lock file in write mode,
        and acquires exclusive non-blocking lock using fcntl.flock.

        Returns:
            Self for use in async context manager.

        Raises:
            LockError: If lock cannot be acquired because another instance
                holds it, or if file operations fail.

        """
        loop = asyncio.get_event_loop()

        def _acquire_lock() -> None:
            """Acquire lock in a thread context."""
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)

            lock_file = None
            try:
                lock_file = self._lock_path.open("w", encoding="utf-8")
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._lock_file = lock_file
            except BlockingIOError as e:
                if lock_file is not None:
                    lock_file.close()
                msg = "Another my-unicorn instance is already running"
                raise LockError(msg, cause=e) from e
            except OSError as e:
                if lock_file is not None:
                    lock_file.close()
                msg = f"Failed to acquire lock: {e}"
                raise LockError(msg, cause=e) from e

        await loop.run_in_executor(None, _acquire_lock)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Release lock when exiting context.

        Closes file descriptor and releases the lock held by fcntl.flock.
        Safe to call even if lock was never acquired.

        Args:
            exc_type: Exception type if exception occurred, None otherwise.
            exc_val: Exception value if exception occurred, None otherwise.
            exc_tb: Exception traceback if exception occurred, None otherwise.

        """
        if self._lock_file is not None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._lock_file.close)
            self._lock_file = None
