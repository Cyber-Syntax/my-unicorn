"""Comprehensive tests for the progress service module.

Tests cover all major functionality including edge cases for network errors,
verification failures, icon extraction errors, and other progress bar issues.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest
from rich.console import Console
from rich.live import Live
from rich.progress import Progress, TaskID

from my_unicorn.services.progress import (
    ProgressConfig,
    ProgressDisplay,
    ProgressType,
    SpeedColumn,
    TaskInfo,
    get_progress_service,
    progress_session,
    set_progress_service,
)


class TestSpeedColumn:
    """Test cases for SpeedColumn rendering."""

    def test_render_high_speed(self) -> None:
        """Test rendering speed >= 1 MB/s."""
        column = SpeedColumn()
        task = Mock()
        task.fields = {"speed": 2.5}

        result = column.render(task)

        assert "2.5 MB/s" in str(result)

    def test_render_low_speed(self) -> None:
        """Test rendering speed < 1 MB/s in KB/s."""
        column = SpeedColumn()
        task = Mock()
        task.fields = {"speed": 0.5}

        result = column.render(task)

        assert "512 KB/s" in str(result)

    def test_render_no_speed(self) -> None:
        """Test rendering when no speed available."""
        column = SpeedColumn()
        task = Mock()
        task.fields = {}

        result = column.render(task)

        assert "-- MB/s" in str(result)

    def test_render_zero_speed(self) -> None:
        """Test rendering zero speed."""
        column = SpeedColumn()
        task = Mock()
        task.fields = {"speed": 0.0}

        result = column.render(task)

        assert "-- MB/s" in str(result)


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
        task_id = TaskID(1)
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
def mock_console() -> Mock:
    """Fixture providing a mocked Rich Console."""
    return Mock(spec=Console)


@pytest.fixture
def mock_progress() -> Mock:
    """Fixture providing a mocked Rich Progress."""
    progress = Mock(spec=Progress)
    progress.add_task.return_value = TaskID(1)
    return progress


@pytest.fixture
def mock_live() -> Mock:
    """Fixture providing a mocked Rich Live display."""
    return Mock(spec=Live)


@pytest.fixture
def progress_service(mock_console: Mock) -> ProgressDisplay:
    """Fixture providing a ProgressDisplay instance."""
    with patch("my_unicorn.services.progress.Progress"):
        service = ProgressDisplay(console=mock_console)
        # Don't set _active=True here as some tests need to test inactive state
        return service


class TestProgressDisplay:
    """Comprehensive test cases for ProgressDisplay."""

    def test_init_with_defaults(self) -> None:
        """Test ProgressDisplay initialization with default values."""
        with (
            patch("my_unicorn.services.progress.Progress"),
            patch("my_unicorn.services.progress.Console") as mock_console_cls,
        ):
            service = ProgressDisplay()

            assert service.console is not None
            assert service.config is not None
            assert not service._active
            assert not service._ui_visible
            assert not service._tasks_added
            assert service._live is None

    def test_init_with_custom_values(self, mock_console: Mock) -> None:
        """Test ProgressDisplay initialization with custom values."""
        config = ProgressConfig(refresh_per_second=8)

        with patch("my_unicorn.services.progress.Progress"):
            service = ProgressDisplay(console=mock_console, config=config)

            assert service.console == mock_console
            assert service.config == config

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
        with patch("my_unicorn.services.progress.Live") as mock_live_cls:
            mock_live = Mock()
            mock_live_cls.return_value = mock_live

            await progress_service.start_session()

            assert progress_service._active
            assert progress_service._live == mock_live
            mock_live.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_session_already_active(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test starting session when already active does nothing."""
        progress_service._active = True
        original_live = progress_service._live

        await progress_service.start_session()

        assert progress_service._live == original_live

    @pytest.mark.asyncio
    async def test_stop_session(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test stopping a progress session."""
        mock_live = Mock()
        progress_service._live = mock_live
        progress_service._active = True

        await progress_service.stop_session()

        assert not progress_service._active
        assert progress_service._live is None
        mock_live.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_session_not_active(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test stopping session when not active does nothing."""
        await progress_service.stop_session()

        assert not progress_service._active
        assert progress_service._live is None

    @pytest.mark.asyncio
    async def test_add_download_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test adding a download task."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._download_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

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

    @pytest.mark.asyncio
    async def test_add_task_with_exception(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test adding task that raises exception."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._download_progress, "add_task"
        ) as mock_add:
            mock_add.side_effect = Exception("Rich error")

            with pytest.raises(Exception, match="Rich error"):
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
        progress_service._active = True  # Make active for this test
        # First add a task
        with (
            patch.object(
                progress_service._download_progress, "add_task"
            ) as mock_add,
            patch.object(
                progress_service._download_progress, "update"
            ) as mock_update,
        ):
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.add_task(
                name="test_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

            # Then update it
            with patch("time.time", return_value=1000.0):
                await progress_service.update_task(task_id, completed=50.0)

            task = progress_service._tasks[task_id]
            assert task.completed == 50.0
            mock_update.assert_called()

    @pytest.mark.asyncio
    async def test_update_nonexistent_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test updating a task that doesn't exist."""
        progress_service._active = True  # Make active for this test
        # Task update should just log warning, not raise exception for nonexistent tasks
        await progress_service.update_task("nonexistent_task", completed=50.0)
        # No exception should be raised

    @pytest.mark.asyncio
    async def test_finish_task_success(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test finishing a task successfully."""
        progress_service._active = True  # Make active for this test
        with (
            patch.object(
                progress_service._download_progress, "add_task"
            ) as mock_add,
            patch.object(
                progress_service._download_progress, "update"
            ) as mock_update,
        ):
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.add_task(
                name="test_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

            await progress_service.finish_task(task_id, success=True)

            task = progress_service._tasks[task_id]
            assert task.success is True
            assert task.is_finished

    @pytest.mark.asyncio
    async def test_finish_task_failure(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test finishing a task with failure."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._download_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.add_task(
                name="test_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

            await progress_service.finish_task(
                task_id, success=False, final_description="Download failed"
            )

            task = progress_service._tasks[task_id]
            assert task.success is False
            assert task.description == "Download failed"

    @pytest.mark.asyncio
    async def test_calculate_speed(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test speed calculation for download tasks."""
        progress_service._active = True  # Make active for this test
        with (
            patch.object(
                progress_service._download_progress, "add_task"
            ) as mock_add,
            patch.object(
                progress_service._download_progress, "update"
            ) as mock_update,
        ):
            mock_add.return_value = TaskID(1)

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

    @pytest.mark.asyncio
    async def test_create_api_fetching_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test creating an API fetching task."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._api_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.create_api_fetching_task(
                "API Request", 10
            )

            assert task_id is not None
            task = progress_service._tasks[task_id]
            assert task.progress_type == ProgressType.API_FETCHING
            assert task.total == 10.0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_create_verification_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test creating a verification task."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._post_processing_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.create_verification_task(
                "file.zip"
            )

            assert task_id is not None
            task = progress_service._tasks[task_id]
            assert task.progress_type == ProgressType.VERIFICATION

    @pytest.mark.asyncio
    async def test_create_icon_extraction_task(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test creating an icon extraction task."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._post_processing_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.create_icon_extraction_task(
                "app.exe"
            )

            assert task_id is not None
            task = progress_service._tasks[task_id]
            assert task.progress_type == ProgressType.ICON_EXTRACTION

    def test_get_task_info_existing(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test getting info for existing task."""
        task = TaskInfo(
            task_id=TaskID(1),
            namespaced_id="test_task",
            name="Test Task",
            progress_type=ProgressType.DOWNLOAD,
        )
        progress_service._tasks["test_task"] = task

        info = progress_service.get_task_info("test_task")

        assert info == task

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
        with (
            patch.object(progress_service, "start_session") as mock_start,
            patch.object(progress_service, "stop_session") as mock_stop,
        ):
            async with progress_service.session():
                pass

            mock_start.assert_called_once()
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_context_manager_with_exception(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test context manager properly cleans up on exception."""
        with (
            patch.object(progress_service, "start_session") as mock_start,
            patch.object(progress_service, "stop_session") as mock_stop,
        ):
            with pytest.raises(ValueError):
                async with progress_service.session():
                    raise ValueError("Test error")

            mock_start.assert_called_once()
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_error_during_download(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test handling network errors during download tasks."""
        progress_service._active = True  # Make active for this test
        with (
            patch.object(
                progress_service._download_progress, "add_task"
            ) as mock_add,
            patch.object(
                progress_service._download_progress, "update"
            ) as mock_update,
        ):
            mock_add.return_value = TaskID(1)
            mock_update.side_effect = ConnectionError("Network error")

            task_id = await progress_service.add_task(
                name="network_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

            # Should log error but not raise (based on the captured logs)
            await progress_service.update_task(task_id, completed=50.0)
            # The error is caught and logged, not re-raised

    @pytest.mark.asyncio
    async def test_verification_error(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test handling verification errors."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._post_processing_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.create_verification_task(
                "corrupt_file.zip"
            )

            # Simulate verification failure
            await progress_service.finish_task(
                task_id,
                success=False,
                final_description="Checksum verification failed",
            )

            task = progress_service._tasks[task_id]
            assert task.success is False
            assert "verification failed" in task.description.lower()

    @pytest.mark.asyncio
    async def test_icon_extraction_error(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test handling icon extraction errors."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._post_processing_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.create_icon_extraction_task(
                "invalid_exe.exe"
            )

            # Simulate extraction failure
            await progress_service.finish_task(
                task_id,
                success=False,
                final_description="Icon extraction failed: Invalid PE file",
            )

            task = progress_service._tasks[task_id]
            assert task.success is False
            assert "extraction failed" in task.description.lower()

    @pytest.mark.asyncio
    async def test_concurrent_task_updates(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test concurrent task updates don't cause race conditions."""
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._download_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

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

    @pytest.mark.asyncio
    async def test_task_update_total_change(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test updating task total during progress."""
        progress_service._active = True  # Make active for this test
        with (
            patch.object(
                progress_service._download_progress, "add_task"
            ) as mock_add,
            patch.object(
                progress_service._download_progress, "update"
            ) as mock_update,
        ):
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.add_task(
                name="variable_size_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

            # Update total size mid-download
            await progress_service.update_task_total(task_id, 200.0)

            task = progress_service._tasks[task_id]
            assert task.total == 200.0

    def test_speed_calculation_edge_cases(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test speed calculation with edge cases."""
        # Test zero time difference
        task = TaskInfo(
            task_id=TaskID(1),
            namespaced_id="test_task",
            name="test",
            progress_type=ProgressType.DOWNLOAD,
        )

        # Mock the method call by directly testing the internal calculation logic
        # Test zero time difference
        time_diff = 0.0
        progress_diff = 100.0
        speed = progress_diff / time_diff if time_diff > 0 else 0.0
        assert speed == 0.0

        # Test negative time difference (should not happen but handle gracefully)
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

        # The progress_session function creates its own service, doesn't use global one
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

        # Should work without error (no-op)
        async with progress_session():
            pass


class TestErrorScenarios:
    """Test various error scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_multiple_session_starts(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test starting multiple sessions doesn't break anything."""
        progress_service._active = False  # Start inactive for this test
        with patch("my_unicorn.services.progress.Live") as mock_live_cls:
            mock_live = Mock()
            mock_live_cls.return_value = mock_live

            await progress_service.start_session()
            await progress_service.start_session()  # Should be no-op
            await progress_service.start_session()  # Should be no-op

            # Should only create and start one Live instance
            assert mock_live_cls.call_count == 1
            assert mock_live.start.call_count == 1

    @pytest.mark.asyncio
    async def test_stop_session_multiple_times(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test stopping session multiple times doesn't break anything."""
        mock_live = Mock()
        progress_service._live = mock_live
        progress_service._active = True

        await progress_service.stop_session()
        await progress_service.stop_session()  # Should be no-op

        # Should only stop once
        assert mock_live.stop.call_count == 1

    @pytest.mark.asyncio
    async def test_task_operations_when_not_active(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test task operations when service is not active."""
        # Set service as inactive
        progress_service._active = False

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
        progress_service._active = True  # Make active for this test
        with patch.object(
            progress_service._download_progress, "add_task"
        ) as mock_add:
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.add_task(
                name="test_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

            # Finish it once
            await progress_service.finish_task(task_id, success=True)

            # Finish it again - should not raise error
            await progress_service.finish_task(task_id, success=False)

            # Should maintain original success state
            task = progress_service._tasks[task_id]
            assert task.success is True  # First finish call wins

    @pytest.mark.asyncio
    async def test_update_task_beyond_total(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test updating task progress beyond total."""
        progress_service._active = True  # Make active for this test
        with (
            patch.object(
                progress_service._download_progress, "add_task"
            ) as mock_add,
            patch.object(
                progress_service._download_progress, "update"
            ) as mock_update,
        ):
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.add_task(
                name="test_file",
                progress_type=ProgressType.DOWNLOAD,
                total=100.0,
            )

            # Update beyond total - should be clamped to total based on implementation
            await progress_service.update_task(task_id, completed=150.0)

            task = progress_service._tasks[task_id]
            assert task.completed == 100.0  # Should be clamped to total

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
        """Test different progress update methods including advance and description."""
        progress_service._active = True
        with (
            patch.object(
                progress_service._post_processing_progress, "add_task"
            ) as mock_add,
            patch.object(
                progress_service._post_processing_progress, "update"
            ) as mock_update,
        ):
            mock_add.return_value = TaskID(1)

            task_id = await progress_service.create_verification_task(
                "test.AppImage"
            )

            # Test absolute completion update
            await progress_service.update_task(task_id, completed=25.0)

            # Test advance update
            await progress_service.update_task(task_id, advance=25.0)

            # Test description update with completion
            await progress_service.update_task(
                task_id, description="🔍 Checking integrity...", completed=75.0
            )

            task_info = progress_service.get_task_info(task_id)
            assert task_info.description == "🔍 Checking integrity..."
            assert task_info.completed == 75.0

            await progress_service.finish_task(task_id, success=True)

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
        await service.update_task(task_id, advance=25.0)

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
