"""Progress reporting protocol for core domain services.

This module defines abstract interfaces for progress reporting that domain
services can depend on without coupling to concrete UI implementations.

The ProgressReporter protocol enables:
- Core services to report progress without importing UI packages
- Testing with mock/null progress reporters
- Alternative UI implementations (CLI, web, GUI)
- Optional progress tracking via null object pattern

Usage in domain services::

    from my_unicorn.core.protocols import (
        ProgressReporter,
        NullProgressReporter,
    )

    class DownloadService:
        def __init__(
            self,
            progress_reporter: ProgressReporter | None = None,
        ):
            self.progress = progress_reporter or NullProgressReporter()

        async def download(self, url: str) -> Path:
            task_id = self.progress.add_task(
                "Downloading", ProgressType.DOWNLOAD
            )
            # ... perform download with progress updates ...
            self.progress.finish_task(task_id)

"""

from __future__ import annotations

from enum import Enum, auto
from typing import Protocol, runtime_checkable


class ProgressType(Enum):
    """Types of progress operations for categorizing tasks.

    Progress types help UI implementations render appropriate visual feedback
    for different operation categories (spinners, progress bars, etc.).

    Attributes:
        API: GitHub API or network API operations
        DOWNLOAD: File download operations with byte-level progress
        VERIFICATION: Hash verification operations
        EXTRACTION: Icon or archive extraction operations
        PROCESSING: General post-processing operations
        INSTALLATION: AppImage installation workflow
        UPDATE: AppImage update workflow

    """

    API = auto()
    DOWNLOAD = auto()
    VERIFICATION = auto()
    EXTRACTION = auto()
    PROCESSING = auto()
    INSTALLATION = auto()
    UPDATE = auto()


@runtime_checkable
class ProgressReporter(Protocol):
    """Abstract interface for reporting progress from domain services.

    UI layer implementations should fulfill this protocol to receive progress
    updates from core workflows and services. This decouples domain logic from
    presentation concerns, following the Dependency Inversion Principle.

    The protocol supports:
    - Determinate progress (known total, e.g., file downloads)
    - Indeterminate progress (unknown total, e.g., API fetching)
    - Task lifecycle management (add, update, finish)
    - Active state checking for conditional progress updates

    Example implementation::

        class ConsoleProgress(ProgressReporter):
            def is_active(self) -> bool:
                return True

            def add_task(
                self,
                name: str,
                progress_type: ProgressType,
                total: float | None = None,
            ) -> str:
                task_id = str(uuid.uuid4())
                print(f"Starting: {name}")
                return task_id

            def update_task(
                self,
                task_id: str,
                completed: float | None = None,
                description: str | None = None,
            ) -> None:
                if completed:
                    print(f"Progress: {completed}")

            def finish_task(
                self,
                task_id: str,
                *,
                success: bool = True,
                description: str | None = None,
            ) -> None:
                status = "✓" if success else "✗"
                print(f"Finished: {status}")

            def get_task_info(self, task_id: str) -> dict:
                return {"completed": 0, "total": None, "description": ""}

    """

    def is_active(self) -> bool:
        """Check if progress reporting is currently active.

        Use this to conditionally perform progress updates. When inactive,
        callers may skip expensive progress calculations.

        Returns:
            True if progress reporting is enabled and active, False otherwise.

        """
        ...

    def add_task(
        self,
        name: str,
        progress_type: ProgressType,
        total: float | None = None,
    ) -> str:
        """Add a new progress task.

        Creates a new tracked task and returns an identifier for subsequent
        updates. The task remains active until finish_task() is called.

        Args:
            name: Human-readable task name for display.
            progress_type: Category of progress operation.
            total: Total units of work (bytes, items, etc.).
                None indicates indeterminate progress.

        Returns:
            Task identifier for use with update_task() and finish_task().

        """
        ...

    def update_task(
        self,
        task_id: str,
        completed: float | None = None,
        description: str | None = None,
    ) -> None:
        """Update progress for an existing task.

        Call periodically during long-running operations to report progress.
        Either completed or description (or both) should be provided.

        Args:
            task_id: Identifier returned from add_task().
            completed: Units of work completed (e.g., bytes downloaded).
            description: Updated task description for status messages.

        """
        ...

    def finish_task(
        self,
        task_id: str,
        *,
        success: bool = True,
        description: str | None = None,
    ) -> None:
        """Mark a task as complete.

        Signals the end of a task's lifecycle. After this call, the task_id
        should not be used for further updates.

        Args:
            task_id: Identifier of task to finish.
            success: Whether task completed successfully.
            description: Final status message.

        """
        ...

    def get_task_info(self, task_id: str) -> dict[str, object]:
        """Get current task information.

        Retrieve the current state of a task for inspection or coordination.

        Args:
            task_id: Identifier of task to query.

        Returns:
            Dictionary with keys:
                - completed: Current completion value (float)
                - total: Total expected value (float or None)
                - description: Current task description (str)

        """
        ...


class NullProgressReporter:
    """No-op progress reporter for when progress display is disabled.

    Implements the null object pattern to eliminate None checks in domain
    code. When a service doesn't need progress reporting, use this class
    instead of passing None.

    All methods are safe to call and have no side effects. The is_active()
    method returns False, allowing callers to skip expensive progress
    calculations when appropriate.

    Example usage:
        # In service constructor
        self.progress = progress_reporter or NullProgressReporter()

        # Safe to call without None checks
        task_id = self.progress.add_task("Operation", ProgressType.DOWNLOAD)
        self.progress.update_task(task_id, completed=50.0)
        self.progress.finish_task(task_id)

    """

    def is_active(self) -> bool:
        """Check if progress reporting is active.

        Returns:
            Always returns False for the null implementation.

        """
        return False

    def add_task(
        self,
        name: str,  # noqa: ARG002
        progress_type: ProgressType,  # noqa: ARG002
        total: float | None = None,  # noqa: ARG002
    ) -> str:
        """Add a new progress task (no-op).

        Args:
            name: Task name (ignored).
            progress_type: Progress type (ignored).
            total: Total value (ignored).

        Returns:
            Placeholder task identifier "null-task".

        """
        return "null-task"

    def update_task(
        self,
        task_id: str,
        completed: float | None = None,
        description: str | None = None,
    ) -> None:
        """Update task progress (no-op).

        Args:
            task_id: Task identifier (ignored).
            completed: Completion value (ignored).
            description: Description (ignored).

        """

    def finish_task(
        self,
        task_id: str,
        *,
        success: bool = True,
        description: str | None = None,
    ) -> None:
        """Mark task as complete (no-op).

        Args:
            task_id: Task identifier (ignored).
            success: Success status (ignored).
            description: Description (ignored).

        """

    def get_task_info(self, task_id: str) -> dict[str, object]:  # noqa: ARG002
        """Get task information.

        Args:
            task_id: Task identifier (ignored).

        Returns:
            Empty task info with default values.

        """
        return {"completed": 0.0, "total": None, "description": ""}
