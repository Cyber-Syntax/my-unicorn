"""Tests for progress display workflow helper functions.

Tests verify that workflow helper functions correctly create and manage
multi-phase progress tasks for common workflows like installation.
"""

import pytest

from my_unicorn.core.progress.display import ProgressDisplay
from my_unicorn.core.progress.display_workflows import (
    create_api_fetching_task,
    create_installation_workflow,
    create_verification_task,
)
from my_unicorn.core.progress.progress_types import ProgressType


@pytest.mark.asyncio
async def test_workflow_helper_api_fetching() -> None:
    """Test create_api_fetching_task standalone function works."""
    progress = ProgressDisplay()
    await progress.start_session()

    task_id = await create_api_fetching_task(progress, "GitHub API")

    assert task_id is not None
    task = progress.get_task_info_full(task_id)
    assert task is not None
    assert task.progress_type == ProgressType.API_FETCHING
    assert task.name == "GitHub API"
    assert task.description == "Fetching GitHub API"

    await progress.stop_session()


@pytest.mark.asyncio
async def test_workflow_helper_api_fetching_custom_description() -> None:
    """Test create_api_fetching_task with custom description."""
    progress = ProgressDisplay()
    await progress.start_session()

    task_id = await create_api_fetching_task(
        progress, "API", description="Custom fetch"
    )

    assert task_id is not None
    task = progress.get_task_info_full(task_id)
    assert task is not None
    assert task.description == "Custom fetch"

    await progress.stop_session()


@pytest.mark.asyncio
async def test_workflow_helper_verification() -> None:
    """Test create_verification_task standalone function works."""
    progress = ProgressDisplay()
    await progress.start_session()

    task_id = await create_verification_task(progress, "file.zip")

    assert task_id is not None
    task = progress.get_task_info_full(task_id)
    assert task is not None
    assert task.progress_type == ProgressType.VERIFICATION
    assert task.name == "file.zip"
    assert task.description == "Verifying file.zip"

    await progress.stop_session()


@pytest.mark.asyncio
async def test_workflow_helper_verification_custom_description() -> None:
    """Test create_verification_task with custom description."""
    progress = ProgressDisplay()
    await progress.start_session()

    task_id = await create_verification_task(
        progress, "app.AppImage", description="SHA256 check"
    )

    assert task_id is not None
    task = progress.get_task_info_full(task_id)
    assert task is not None
    assert task.description == "SHA256 check"

    await progress.stop_session()


@pytest.mark.asyncio
async def test_workflow_helper_installation_with_verification() -> None:
    """Test create_installation_workflow creates linked phases with verification."""
    progress = ProgressDisplay()
    await progress.start_session()

    verify_id, install_id = await create_installation_workflow(
        progress, "MyApp", with_verification=True
    )

    assert verify_id is not None
    assert install_id is not None

    # Check verification task
    verify_task = progress.get_task_info_full(verify_id)
    assert verify_task is not None
    assert verify_task.progress_type == ProgressType.VERIFICATION
    assert verify_task.name == "MyApp"
    assert verify_task.description == "Verifying MyApp"
    assert verify_task.phase == 1
    assert verify_task.total_phases == 2

    # Check installation task
    install_task = progress.get_task_info_full(install_id)
    assert install_task is not None
    assert install_task.progress_type == ProgressType.INSTALLATION
    assert install_task.name == "MyApp"
    assert install_task.description == "Installing MyApp"
    assert install_task.phase == 2
    assert install_task.total_phases == 2
    assert install_task.parent_task_id == verify_id

    await progress.stop_session()


@pytest.mark.asyncio
async def test_workflow_helper_installation_without_verification() -> None:
    """Test create_installation_workflow without verification phase."""
    progress = ProgressDisplay()
    await progress.start_session()

    verify_id, install_id = await create_installation_workflow(
        progress, "MyApp", with_verification=False
    )

    assert verify_id is None
    assert install_id is not None

    # Check installation task is single phase
    install_task = progress.get_task_info_full(install_id)
    assert install_task is not None
    assert install_task.progress_type == ProgressType.INSTALLATION
    assert install_task.phase == 1
    assert install_task.total_phases == 1
    assert install_task.parent_task_id is None

    await progress.stop_session()
