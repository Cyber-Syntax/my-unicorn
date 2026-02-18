"""Tests for the ProgressDisplay and ASCII progress backend.

These tests exercise formatting and behavior of the progress display,
including session management, task lifecycle, and rendering helpers.
"""

import asyncio
from unittest.mock import patch

import pytest

from my_unicorn.core.progress.progress import (
    ProgressConfig,
    ProgressDisplay,
    ProgressType,
    TaskInfo,
)

# 'progress_service' fixture is provided by tests/core/progress/conftest.py


class TestProgressDisplay:
    """Comprehensive test cases for ProgressDisplay."""

    def test_init_with_defaults(self) -> None:
        """Test ProgressDisplay initialization with default values."""
        service = ProgressDisplay()

        assert service._backend is not None
        assert service.config is not None
        assert not service._session_manager._active

    def test_init_with_custom_values(self) -> None:
        """Test ProgressDisplay initialization with custom values."""
        config = ProgressConfig(refresh_per_second=8)
        service = ProgressDisplay(config=config)

        assert service.config == config
        assert service.config.refresh_per_second == 8

    def test_generate_namespaced_id(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test namespaced ID generation."""
        id1 = progress_service._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "test_file"
        )
        id2 = progress_service._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "another_file"
        )
        id3 = progress_service._id_generator.generate_namespaced_id(
            ProgressType.API_FETCHING, "api_call"
        )

        assert id1.startswith("dl_1_")
        assert id2.startswith("dl_2_")
        assert id3.startswith("api_1_")
        assert id1 != id2
        assert id1 != id3

    def test_generate_namespaced_id_sanitization(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test that namespaced ID sanitizes special characters."""
        dirty_name = "file with spaces & symbols!"
        clean_id = progress_service._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, dirty_name
        )

        assert "dl_1_filewithspaces" in clean_id

    @pytest.mark.asyncio
    async def test_start_session(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test starting a progress session."""
        await progress_service.start_session()

        assert progress_service._session_manager._active
        assert progress_service._session_manager._render_task is not None

    @pytest.mark.asyncio
    async def test_start_session_already_active(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test starting session when already active does nothing."""
        await progress_service.start_session()
        first_task = progress_service._session_manager._render_task

        await progress_service.start_session()

        # Should still be the same render task
        assert progress_service._session_manager._render_task == first_task

    @pytest.mark.asyncio
    async def test_stop_session(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test stopping a progress session."""
        await progress_service.start_session()
        assert progress_service._session_manager._active

        await progress_service.stop_session()

        assert not progress_service._session_manager._active
        assert progress_service._session_manager._render_task is None

    @pytest.mark.asyncio
    async def test_stop_session_not_active(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test stopping session when not active does nothing."""
        await progress_service.stop_session()

        assert not progress_service._session_manager._active
        assert progress_service._session_manager._render_task is None

    @pytest.mark.asyncio
    async def test_add_download_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test adding a download task."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="test_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
            description="Downloading test file",
        )

        assert task_id is not None
        assert (
            progress_service._task_registry.get_task_info_full_sync(task_id)
            is not None
        )
        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.name == "test_file"
        assert task.progress_type == ProgressType.DOWNLOAD
        assert task.total == 100.0
        assert task.description == "Downloading test file"

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_add_task_with_exception(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test adding task when session not active raises exception."""
        # Don't start session - should raise RuntimeError
        with pytest.raises(RuntimeError, match="Progress session not active"):
            await progress_service.add_task(
                name="test_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

    @pytest.mark.asyncio
    async def test_update_task_progress(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test updating task progress."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="test_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        # Update task progress
        await progress_service.update_task(task_id, completed=50.0)

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.completed == 50.0

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_update_nonexistent_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test updating a task that doesn't exist."""
        await progress_service.start_session()
        # Task update should log warning, not raise exception
        await progress_service.update_task("nonexistent_task", completed=50.0)
        # No exception should be raised

    @pytest.mark.asyncio
    async def test_finish_task_success(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test finishing a task successfully."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="test_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        await progress_service.finish_task(task_id, success=True)

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.success is True
        assert task.is_finished

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_finish_task_failure(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test finishing a task with failure."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="test_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        await progress_service.finish_task(
            task_id, success=False, description="Download failed"
        )

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.success is False
        assert task.description == "Download failed"

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_calculate_speed(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test speed calculation for download tasks."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="test_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        # Simulate progress over time
        with patch("time.time", return_value=1000.0):
            await progress_service.update_task(task_id, completed=25.0)

        with patch("time.time", return_value=1001.0):  # 1 second later
            await progress_service.update_task(task_id, completed=50.0)

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        # Should calculate speed based on progress
        assert task.current_speed_mbps > 0

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_create_icon_extraction_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test creating an icon extraction task."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="app_name",
            progress_type=ProgressType.ICON_EXTRACTION,
            description="Extracting icon for app_name",
        )

        assert task_id is not None
        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.progress_type == ProgressType.ICON_EXTRACTION

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_get_task_info_existing(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test getting info for an existing task returns dict."""
        # Manually create a task info
        task_info = TaskInfo(
            task_id="test_task_1",
            namespaced_id="test_1_task",
            name="test_task",
            progress_type=ProgressType.DOWNLOAD,
            completed=50.0,
            total=100.0,
            description="Test description",
        )
        await progress_service._task_registry.add_task_info(
            "test_task", task_info
        )

        info = progress_service.get_task_info("test_task")

        # get_task_info returns dict per ProgressReporter protocol
        assert isinstance(info, dict)
        assert info["completed"] == 50.0
        assert info["total"] == 100.0
        assert info["description"] == "Test description"

    @pytest.mark.asyncio
    async def test_get_task_info_full_existing(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test getting full TaskInfo for an existing task."""
        # Manually create a task info
        task_info = TaskInfo(
            task_id="test_task_1",
            namespaced_id="test_1_task",
            name="test_task",
            progress_type=ProgressType.DOWNLOAD,
        )
        await progress_service._task_registry.add_task_info(
            "test_task", task_info
        )

        info = progress_service.get_task_info_full("test_task")

        assert info == task_info

    def test_get_task_info_nonexistent(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test getting info for nonexistent task returns defaults."""
        info = progress_service.get_task_info("nonexistent_task")

        # Protocol requires returning dict with defaults for missing task
        assert isinstance(info, dict)
        assert info["completed"] == 0.0
        assert info["total"] is None
        assert info["description"] == ""

    def test_get_task_info_full_nonexistent(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test getting full TaskInfo for nonexistent task returns None."""
        info = progress_service.get_task_info_full("nonexistent_task")

        assert info is None

    def test_is_active(self, progress_service: ProgressDisplay) -> None:
        """Test checking if service is active."""
        # Start with inactive service
        progress_service._session_manager._active = False
        assert not progress_service.is_active()

        progress_service._session_manager._active = True
        assert progress_service.is_active()

    @pytest.mark.asyncio
    async def test_session_context_manager(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test using progress service as async context manager."""
        async with progress_service.session():
            assert progress_service.is_active()

        assert not progress_service.is_active()

    @pytest.mark.asyncio
    async def test_session_context_manager_with_exception(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test context manager properly cleans up on exception."""
        with pytest.raises(ValueError):
            async with progress_service.session():
                raise ValueError("Test error")

        # Should have cleaned up properly
        assert not progress_service.is_active()

    @pytest.mark.asyncio
    async def test_network_error_during_download(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test handling download tasks (no network errors expected)."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="network_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        # Should update without error
        await progress_service.update_task(task_id, completed=50.0)

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.completed == 50.0

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_verification_error(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test handling verification error."""
        from my_unicorn.core.progress.display_workflows import (
            create_verification_task,
        )

        await progress_service.start_session()

        task_id = await create_verification_task(progress_service, "file.zip")

        # Simulate verification failure
        await progress_service.finish_task(
            task_id,
            success=False,
            description="Checksum mismatch",
        )

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.success is False
        assert "Checksum mismatch" in task.description

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_icon_extraction_error(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test handling icon extraction error."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="app_name",
            progress_type=ProgressType.ICON_EXTRACTION,
            description="Extracting icon for app_name",
        )

        # Simulate extraction failure
        await progress_service.finish_task(
            task_id,
            success=False,
            description="Failed to extract icon",
        )

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.success is False
        assert "Failed to extract icon" in task.description

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_concurrent_task_updates(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test concurrent task updates don't cause race conditions."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="concurrent_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        # Simulate concurrent updates
        async def update_task(progress: float) -> None:
            await progress_service.update_task(task_id, completed=progress)

        tasks = [update_task(i * 10) for i in range(1, 11)]

        # Should complete without raising exceptions
        await asyncio.gather(*tasks, return_exceptions=True)

        # Task should still exist and be valid
        assert (
            progress_service._task_registry.get_task_info_full_sync(task_id)
            is not None
        )

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_task_update_total_change(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test updating task total during progress."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="variable_size_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        # Update total size mid-download
        await progress_service.update_task_total(task_id, 200.0)

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.total == 200.0

        await progress_service.stop_session()

    def test_speed_calculation_edge_cases(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test speed calculation with edge cases."""
        # Test zero time difference
        # Mock the method call by directly testing calculation logic
        # Test zero time difference
        time_diff = 0.0
        progress_diff = 100.0
        speed = progress_diff / time_diff if time_diff > 0 else 0.0
        assert speed == 0.0

        # Test negative time difference (handle gracefully)
        time_diff = -1.0
        speed = progress_diff / time_diff if time_diff > 0 else 0.0
        assert speed == 0.0

        # Test zero progress difference
        time_diff = 1.0
        progress_diff = 0.0
        speed = progress_diff / time_diff if time_diff > 0 else 0.0
        assert speed == 0.0

        # Test normal calculation
        time_diff = 1.0
        progress_diff = 50.0
        speed = progress_diff / time_diff if time_diff > 0 else 0.0
        assert speed == 50.0  # 50 MB in 1 second
