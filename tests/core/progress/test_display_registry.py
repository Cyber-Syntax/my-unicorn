"""Tests for TaskRegistry module.

Tests cover task storage, retrieval, state management, and thread safety.
"""

import asyncio
import time

import pytest

from my_unicorn.core.progress.display_registry import TaskRegistry
from my_unicorn.core.progress.progress_types import (
    ProgressType,
    TaskConfig,
    TaskInfo,
)


@pytest.mark.asyncio
async def test_task_registry_add_task_info() -> None:
    """Test adding task info to registry."""
    registry = TaskRegistry()

    # Create a task config and info
    config = TaskConfig(
        name="Download Task",
        progress_type=ProgressType.DOWNLOAD,
        total=1000.0,
    )
    task_info = TaskInfo(
        task_id="task_1",
        namespaced_id="task_1",
        name=config.name,
        progress_type=config.progress_type,
        total=config.total,
        created_at=time.monotonic(),
    )

    # Add task
    await registry.add_task_info("task_1", task_info)

    # Verify it was added
    retrieved = await registry.get_task_info_full("task_1")
    assert retrieved is not None
    assert retrieved.task_id == "task_1"
    assert retrieved.name == "Download Task"


@pytest.mark.asyncio
async def test_get_task_info_existing() -> None:
    """Test retrieving existing task info."""

    registry = TaskRegistry()

    # Create and add task
    task_info = TaskInfo(
        task_id="task_1",
        namespaced_id="task_1",
        name="Test Task",
        progress_type=ProgressType.DOWNLOAD,
        total=500.0,
        completed=250.0,
        description="Test description",
        created_at=time.monotonic(),
    )
    await registry.add_task_info("task_1", task_info)

    # Retrieve via get_task_info (dict format)
    info_dict = await registry.get_task_info("task_1")

    assert info_dict["completed"] == 250.0
    assert info_dict["total"] == 500.0
    assert info_dict["description"] == "Test description"


@pytest.mark.asyncio
async def test_get_task_info_nonexistent() -> None:
    """Test retrieving nonexistent task returns defaults."""

    registry = TaskRegistry()

    # Try to retrieve nonexistent task
    info_dict = await registry.get_task_info("nonexistent")

    # Should return default values
    assert info_dict == {"completed": 0.0, "total": None, "description": ""}


@pytest.mark.asyncio
async def test_get_task_info_full_existing() -> None:
    """Test retrieving full TaskInfo object."""

    registry = TaskRegistry()

    # Create and add task
    task_info = TaskInfo(
        task_id="task_2",
        namespaced_id="task_2",
        name="Full Info Task",
        progress_type=ProgressType.VERIFICATION,
        total=100.0,
        completed=50.0,
        phase=2,
        total_phases=3,
        created_at=time.monotonic(),
    )
    await registry.add_task_info("task_2", task_info)

    # Retrieve full TaskInfo
    retrieved = await registry.get_task_info_full("task_2")

    assert retrieved is not None
    assert retrieved.name == "Full Info Task"
    assert retrieved.phase == 2
    assert retrieved.total_phases == 3


@pytest.mark.asyncio
async def test_get_task_info_full_nonexistent() -> None:
    """Test retrieving full TaskInfo for nonexistent task returns None."""

    registry = TaskRegistry()

    # Try to retrieve nonexistent task
    retrieved = await registry.get_task_info_full("nonexistent")

    assert retrieved is None


@pytest.mark.asyncio
async def test_update_task() -> None:
    """Test updating task info."""

    registry = TaskRegistry()

    # Create and add task
    task_info = TaskInfo(
        task_id="task_3",
        namespaced_id="task_3",
        name="Update Test",
        progress_type=ProgressType.DOWNLOAD,
        total=1000.0,
        completed=0.0,
        created_at=time.monotonic(),
    )
    await registry.add_task_info("task_3", task_info)

    # Update task with new completed value
    updated = await registry.update_task("task_3", completed=500.0)

    assert updated is not None
    assert updated.completed == 500.0
    assert updated.total == 1000.0

    # Verify it was actually updated in registry
    retrieved = await registry.get_task_info_full("task_3")
    assert retrieved is not None
    assert retrieved.completed == 500.0


@pytest.mark.asyncio
async def test_update_task_nonexistent() -> None:
    """Test updating nonexistent task returns None."""

    registry = TaskRegistry()

    # Try to update nonexistent task
    updated = await registry.update_task("nonexistent", completed=100.0)

    assert updated is None


@pytest.mark.asyncio
async def test_update_task_multiple_fields() -> None:
    """Test updating multiple fields at once."""

    registry = TaskRegistry()

    # Create and add task
    task_info = TaskInfo(
        task_id="task_4",
        namespaced_id="task_4",
        name="Multi Update",
        progress_type=ProgressType.DOWNLOAD,
        total=1000.0,
        created_at=time.monotonic(),
    )
    await registry.add_task_info("task_4", task_info)

    # Update multiple fields
    updated = await registry.update_task(
        "task_4",
        completed=750.0,
        description="Updated description",
        current_speed_mbps=5.5,
    )

    assert updated is not None
    assert updated.completed == 750.0
    assert updated.description == "Updated description"
    assert updated.current_speed_mbps == 5.5


@pytest.mark.asyncio
async def test_finish_task() -> None:
    """Test finishing a task."""

    registry = TaskRegistry()

    # Create and add task
    task_info = TaskInfo(
        task_id="task_5",
        namespaced_id="task_5",
        name="Finish Test",
        progress_type=ProgressType.DOWNLOAD,
        total=1000.0,
        completed=1000.0,
        created_at=time.monotonic(),
    )
    await registry.add_task_info("task_5", task_info)

    # Finish task with success
    await registry.finish_task("task_5", success=True)

    # Verify task is marked as finished
    retrieved = await registry.get_task_info_full("task_5")
    assert retrieved is not None
    assert retrieved.is_finished is True
    assert retrieved.success is True


@pytest.mark.asyncio
async def test_finish_task_with_failure() -> None:
    """Test finishing a task with failure."""

    registry = TaskRegistry()

    # Create and add task
    task_info = TaskInfo(
        task_id="task_6",
        namespaced_id="task_6",
        name="Fail Test",
        progress_type=ProgressType.VERIFICATION,
        total=500.0,
        created_at=time.monotonic(),
    )
    await registry.add_task_info("task_6", task_info)

    # Finish task with failure
    await registry.finish_task("task_6", success=False)

    # Verify task is marked as failed
    retrieved = await registry.get_task_info_full("task_6")
    assert retrieved is not None
    assert retrieved.is_finished is True
    assert retrieved.success is False


@pytest.mark.asyncio
async def test_finish_task_nonexistent() -> None:
    """Test finishing nonexistent task is safe."""

    registry = TaskRegistry()

    # Should not raise an error
    await registry.finish_task("nonexistent", success=True)


@pytest.mark.asyncio
async def test_concurrent_access() -> None:
    """Test async lock protects against concurrent modifications."""

    registry = TaskRegistry()

    # Create initial task
    task_info = TaskInfo(
        task_id="task_7",
        namespaced_id="task_7",
        name="Concurrent Test",
        progress_type=ProgressType.DOWNLOAD,
        total=1000.0,
        created_at=time.monotonic(),
    )
    await registry.add_task_info("task_7", task_info)

    # Run multiple concurrent updates
    async def update_multiple() -> None:
        for i in range(10):
            await registry.update_task("task_7", completed=float(i * 100))

    # Run updates concurrently
    await asyncio.gather(
        update_multiple(),
        update_multiple(),
        update_multiple(),
    )

    # Final state should be consistent
    final = await registry.get_task_info_full("task_7")
    assert final is not None
    # Task should have a valid completed value (last one wins)
    assert 0 <= final.completed <= 1000.0


@pytest.mark.asyncio
async def test_task_registry_multiple_types() -> None:
    """Test managing multiple tasks of different types."""

    registry = TaskRegistry()

    # Add tasks of different types
    types_and_names = [
        (ProgressType.DOWNLOAD, "Download 1"),
        (ProgressType.VERIFICATION, "Verify 1"),
        (ProgressType.INSTALLATION, "Install 1"),
        (ProgressType.DOWNLOAD, "Download 2"),
    ]

    for idx, (ptype, name) in enumerate(types_and_names):
        task_info = TaskInfo(
            task_id=f"task_{idx}",
            namespaced_id=f"task_{idx}",
            name=name,
            progress_type=ptype,
            created_at=time.monotonic(),
        )
        await registry.add_task_info(f"task_{idx}", task_info)

    # Verify all tasks are stored
    for idx in range(len(types_and_names)):
        retrieved = await registry.get_task_info_full(f"task_{idx}")
        assert retrieved is not None
        assert retrieved.name == types_and_names[idx][1]


@pytest.mark.asyncio
async def test_task_registry_add_to_task_sets() -> None:
    """Test that tasks are added to appropriate type sets."""

    registry = TaskRegistry()

    # Add tasks of same type
    for i in range(3):
        task_info = TaskInfo(
            task_id=f"download_{i}",
            namespaced_id=f"download_{i}",
            name=f"Download {i}",
            progress_type=ProgressType.DOWNLOAD,
            created_at=time.monotonic(),
        )
        await registry.add_task_info(f"download_{i}", task_info)

    # Verify all are in the download task set
    download_set = await registry.get_task_set(ProgressType.DOWNLOAD)
    assert len(download_set) == 3
    assert "download_0" in download_set
    assert "download_1" in download_set
    assert "download_2" in download_set


@pytest.mark.asyncio
async def test_update_task_preserves_other_fields() -> None:
    """Test that updating one field doesn't affect others."""

    registry = TaskRegistry()

    # Create task with multiple fields
    task_info = TaskInfo(
        task_id="task_8",
        namespaced_id="task_8",
        name="Preserve Test",
        progress_type=ProgressType.DOWNLOAD,
        total=1000.0,
        completed=100.0,
        description="Original",
        phase=1,
        total_phases=3,
        created_at=time.monotonic(),
    )
    await registry.add_task_info("task_8", task_info)

    # Update only completed
    updated = await registry.update_task("task_8", completed=500.0)

    assert updated is not None
    assert updated.completed == 500.0
    assert updated.total == 1000.0
    assert updated.description == "Original"
    assert updated.phase == 1
    assert updated.total_phases == 3
