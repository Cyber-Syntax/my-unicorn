"""Task registry for managing progress tasks and their state.

This module provides task storage and state management, extracted from
ProgressDisplay to follow SRP (Single Responsibility Principle).
"""

from __future__ import annotations

import asyncio
import time

from my_unicorn.logger import get_logger

from .progress_types import ProgressType, TaskInfo

logger = get_logger(__name__)


class TaskRegistry:
    """Manages task storage and state for progress display.

    Provides thread-safe access to task information using async locks.
    Stores tasks in two ways:
    - Primary storage: _tasks dict for full TaskInfo objects
    - Index storage: _task_sets dicts by ProgressType for fast lookups
    """

    def __init__(self) -> None:
        """Initialize the task registry."""
        self._tasks: dict[str, TaskInfo] = {}
        self._task_lock = asyncio.Lock()

        # Task sets for fast lookup by type
        self._task_sets: dict[ProgressType, set[str]] = {
            ProgressType.API_FETCHING: set(),
            ProgressType.DOWNLOAD: set(),
            ProgressType.VERIFICATION: set(),
            ProgressType.ICON_EXTRACTION: set(),
            ProgressType.INSTALLATION: set(),
            ProgressType.UPDATE: set(),
        }

    async def add_task_info(self, task_id: str, task_info: TaskInfo) -> None:
        """Add a task to the registry.

        Args:
            task_id: Unique task identifier
            task_info: TaskInfo object with task metadata

        """
        async with self._task_lock:
            self._tasks[task_id] = task_info
            self._task_sets[task_info.progress_type].add(task_id)

    async def update_task(
        self, task_id: str, **updates: object
    ) -> TaskInfo | None:
        """Update a task with new values.

        Args:
            task_id: Task identifier
            **updates: Field updates (e.g., completed=500.0, description="...")

        Returns:
            Updated TaskInfo or None if task not found

        """
        async with self._task_lock:
            if task_id not in self._tasks:
                return None

            task_info = self._tasks[task_id]

            # Apply updates to task info
            for key, value in updates.items():
                if hasattr(task_info, key):
                    setattr(task_info, key, value)

            task_info.last_update = time.monotonic()

            return task_info

    async def get_task_info(self, task_id: str) -> dict[str, object]:
        """Get task information by ID in protocol-compliant format.

        Returns task info as a dict matching the ProgressReporter protocol.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with completed, total, and description keys.
            Returns empty defaults if task not found.

        """
        task = self._tasks.get(task_id)
        if task is None:
            return {"completed": 0.0, "total": None, "description": ""}
        return {
            "completed": task.completed,
            "total": task.total,
            "description": task.description,
        }

    async def get_task_info_full(self, task_id: str) -> TaskInfo | None:
        """Get full task information by ID.

        This method returns the full TaskInfo object for internal UI
        operations.

        Args:
            task_id: Task identifier

        Returns:
            Full TaskInfo object or None if not found

        """
        return self._tasks.get(task_id)

    async def finish_task(
        self,
        task_id: str,
        success: bool = True,
        description: str | None = None,
    ) -> None:
        """Mark a task as finished.

        Args:
            task_id: Task identifier
            success: Whether the task succeeded
            description: Final description (if provided)

        """
        async with self._task_lock:
            if task_id not in self._tasks:
                return

            task_info = self._tasks[task_id]
            task_info.is_finished = True
            task_info.success = success

            if description is not None:
                task_info.description = description

            # Mark as completed if successful
            if success and task_info.total > 0:
                task_info.completed = task_info.total

    async def get_task_set(self, progress_type: ProgressType) -> set[str]:
        """Get set of task IDs for a specific progress type.

        Args:
            progress_type: Type of progress operation

        Returns:
            Set of task IDs matching the progress type

        """
        return self._task_sets.get(progress_type, set()).copy()

    def get_task_info_sync(self, task_id: str) -> dict[str, object]:
        """Get task info in protocol-compliant dict format (thread-safe sync).

        This is a synchronous accessor for use by protocol methods that
        cannot be async. Reading task state is safe without async lock
        due to Python's GIL, though updates may occur concurrently.

        Args:
            task_id: Task identifier

        Returns:
            Dict with completed, total, description keys

        """
        task = self._tasks.get(task_id)
        if task is None:
            return {"completed": 0.0, "total": None, "description": ""}
        return {
            "completed": task.completed,
            "total": task.total,
            "description": task.description,
        }

    def get_task_info_full_sync(self, task_id: str) -> TaskInfo | None:
        """Get full TaskInfo object (thread-safe sync read).

        This is a synchronous accessor for internal use. Reading task
        state is safe without async lock due to Python's GIL.

        Args:
            task_id: Task identifier

        Returns:
            Full TaskInfo object or None if not found

        """
        return self._tasks.get(task_id)
