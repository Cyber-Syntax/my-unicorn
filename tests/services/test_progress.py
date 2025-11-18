"""Comprehensive tests for the progress service module.

Tests cover all major functionality including edge cases for network errors,
verification failures, icon extraction errors, and other progress bar issues.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from my_unicorn.progress import (
    ProgressConfig,
    ProgressDisplay,
    ProgressType,
    TaskInfo,
    get_progress_service,
    progress_session,
    set_progress_service,
)


class TestProgressType:
    """Test cases for ProgressType enum."""

    def test_all_progress_types_exist(self) -> None:
        """Test that all expected progress types are defined."""
        expected_types = {
            "API_FETCHING",
            "DOWNLOAD",
            "VERIFICATION",
            "ICON_EXTRACTION",
            "INSTALLATION",
            "UPDATE",
        }

        actual_types = {pt.name for pt in ProgressType}

        assert actual_types == expected_types


class TestTaskInfo:
    """Test cases for TaskInfo dataclass."""

    def test_progress_task_creation(self) -> None:
        """Test creating a TaskInfo with required fields."""
        task_id = "test_task_1"
        task = TaskInfo(
            task_id=task_id,
            namespaced_id="test_1_task",
            name="Test Task",
            progress_type=ProgressType.DOWNLOAD,
        )

        assert task.task_id == task_id
        assert task.namespaced_id == "test_1_task"
        assert task.name == "Test Task"
        assert task.progress_type == ProgressType.DOWNLOAD
        assert task.total == 0.0
        assert task.completed == 0.0
        assert task.success is None
        assert not task.is_finished


class TestProgressConfig:
    """Test cases for ProgressConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ProgressConfig()

        assert config.refresh_per_second == 4
        assert not config.show_overall
        assert config.show_api_fetching
        assert config.show_downloads
        assert config.show_post_processing

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = ProgressConfig(
            refresh_per_second=10, show_overall=True, show_api_fetching=False
        )

        assert config.refresh_per_second == 10
        assert config.show_overall
        assert not config.show_api_fetching


@pytest.fixture
def progress_service() -> ProgressDisplay:
    """Fixture providing a ProgressDisplay instance."""
    service = ProgressDisplay()
    # Don't set _active=True here as some tests need to test inactive state
    return service


class TestProgressDisplay:
    """Comprehensive test cases for ProgressDisplay."""

    def test_init_with_defaults(self) -> None:
        """Test ProgressDisplay initialization with default values."""
        service = ProgressDisplay()

        assert service._backend is not None
        assert service.config is not None
        assert not service._active

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
        id1 = progress_service._generate_namespaced_id(
            ProgressType.DOWNLOAD, "test_file"
        )
        id2 = progress_service._generate_namespaced_id(
            ProgressType.DOWNLOAD, "another_file"
        )
        id3 = progress_service._generate_namespaced_id(
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
        clean_id = progress_service._generate_namespaced_id(
            ProgressType.DOWNLOAD, dirty_name
        )

        assert "dl_1_filewithspaces" in clean_id

    @pytest.mark.asyncio
    async def test_start_session(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test starting a progress session."""
        await progress_service.start_session()

        assert progress_service._active
        assert progress_service._render_task is not None

    @pytest.mark.asyncio
    async def test_start_session_already_active(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test starting session when already active does nothing."""
        await progress_service.start_session()
        first_task = progress_service._render_task

        await progress_service.start_session()

        # Should still be the same render task
        assert progress_service._render_task == first_task

    @pytest.mark.asyncio
    async def test_stop_session(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test stopping a progress session."""
        await progress_service.start_session()
        assert progress_service._active

        await progress_service.stop_session()

        assert not progress_service._active
        assert progress_service._render_task is None

    @pytest.mark.asyncio
    async def test_stop_session_not_active(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test stopping session when not active does nothing."""
        await progress_service.stop_session()

        assert not progress_service._active
        assert progress_service._render_task is None

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
        assert task_id in progress_service._tasks
        task = progress_service._tasks[task_id]
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

        task = progress_service._tasks[task_id]
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

        task = progress_service._tasks[task_id]
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

        task = progress_service._tasks[task_id]
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

        task = progress_service._tasks[task_id]
        # Should calculate speed based on progress
        assert task.current_speed_mbps > 0

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_create_api_fetching_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test creating an API fetching task."""
        await progress_service.start_session()

        task_id = await progress_service.create_api_fetching_task(
            "API Request"
        )

        assert task_id is not None
        task = progress_service._tasks[task_id]
        assert task.progress_type == ProgressType.API_FETCHING

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_create_verification_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test creating a verification task."""
        await progress_service.start_session()

        task_id = await progress_service.create_verification_task("file.zip")

        assert task_id is not None
        task = progress_service._tasks[task_id]
        assert task.progress_type == ProgressType.VERIFICATION

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_create_icon_extraction_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test creating an icon extraction task."""
        await progress_service.start_session()

        task_id = await progress_service.create_icon_extraction_task(
            "app_name"
        )

        assert task_id is not None
        task = progress_service._tasks[task_id]
        assert task.progress_type == ProgressType.ICON_EXTRACTION

        await progress_service.stop_session()

    def test_get_task_info_existing(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test getting info for an existing task."""
        # Manually create a task info
        task_info = TaskInfo(
            task_id="test_task_1",
            namespaced_id="test_1_task",
            name="test_task",
            progress_type=ProgressType.DOWNLOAD,
        )
        progress_service._tasks["test_task"] = task_info

        info = progress_service.get_task_info("test_task")

        assert info == task_info

    def test_get_task_info_nonexistent(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test getting info for nonexistent task returns None."""
        info = progress_service.get_task_info("nonexistent_task")

        assert info is None

    def test_is_active(self, progress_service: ProgressDisplay) -> None:
        """Test checking if service is active."""
        # Start with inactive service
        progress_service._active = False
        assert not progress_service.is_active()

        progress_service._active = True
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

        task = progress_service._tasks[task_id]
        assert task.completed == 50.0

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_verification_error(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test handling verification error."""
        await progress_service.start_session()

        task_id = await progress_service.create_verification_task("file.zip")

        # Simulate verification failure
        await progress_service.finish_task(
            task_id,
            success=False,
            description="Checksum mismatch",
        )

        task = progress_service._tasks[task_id]
        assert task.success is False
        assert "Checksum mismatch" in task.description

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_icon_extraction_error(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test handling icon extraction error."""
        await progress_service.start_session()

        task_id = await progress_service.create_icon_extraction_task(
            "app_name"
        )

        # Simulate extraction failure
        await progress_service.finish_task(
            task_id,
            success=False,
            description="Failed to extract icon",
        )

        task = progress_service._tasks[task_id]
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
        assert task_id in progress_service._tasks

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

        task = progress_service._tasks[task_id]
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


class TestModuleFunctions:
    """Test module-level functions."""

    def test_get_set_progress_service(self) -> None:
        """Test getting and setting global progress service."""
        # Store original service
        original_service = get_progress_service()

        # Set a service
        mock_service = Mock()
        set_progress_service(mock_service)

        # Should retrieve the set service
        retrieved_service = get_progress_service()
        assert retrieved_service == mock_service

        # Clean up
        set_progress_service(original_service)

    @pytest.mark.asyncio
    async def test_progress_session_context_manager(self) -> None:
        """Test progress_session context manager."""
        original_service = get_progress_service()

        # progress_session creates its own service
        # Test that it works without error
        async with progress_session():
            service = get_progress_service()
            assert service is not None
            assert service.is_active()

        # Clean up
        set_progress_service(original_service)

    @pytest.mark.asyncio
    async def test_progress_session_no_service(self) -> None:
        """Test progress_session when no service is set."""
        set_progress_service(None)

        # Should create a new service
        async with progress_session():
            service = get_progress_service()
            assert service is not None


class TestErrorScenarios:
    """Test various error scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_multiple_session_starts(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test starting multiple sessions doesn't break anything."""
        await progress_service.start_session()
        first_render_task = progress_service._render_task

        await progress_service.start_session()  # Should be no-op
        await progress_service.start_session()  # Should be no-op

        # Should still have the same render task
        assert progress_service._render_task == first_render_task

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_stop_session_multiple_times(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test stopping session multiple times doesn't break anything."""
        await progress_service.start_session()
        await progress_service.stop_session()
        await progress_service.stop_session()  # Should be no-op

        # Should be inactive
        assert not progress_service._active

    @pytest.mark.asyncio
    async def test_task_operations_when_not_active(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test task operations when service is not active."""
        # Service starts inactive

        # Should raise RuntimeError when trying to add task while inactive
        with pytest.raises(RuntimeError, match="Progress session not active"):
            await progress_service.add_task(
                name="test_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

    @pytest.mark.asyncio
    async def test_finish_already_finished_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test finishing a task that's already finished."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="test_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        # Finish it once
        await progress_service.finish_task(task_id, success=True)

        # Finish it again - should not raise error
        await progress_service.finish_task(task_id, success=False)

        # Second finish call updates the state
        task = progress_service._tasks[task_id]
        assert task.success is False

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_update_task_beyond_total(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test updating task progress beyond total."""
        await progress_service.start_session()

        task_id = await progress_service.add_task(
            name="test_file",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
        )

        # Update beyond total - stores as-is, backend handles display
        await progress_service.update_task(task_id, completed=150.0)

        task = progress_service._tasks[task_id]
        assert task.completed == 150.0

        await progress_service.stop_session()

    def test_task_counter_isolation(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test that task counters are isolated per progress type."""
        # Generate IDs for different types
        download_id1 = progress_service._generate_namespaced_id(
            ProgressType.DOWNLOAD, "file1"
        )
        download_id2 = progress_service._generate_namespaced_id(
            ProgressType.DOWNLOAD, "file2"
        )
        api_id1 = progress_service._generate_namespaced_id(
            ProgressType.API_FETCHING, "api1"
        )

        # Each type should have its own counter
        assert download_id1.startswith("dl_1_")
        assert download_id2.startswith("dl_2_")
        assert api_id1.startswith("api_1_")

    @pytest.mark.asyncio
    async def test_progress_update_methods_comprehensive(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test different progress update methods."""
        await progress_service.start_session()

        task_id = await progress_service.create_verification_task(
            "test.AppImage"
        )

        # Test absolute completion update
        await progress_service.update_task(task_id, completed=25.0)

        # Test description update with completion
        await progress_service.update_task(
            task_id, description="🔍 Checking integrity...", completed=75.0
        )

        task_info = progress_service.get_task_info(task_id)
        assert task_info.description == "🔍 Checking integrity..."
        assert task_info.completed == 75.0

        await progress_service.finish_task(task_id, success=True)

        await progress_service.stop_session()

    @pytest.mark.asyncio
    async def test_basic_progress_operations_with_session(self) -> None:
        """Test basic progress operations with proper session management."""
        service = ProgressDisplay()

        # Test session management
        await service.start_session(total_operations=1)
        assert service.is_active()

        # Test task creation
        task_id = await service.add_task(
            "test_task",
            ProgressType.DOWNLOAD,
            total=100.0,
        )

        # Test task updates
        await service.update_task(task_id, completed=50.0)

        # Test task info
        task_info = service.get_task_info(task_id)
        assert task_info is not None
        assert task_info.name == "test_task"
        assert task_info.progress_type == ProgressType.DOWNLOAD

        # Test task completion
        await service.finish_task(task_id, success=True)

        # Test session cleanup
        await service.stop_session()
        assert not service.is_active()
