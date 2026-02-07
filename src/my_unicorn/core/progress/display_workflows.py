"""Workflow helper functions for progress display.

These are standalone utility functions for creating common multi-phase
progress workflows. They are not part of the ProgressReporter protocol,
but provide convenient helpers for orchestrating complex operations.

Example:
    from my_unicorn.core.progress.display import ProgressDisplay
    from my_unicorn.core.progress.display_workflows import (
        create_api_fetching_task,
        create_verification_task,
        create_installation_workflow,
    )

    progress = ProgressDisplay()
    await progress.start_session()

    # Create individual tasks
    api_task = await create_api_fetching_task(progress, "GitHub releases")
    verify_task = await create_verification_task(progress, "app.AppImage")

    # Create multi-phase workflow
    verify_id, install_id = await create_installation_workflow(
        progress, "MyApp", with_verification=True
    )

    await progress.stop_session()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .progress_types import ProgressType

if TYPE_CHECKING:
    from .display import ProgressDisplay


async def create_api_fetching_task(
    progress_display: ProgressDisplay,
    name: str,
    description: str | None = None,
) -> str:
    """Create an API fetching task.

    This is a convenience helper for creating a task to track API calls.

    Args:
        progress_display: ProgressDisplay instance to add task to
        name: Task name
        description: Task description (defaults to "Fetching {name}")

    Returns:
        Task ID for the created API fetching task

    Example:
        task_id = await create_api_fetching_task(
            progress, "GitHub API", description="Fetching releases"
        )
    """
    return await progress_display.add_task(
        name=name,
        progress_type=ProgressType.API_FETCHING,
        description=description or f"Fetching {name}",
    )


async def create_verification_task(
    progress_display: ProgressDisplay,
    name: str,
    description: str | None = None,
) -> str:
    """Create a verification task.

    This is a convenience helper for creating a task to track file verification
    (e.g., hash checking).

    Args:
        progress_display: ProgressDisplay instance to add task to
        name: Task name
        description: Task description (defaults to "Verifying {name}")

    Returns:
        Task ID for the created verification task

    Example:
        task_id = await create_verification_task(
            progress, "app.AppImage", description="SHA256 check"
        )
    """
    return await progress_display.add_task(
        name=name,
        progress_type=ProgressType.VERIFICATION,
        description=description or f"Verifying {name}",
    )


async def create_installation_workflow(
    progress_display: ProgressDisplay,
    name: str,
    with_verification: bool = True,
) -> tuple[str | None, str]:
    """Create a multi-phase installation workflow.

    This creates linked verification and installation tasks for the
    same application. The verification task is phase 1/2, and installation
    is phase 2/2.

    When with_verification=False, creates only the installation task
    as phase 1/1 (standalone).

    Args:
        progress_display: ProgressDisplay instance to add tasks to
        name: Application name
        with_verification: Whether to create a verification task

    Returns:
        Tuple of (verification_task_id, installation_task_id)
        verification_task_id will be None if with_verification=False

    Example:
        verify_id, install_id = await create_installation_workflow(
            progress, "MyApp", with_verification=True
        )
        # Now can update both tasks in sequence as phases complete
    """
    verification_task_id = None

    if with_verification:
        # Create verification task as phase 1/2
        verification_task_id = await progress_display.add_task(
            name=name,
            progress_type=ProgressType.VERIFICATION,
            description=f"Verifying {name}",
            phase=1,
            total_phases=2,
        )

        # Create installation task as phase 2/2
        installation_task_id = await progress_display.add_task(
            name=name,
            progress_type=ProgressType.INSTALLATION,
            description=f"Installing {name}",
            parent_task_id=verification_task_id,
            phase=2,
            total_phases=2,
        )
    else:
        # Create installation task as phase 1/1 (no verification)
        installation_task_id = await progress_display.add_task(
            name=name,
            progress_type=ProgressType.INSTALLATION,
            description=f"Installing {name}",
            phase=1,
            total_phases=1,
        )

    return verification_task_id, installation_task_id
