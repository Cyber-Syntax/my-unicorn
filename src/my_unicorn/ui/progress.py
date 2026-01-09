"""Progress display with ASCII rendering backend.

This module provides a centralized progress display UI component that handles
different types of operations with ASCII-based visual feedback.

Design notes:
- Concurrency: the backend (`AsciiProgressBackend`) uses an
    `asyncio.Lock` to protect async rendering and a separate
    `threading.Lock` (`_sync_lock`) to protect state when synchronous
    callers update tasks. The renderer snapshots shared state while
    holding locks, releases them, and then formats output so rendering
    is safe for concurrent use.
- Timing: use `time.monotonic()` for measuring intervals (spinner
    frames, speed calculations, and debounce timestamps) so rendering is
    robust to system clock changes. Wall-clock creation timestamps may
    continue to use `time.time()` when appropriate.

Usage (simple, recommended):

    from my_unicorn.progress import progress_session

    async with progress_session() as progress:
        # create linked verification & installation tasks
        verification_id, installation_id = (
        await progress.create_installation_workflow("App")
        )
        # update/finish tasks as work proceeds

"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

from my_unicorn.logger import get_logger

# Import classes for re-export
from .ascii import AsciiProgressBackend
from .display import ProgressDisplay
from .progress_types import (
    ID_CACHE_LIMIT,
    OPERATION_NAMES,
    ProgressConfig,
    ProgressType,
    TaskInfo,
    TaskState,
)

__all__ = [
    "ID_CACHE_LIMIT",
    "OPERATION_NAMES",
    "AsciiProgressBackend",
    "ProgressConfig",
    "ProgressDisplay",
    "ProgressType",
    "TaskInfo",
    "TaskState",
    "github_api_progress_task",
    "operation_progress_session",
    "progress_session",
]

logger = get_logger(__name__)


# ============================================================================
# Progress Workflow Helpers (from utils/progress_helpers.py)
# ============================================================================


@asynccontextmanager
async def github_api_progress_task(
    progress: ProgressDisplay | None,
    *,
    task_name: str,
    total: int,
) -> AsyncIterator[str | None]:
    """Manage GitHub API progress task lifecycle.

    This context manager handles the complete lifecycle of a GitHub API
    progress task, including creation, updates, and cleanup on both
    success and failure.

    Args:
        progress: Progress display service (can be None)
        task_name: Name for the progress task
        total: Total number of API calls expected

    Yields:
        Task ID if progress service available, None otherwise

    Example:
        >>> async with github_api_progress_task(
        ...     progress, task_name="Fetching releases", total=5
        ... ) as task_id:
        ...     # Perform API operations
        ...     pass
    """
    if not progress:
        yield None
        return

    task_id = await progress.create_api_fetching_task(
        name=task_name,
        description="🌐 Fetching release information...",
    )
    await progress.update_task(task_id, total=float(total), completed=0.0)

    try:
        yield task_id
        await progress.finish_task(task_id, success=True)
    except Exception:
        await progress.finish_task(task_id, success=False)
        raise


@asynccontextmanager
async def operation_progress_session(
    progress: ProgressDisplay | None,
    *,
    total_operations: int,
) -> AsyncIterator[ProgressDisplay | None]:
    """Manage progress session lifecycle for operations.

    This context manager handles the progress session lifecycle for
    operations that need progress tracking. It automatically handles
    the case where progress is None or total_operations is 0.

    Args:
        progress: Progress display service (can be None)
        total_operations: Total number of operations to track

    Yields:
        Progress service if available, None otherwise

    Example:
        >>> async with operation_progress_session(
        ...     progress, total_operations=10
        ... ) as prog:
        ...     if prog:
        ...         await prog.update_task(...)
    """
    if not progress or total_operations == 0:
        yield progress
        return

    async with progress.session(total_operations):
        yield progress


@asynccontextmanager
async def progress_session(
    total_operations: int = 0,
) -> AsyncGenerator[ProgressDisplay, None]:
    """Context manager for creating and managing a progress session.

    Creates a new ProgressDisplay instance for dependency injection.

    Args:
        total_operations: Total number of operations

    Yields:
        Progress display instance

    """
    service = ProgressDisplay()

    async with service.session(total_operations):
        yield service
