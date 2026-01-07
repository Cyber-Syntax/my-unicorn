"""Progress workflow helpers for command operations.

This module provides context managers and utilities for managing progress
tracking lifecycle across different command operations (install, update, etc.).
It eliminates duplication of progress management patterns.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from my_unicorn.ui.progress import ProgressDisplay


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
