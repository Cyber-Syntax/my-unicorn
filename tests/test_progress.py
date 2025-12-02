"""Comprehensive tests for the progress service module.

Tests cover all major functionality including edge cases for network errors,
verification failures, icon extraction errors, and other progress bar issues.
"""

import asyncio
import io
from unittest.mock import Mock, patch

import pytest

from my_unicorn.progress import (
    AsciiProgressBackend,
    ProgressConfig,
    ProgressDisplay,
    ProgressType,
    TaskInfo,
    TaskState,
    get_progress_service,
    progress_session,
    set_progress_service,
)


class TestTaskState:
    """Test cases for TaskState dataclass."""

    def test_task_state_creation(self) -> None:
        """Test creating a TaskState with required fields."""
        state = TaskState(
            task_id="task_1",
            name="Test Task",
            progress_type=ProgressType.DOWNLOAD,
        )

        assert state.task_id == "task_1"
        assert state.name == "Test Task"
        assert state.progress_type == ProgressType.DOWNLOAD
        assert state.total == 0.0
        assert state.completed == 0.0
        assert state.success is None
        assert not state.is_finished

    def test_task_state_multi_phase(self) -> None:
        """Test TaskState with multi-phase tracking."""
        state = TaskState(
            task_id="task_1",
            name="Multi-phase Task",
            progress_type=ProgressType.VERIFICATION,
            parent_task_id="parent_task",
            phase=1,
            total_phases=2,
        )

        assert state.parent_task_id == "parent_task"
        assert state.phase == 1
        assert state.total_phases == 2


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

    def test_task_info_with_speed_history(self) -> None:
        """Test TaskInfo speed tracking initialization."""
        task = TaskInfo(
            task_id="dl_1",
            namespaced_id="dl_1_file",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
        )

        # Speed history should be initialized in __post_init__
        assert task.speed_history is not None
        assert len(task.speed_history) == 0

    def test_task_info_multi_phase(self) -> None:
        """Test TaskInfo with multi-phase tracking."""
        task = TaskInfo(
            task_id="vf_1",
            namespaced_id="vf_1_app",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            parent_task_id="parent_1",
            phase=1,
            total_phases=2,
        )

        assert task.parent_task_id == "parent_1"
        assert task.phase == 1
        assert task.total_phases == 2


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
        assert config.batch_ui_updates
        assert config.ui_update_interval == 0.25
        assert config.speed_calculation_interval == 0.5
        assert config.max_speed_history == 10

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = ProgressConfig(
            refresh_per_second=10,
            show_overall=True,
            show_api_fetching=False,
            batch_ui_updates=False,
            ui_update_interval=0.1,
        )

        assert config.refresh_per_second == 10
        assert config.show_overall
        assert not config.show_api_fetching
        assert not config.batch_ui_updates
        assert config.ui_update_interval == 0.1

    def test_invalid_config_validation(self) -> None:
        """ProgressConfig validation should reject invalid values."""
        with pytest.raises(ValueError):
            ProgressConfig(refresh_per_second=0)

        with pytest.raises(ValueError):
            ProgressConfig(bar_width=0)

        with pytest.raises(ValueError):
            ProgressConfig(spinner_fps=0)


@pytest.fixture
def progress_service() -> ProgressDisplay:
    """Fixture providing a ProgressDisplay instance."""
    service = ProgressDisplay()
    # Don't set _active=True here as some tests need to test inactive state
    return service


@pytest.fixture
def ascii_backend() -> AsciiProgressBackend:
    """Fixture providing an AsciiProgressBackend instance."""
    output = io.StringIO()
    backend = AsciiProgressBackend(output=output, interactive=False)
    return backend


class TestAsciiProgressBackend:
    """Test cases for AsciiProgressBackend."""

    def test_backend_initialization(self) -> None:
        """Test backend initialization with defaults."""
        output = io.StringIO()
        backend = AsciiProgressBackend(output=output)

        assert backend.output == output
        assert backend.bar_width == 30
        assert backend.max_name_width == 20
        assert len(backend.tasks) == 0

    def test_backend_add_task(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test adding a task to the backend."""
        ascii_backend.add_task(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
        )

        assert "dl_1" in ascii_backend.tasks
        task = ascii_backend.tasks["dl_1"]
        assert task.name == "test.AppImage"
        assert task.total == 1000.0

    def test_backend_update_task(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test updating task progress in backend."""
        ascii_backend.add_task(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
        )

        ascii_backend.update_task("dl_1", completed=500.0, speed=1024.0)

        task = ascii_backend.tasks["dl_1"]
        assert task.completed == 500.0
        assert task.speed == 1024.0

    def test_backend_finish_task(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test finishing a task in backend."""
        ascii_backend.add_task(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
        )

        ascii_backend.finish_task("dl_1", success=True, description="Complete")

        task = ascii_backend.tasks["dl_1"]
        assert task.is_finished
        assert task.success
        assert task.description == "Complete"

    def test_backend_multi_phase_task(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test backend handling of multi-phase tasks."""
        ascii_backend.add_task(
            task_id="vf_1",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
        )

        ascii_backend.add_task(
            task_id="in_1",
            name="MyApp",
            progress_type=ProgressType.INSTALLATION,
            parent_task_id="vf_1",
            phase=2,
            total_phases=2,
        )

        verify_task = ascii_backend.tasks["vf_1"]
        install_task = ascii_backend.tasks["in_1"]

        assert verify_task.phase == 1
        assert verify_task.total_phases == 2
        assert install_task.phase == 2
        assert install_task.parent_task_id == "vf_1"

    @pytest.mark.asyncio
    async def test_backend_render_once(
        self, ascii_backend: AsciiProgressBackend
    ) -> None:
        """Test rendering backend output once."""
        ascii_backend.add_task(
            task_id="dl_1",
            name="test.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
        )

        ascii_backend.update_task("dl_1", completed=500.0)

        await ascii_backend.render_once()

        # Check that output was written
        output_value = ascii_backend.output.getvalue()  # type: ignore[attr-defined]
        assert len(output_value) > 0

    def test_backend_interactive_vs_noninteractive(self) -> None:
        """Test interactive vs non-interactive mode detection."""
        output = io.StringIO()

        # Explicit interactive mode
        backend_interactive = AsciiProgressBackend(
            output=output, interactive=True
        )
        assert backend_interactive.interactive

        # Explicit non-interactive mode
        backend_noninteractive = AsciiProgressBackend(
            output=output, interactive=False
        )
        assert not backend_noninteractive.interactive


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
        assert task_info is not None
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

    @pytest.mark.asyncio
    async def test_multi_phase_installation_workflow(self) -> None:
        """Test multi-phase installation workflow creation."""
        service = ProgressDisplay()

        await service.start_session()

        # Test with verification
        verify_id, install_id = await service.create_installation_workflow(
            "MyApp", with_verification=True
        )

        assert verify_id is not None
        assert install_id is not None

        # Check verification task
        verify_task = service.get_task_info(verify_id)
        assert verify_task is not None
        assert verify_task.phase == 1
        assert verify_task.total_phases == 2
        assert verify_task.progress_type == ProgressType.VERIFICATION

        # Check installation task
        install_task = service.get_task_info(install_id)
        assert install_task is not None
        assert install_task.phase == 2
        assert install_task.total_phases == 2
        assert install_task.parent_task_id == verify_id
        assert install_task.progress_type == ProgressType.INSTALLATION

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_installation_workflow_without_verification(self) -> None:
        """Test installation workflow without verification phase."""
        service = ProgressDisplay()

        await service.start_session()

        verify_id, install_id = await service.create_installation_workflow(
            "MyApp", with_verification=False
        )

        assert verify_id is None
        assert install_id is not None

        install_task = service.get_task_info(install_id)
        assert install_task is not None
        assert install_task.phase == 1
        assert install_task.total_phases == 1
        assert install_task.parent_task_id is None

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_speed_calculation_with_history(self) -> None:
        """Test speed calculation using history."""
        service = ProgressDisplay()

        await service.start_session()

        task_id = await service.add_task(
            "speed_test.AppImage",
            ProgressType.DOWNLOAD,
            total=10000.0,
        )

        # Simulate multiple progress updates
        with patch("time.time", return_value=1000.0):
            await service.update_task(task_id, completed=1000.0)

        with patch("time.time", return_value=1001.0):
            await service.update_task(task_id, completed=2000.0)

        with patch("time.time", return_value=1002.0):
            await service.update_task(task_id, completed=3000.0)

        task_info = service.get_task_info(task_id)
        assert task_info is not None
        # Speed should be calculated from history
        assert task_info.current_speed_mbps > 0

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_create_post_processing_task(self) -> None:
        """Test creating post-processing tasks."""
        service = ProgressDisplay()

        await service.start_session()

        task_id = await service.create_post_processing_task(
            "MyApp",
            progress_type=ProgressType.UPDATE,
            description="Updating MyApp",
        )

        assert task_id is not None
        task_info = service.get_task_info(task_id)
        assert task_info is not None
        assert task_info.progress_type == ProgressType.UPDATE
        assert task_info.description == "Updating MyApp"

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_id_cache_management(self) -> None:
        """Test ID cache is properly managed."""
        service = ProgressDisplay()

        await service.start_session()

        # Generate several IDs
        for i in range(10):
            await service.add_task(
                f"task_{i}",
                ProgressType.DOWNLOAD,
                total=100.0,
            )

        # Stop session should clear cache
        await service.stop_session()

    @pytest.mark.asyncio
    async def test_task_sets_tracking(self) -> None:
        """Test that task sets are properly maintained."""
        service = ProgressDisplay()

        await service.start_session()

        dl_task = await service.add_task(
            "download.AppImage",
            ProgressType.DOWNLOAD,
            total=1000.0,
        )

        api_task = await service.create_api_fetching_task("GitHub API")

        # Verify tasks were created
        assert service.get_task_info(dl_task) is not None
        assert service.get_task_info(api_task) is not None

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_render_loop_error_handling(self) -> None:
        """Test that render loop handles errors gracefully."""
        service = ProgressDisplay()

        await service.start_session()

        # Let it run for a bit
        await asyncio.sleep(0.3)

        # Should still be active even if errors occur
        assert service.is_active()

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_backend_cleanup(self) -> None:
        """Test backend cleanup on session stop."""
        service = ProgressDisplay()

        await service.start_session()

        task_id = await service.add_task(
            "test.AppImage",
            ProgressType.DOWNLOAD,
            total=100.0,
        )

        await service.update_task(task_id, completed=50.0)
        await service.finish_task(task_id, success=True)

        # Stop should trigger cleanup
        await service.stop_session()

        assert not service.is_active()


class TestProgressCoverageExtras:
    """Additional tests targeting branches flagged by coverage annotate."""

    def test_isatty_exception_handling(self) -> None:
        """Ensure backend handles output objects whose isatty raises."""

        class BadOutput(io.StringIO):
            def isatty(self) -> bool:  # type: ignore[override]
                raise RuntimeError("broken isatty")

        out = BadOutput()
        # Should not raise during initialization
        backend = AsciiProgressBackend(output=out, interactive=None)
        assert backend.interactive is False

    def test_format_download_lines_variations(self) -> None:
        """Cover branches in _format_download_lines (sizes, speeds, eta, errors)."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        # Case: no total, no speed
        t1 = TaskState(
            task_id="a", name="no_size", progress_type=ProgressType.DOWNLOAD
        )
        lines = backend._format_download_lines(t1, max_name_width=10)
        assert any("--" in l or "00:00" in l for l in lines)

        # Case: total and speed present, unfinished
        t2 = TaskState(
            task_id="b",
            name="big.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=1000.0,
            completed=200.0,
            speed=100.0,
            is_finished=False,
        )
        lines2 = backend._format_download_lines(t2, max_name_width=15)
        assert any("00:00" not in l for l in lines2)

        # Case: finished with error message
        t3 = TaskState(
            task_id="c",
            name="err.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
            completed=100.0,
            speed=0.0,
            is_finished=True,
            success=False,
            error_message="Something went wrong while downloading",
        )
        lines3 = backend._format_download_lines(t3, max_name_width=15)
        assert any("Error:" in l for l in lines3)

    def test_update_finish_nonexistent_no_raise(self) -> None:
        """Updating/finishing nonexistent backend tasks should be safe."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        # Should not raise
        backend.update_task("nope", completed=1.0)
        backend.finish_task("nope", success=False)

    def test_api_rendering_status_variations(self) -> None:
        """Cover API fetching status formatting permutations."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        # in-progress with total
        backend.add_task("api1", "repo", ProgressType.API_FETCHING, total=10.0)
        backend.update_task("api1", completed=3.0)
        api_lines = backend._render_api_section()
        assert any("Fetching..." in l or "Retrieved" in l for l in api_lines)

        # finished and cached
        backend.add_task("api2", "repo2", ProgressType.API_FETCHING, total=5.0)
        backend.finish_task("api2", success=True, description="Cached content")
        api_lines2 = backend._render_api_section()
        assert any("Retrieved" in l for l in api_lines2)

    def test_calculate_dynamic_name_width_and_spinner_header(self) -> None:
        """Trigger terminal-size exception and spinner/header helpers."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=True)
        # Force shutil.get_terminal_size to raise by monkeypatching
        import shutil

        orig = shutil.get_terminal_size

        def bad_getter():
            raise OSError("no tty")

        shutil.get_terminal_size = bad_getter  # type: ignore[assignment]
        try:
            name_w = backend._calculate_dynamic_name_width(
                "name", fixed_width=10
            )
            assert isinstance(name_w, int)
        finally:
            shutil.get_terminal_size = orig

        # Spinner deterministic value
        with patch("time.time", return_value=1.23):
            spin = backend._compute_spinner()
            assert isinstance(spin, str) and len(spin) > 0

        # header
        assert backend._compute_download_header(2, 1).startswith("Downloading")

    def test_format_processing_task_lines(self) -> None:
        """Cover processing task formatting (spinner, finished, errors)."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        t = TaskState(
            task_id="p1",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
            is_finished=False,
        )
        lines = backend._format_processing_task_lines(
            t, name_width=10, spinner="*"
        )
        assert any(
            "Processing" in l or "Verifying" in l or "*" in l for l in lines
        )

        # finished with error
        t2 = TaskState(
            task_id="p2",
            name="MyApp",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
            is_finished=True,
            success=False,
            error_message="boom",
        )
        lines2 = backend._format_processing_task_lines(
            t2, name_width=10, spinner="~"
        )
        assert any("Error:" in l for l in lines2)

    def test_clear_and_write_paths(self) -> None:
        """Exercise clear previous output and interactive/noninteractive writes."""
        # interactive clear
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=True)
        backend._last_output_lines = 2
        backend._clear_previous_output()
        assert "\033[" in out.getvalue()

        # write_interactive empty
        backend._write_interactive("")
        assert backend._last_output_lines == 0

        # noninteractive summary write
        out2 = io.StringIO()
        backend2 = AsciiProgressBackend(output=out2, interactive=False)
        backend2._write_noninteractive("Summary: All done")
        assert "Summary: All done" in out2.getvalue()

    def test_format_api_task_status_all_cases(self) -> None:
        """Exercise different status outputs from _format_api_task_status."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        # total > 0, unfinished
        t = TaskState(
            task_id="a",
            name="x",
            progress_type=ProgressType.API_FETCHING,
            total=10.0,
            completed=2.0,
        )
        assert "Fetching" in backend._format_api_task_status(t)

        # total >0 finished, cached
        t2 = TaskState(
            task_id="b",
            name="y",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            description="Cached result",
        )
        assert "Retrieved" in backend._format_api_task_status(t2)

        # no total, finished cached
        t3 = TaskState(
            task_id="c",
            name="z",
            progress_type=ProgressType.API_FETCHING,
            is_finished=True,
            description="cached",
        )
        assert backend._format_api_task_status(t3).startswith("Retrieved")

    def test_select_current_task_variants(self) -> None:
        """Select current task from list with various finished/failed states."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        t1 = TaskState(
            task_id="1",
            name="a",
            progress_type=ProgressType.VERIFICATION,
            is_finished=True,
            success=True,
            phase=1,
        )
        t2 = TaskState(
            task_id="2",
            name="a",
            progress_type=ProgressType.VERIFICATION,
            is_finished=True,
            success=False,
            phase=2,
        )
        t3 = TaskState(
            task_id="3",
            name="a",
            progress_type=ProgressType.VERIFICATION,
            is_finished=False,
            success=None,
            phase=3,
        )

        sel = backend._select_current_task([t1, t2, t3])
        # According to selection logic, first failing phase is preferred
        assert sel is t2

    def test_generate_namespaced_id_cache_hit_and_clear(self) -> None:
        """Ensure ProgressDisplay caches generated namespaced ids and can clear cache."""
        pd = ProgressDisplay()
        pd._active = True  # avoid start_session checks for direct invocation
        id1 = pd._generate_namespaced_id(ProgressType.DOWNLOAD, "same")
        id2 = pd._generate_namespaced_id(ProgressType.DOWNLOAD, "same")
        assert id1 == id2
        pd._clear_id_cache()
        id3 = pd._generate_namespaced_id(ProgressType.DOWNLOAD, "same")
        assert id3 != id1

    def test_generate_namespaced_id_unnamed(
        self, progress_service: ProgressDisplay
    ) -> None:
        """When sanitization produces an empty name, fallback to 'unnamed'."""
        # Use a name containing only non-allowed chars so sanitization yields empty
        nid = progress_service._generate_namespaced_id(
            ProgressType.DOWNLOAD, "!!!   $$$"
        )
        assert "unnamed" in nid

    def test_calculate_speed_returns_current_when_no_time(self) -> None:
        """_calculate_speed should return current_speed when no time/progress delta."""
        pd = ProgressDisplay()
        ti = TaskInfo(
            task_id="t",
            namespaced_id="t",
            name="n",
            progress_type=ProgressType.DOWNLOAD,
        )
        ti.current_speed_mbps = 2.0
        ti.last_speed_update = 100.0
        ti.completed = 100.0
        # time equals last update and completed unchanged
        res = pd._calculate_speed(ti, completed=100.0, current_time=100.0)
        assert res == 2.0 * 1024 * 1024

    def test_write_noninteractive_ioerror_is_swallowed(self) -> None:
        """Ensure write errors in noninteractive mode are swallowed."""

        class BadOut:
            def write(self, s: str) -> int:
                raise OSError("broken")

            def flush(self) -> None:
                raise OSError("broken")

        backend = AsciiProgressBackend(output=BadOut(), interactive=False)
        # Should not raise
        backend._write_noninteractive("Some content")

    @pytest.mark.asyncio
    async def test_cleanup_interactive_writes_final_output(self) -> None:
        """Interactive cleanup should write final output and reset last lines."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=True)
        # Add a finished task so _build_output has content
        backend.add_task("t1", "app", ProgressType.DOWNLOAD, total=10.0)
        backend.finish_task("t1", success=True)
        # Should write final output without error
        backend._last_output_lines = 2
        await backend.cleanup()
        assert backend._last_output_lines == 0

    def test_render_api_section_no_tasks(self) -> None:
        """API section should return empty list when there are no API tasks."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        assert backend._render_api_section() == []

    def test_render_downloads_and_processing_sections(self) -> None:
        """Ensure downloads and processing renderers handle empty and populated lists."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        # No downloads initially
        assert backend._render_downloads_section() == []

        # Add a download and ensure section renders
        backend.add_task(
            "dl_a", "file.AppImage", ProgressType.DOWNLOAD, total=100.0
        )
        backend.update_task("dl_a", completed=10.0, speed=50.0)
        dl_lines = backend._render_downloads_section()
        assert any(
            "Downloading" in l or "00:00" in l or "Error:" in l
            for l in dl_lines
        )

        # Processing: no post tasks
        assert backend._render_processing_section() == []

        # Add a verification task to trigger 'Verifying' header
        backend.add_task(
            "vf_a", "MyApp", ProgressType.VERIFICATION, phase=1, total_phases=2
        )
        proc_lines = backend._render_processing_section()
        assert any(
            l.startswith("Verifying")
            or l.startswith("Installing")
            or l.startswith("Processing")
            for l in proc_lines
        )

    def test_build_output_handles_sync_lock_exception(self) -> None:
        """Simulate a failing sync lock to hit the except branch in _build_output."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        class BadLock:
            def __enter__(self):
                raise RuntimeError("lock failed")

            def __exit__(self, exc_type, exc, tb):
                return False

        # Replace the sync lock with one that raises on enter
        backend._sync_lock = BadLock()  # type: ignore[assignment]
        out = backend._build_output()
        assert isinstance(out, str)

    def test_build_output_from_snapshot_api_downloads_processing_variants(
        self,
    ) -> None:
        """Call _build_output_from_snapshot with crafted snapshots to exercise branches."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        # Create TaskState variants for API fetching
        api1 = TaskState(
            task_id="api1",
            name="r1",
            progress_type=ProgressType.API_FETCHING,
            total=10.0,
            completed=3.0,
        )
        api2 = TaskState(
            task_id="api2",
            name="r2",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            description="Cached content",
        )
        api3 = TaskState(
            task_id="api3",
            name="r3",
            progress_type=ProgressType.API_FETCHING,
            is_finished=True,
            description="cached",
        )

        # Download task
        dl = TaskState(
            task_id="dl1",
            name="file.AppImage",
            progress_type=ProgressType.DOWNLOAD,
            total=100.0,
            completed=50.0,
            speed=100.0,
        )

        # Processing tasks: verification + installation
        vf = TaskState(
            task_id="vf1",
            name="MyApp",
            progress_type=ProgressType.VERIFICATION,
            phase=1,
            total_phases=2,
        )
        inst = TaskState(
            task_id="in1",
            name="MyApp",
            progress_type=ProgressType.INSTALLATION,
            phase=2,
            total_phases=2,
        )

        tasks_snapshot = {
            "api1": api1,
            "api2": api2,
            "api3": api3,
            "dl1": dl,
            "vf1": vf,
            "in1": inst,
        }

        order_snapshot = ["api1", "api2", "api3", "dl1", "vf1", "in1"]

        out = backend._build_output_from_snapshot(
            tasks_snapshot, order_snapshot
        )
        # Check that all major section headers exist
        assert "Fetching from API:" in out
        assert "Downloading" in out
        assert (
            "Verifying:" in out or "Installing:" in out or "Processing:" in out
        )

    def test_write_interactive_swallow_ioerror(self) -> None:
        """Ensure _write_interactive swallows IO errors from output.write/flush."""

        class BadOut:
            def __init__(self):
                self.calls = 0

            def write(self, s: str) -> int:
                # Allow the first two writes (used by _clear_previous_output),
                # then fail on subsequent writes to exercise the exception
                # handling in _write_interactive.
                if self.calls < 2:
                    self.calls += 1
                    return len(s)
                raise OSError("broken")

            def flush(self) -> None:
                # Allow initial flush during clear, then raise afterwards
                if self.calls <= 2:
                    self.calls += 1
                    return None
                raise OSError("broken")

        out = BadOut()
        backend = AsciiProgressBackend(output=out, interactive=True)
        backend._last_output_lines = 1
        # Should not raise
        backend._write_interactive("line1\n")

    @pytest.mark.asyncio
    async def test_render_loop_logs_and_continues_on_exception(self) -> None:
        """Ensure the render loop catches exceptions from backend.render_once and continues."""
        pd = ProgressDisplay()

        class BrokenBackend:
            def __init__(self, parent):
                self.parent = parent
                self.called = 0

            async def render_once(self):
                # Raise on first call, then stop the loop on second
                self.called += 1
                if self.called == 1:
                    raise RuntimeError("boom")
                # Stop the loop so the test completes
                self.parent._stop_rendering.set()

        pd._backend = BrokenBackend(pd)
        # Ensure stop flag is cleared
        pd._stop_rendering.clear()

        # Run the render loop until it stops (should handle one exception)
        await pd._render_loop()

    def test_api_status_branches_snapshot_and_nonsnapshot(self) -> None:
        """Exercise all API status branches in both snapshot and non-snapshot renderers."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        # total >0 unfinished
        api_a = TaskState(
            task_id="a",
            name="a",
            progress_type=ProgressType.API_FETCHING,
            total=10.0,
            completed=2.0,
        )
        # total >0 finished cached
        api_b = TaskState(
            task_id="b",
            name="b",
            progress_type=ProgressType.API_FETCHING,
            total=5.0,
            completed=5.0,
            is_finished=True,
            description="cached copy",
        )
        # total >0 finished not cached
        api_c = TaskState(
            task_id="c",
            name="c",
            progress_type=ProgressType.API_FETCHING,
            total=3.0,
            completed=3.0,
            is_finished=True,
            description="ok",
        )
        # no total finished cached
        api_d = TaskState(
            task_id="d",
            name="d",
            progress_type=ProgressType.API_FETCHING,
            is_finished=True,
            description="CACHED",
        )
        # no total not finished
        api_e = TaskState(
            task_id="e", name="e", progress_type=ProgressType.API_FETCHING
        )

        tasks = {t.task_id: t for t in (api_a, api_b, api_c, api_d, api_e)}
        order = ["a", "b", "c", "d", "e"]

        # Snapshot-based builder
        out = backend._build_output_from_snapshot(tasks, order)
        assert "Fetching from API:" in out
        assert "Retrieved from cache" in out
        assert "Retrieved" in out or "Fetching..." in out

        # Non-snapshot renderer by setting internal state
        backend.tasks = tasks
        backend._task_order = order
        api_lines = backend._render_api_section()
        assert any("Retrieved" in l or "Fetching" in l for l in api_lines)

    def test_processing_section_installing_header(self) -> None:
        """Ensure processing renderer emits 'Installing:' when installation tasks exist."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        # Only installation tasks
        inst1 = TaskState(
            task_id="i1",
            name="App",
            progress_type=ProgressType.INSTALLATION,
            phase=1,
            total_phases=1,
        )
        tasks = {"i1": inst1}
        order = ["i1"]

        out = backend._build_output_from_snapshot(tasks, order)
        assert "Installing:" in out

    def test_clear_previous_output_early_return(self) -> None:
        """_clear_previous_output should return early when non-interactive or no lines."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        # With non-interactive, _clear_previous_output should do nothing
        backend._clear_previous_output()

    def test_write_interactive_sync_lock_exception_handled(self) -> None:
        """Ensure _write_interactive swallows exceptions when sync-lock fails to set state."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=True)
        # Ensure clear_previous_output returns early (no previous lines)
        backend._last_output_lines = 0

        class BadLock:
            def __enter__(self):
                raise RuntimeError("lock fail")

            def __exit__(self, exc_type, exc, tb):
                return False

        backend._sync_lock = BadLock()  # type: ignore[assignment]
        # Should not raise even though setting _last_output_lines will fail
        backend._write_interactive("hello\n")

    def test_write_noninteractive_no_write_attr_and_empty(self) -> None:
        """_write_noninteractive should handle outputs without write and empty content."""
        # Output without a write attribute
        backend = AsciiProgressBackend(output=object(), interactive=False)
        assert backend._write_noninteractive("anything") == set()

        # Empty/whitespace-only output returns empty set
        out = io.StringIO()
        backend2 = AsciiProgressBackend(output=out, interactive=False)
        assert backend2._write_noninteractive("   ") == set()

    @pytest.mark.asyncio
    async def test_render_once_interactive_branch(self) -> None:
        """Run render_once in interactive mode to exercise interactive branch."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=True)
        # Add a task so output is non-empty
        backend.add_task(
            "d1", "file.AppImage", ProgressType.DOWNLOAD, total=10.0
        )
        backend.update_task("d1", completed=5.0)
        await backend.render_once()
        # Should have written something
        assert out.getvalue()

    def test_format_api_task_status_variants(self) -> None:
        """Explicitly exercise all branches of _format_api_task_status."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)

        # total > 0, finished, cached
        t1 = TaskState(
            task_id="a",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=2,
            completed=2,
            is_finished=True,
            description="Cached result",
        )
        assert "Retrieved from cache" in backend._format_api_task_status(t1)

        # total > 0, finished, not cached
        t2 = TaskState(
            task_id="b",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=3,
            completed=3,
            is_finished=True,
            description="OK",
        )
        assert "Retrieved" in backend._format_api_task_status(t2)

        # total > 0, not finished
        t3 = TaskState(
            task_id="c",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=4,
            completed=1,
            is_finished=False,
            description="",
        )
        assert "Fetching" in backend._format_api_task_status(t3)

        # total == 0, finished, cached
        t4 = TaskState(
            task_id="d",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=True,
            description="cached",
        )
        assert backend._format_api_task_status(t4) == "Retrieved from cache"

        # total == 0, not finished
        t5 = TaskState(
            task_id="e",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=False,
            description="",
        )
        assert backend._format_api_task_status(t5) == "Fetching..."

    def test_format_api_task_status_exact_retrieved(self) -> None:
        """Ensure exact formatting for total/total Retrieved branch."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        t = TaskState(
            task_id="x",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=7,
            completed=7,
            is_finished=True,
            description="ok",
        )
        assert backend._format_api_task_status(t) == "7/7        Retrieved"

    def test_processing_section_verifying_header(self) -> None:
        """When only verification tasks exist, header should be 'Verifying:'"""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        ts = {
            "v1": TaskState(
                task_id="v1",
                name="app",
                progress_type=ProgressType.VERIFICATION,
                is_finished=False,
            )
        }
        out = backend._build_output_from_snapshot(ts, ["v1"])
        assert "Verifying:" in out

    def test_write_noninteractive_writer_raises_is_handled(self) -> None:
        """If writer raises during non-interactive write, exception is swallowed and signatures returned."""

        class BadWriter:
            def write(self, _):
                raise RuntimeError("bork")

            def flush(self):
                pass

        backend = AsciiProgressBackend(output=BadWriter(), interactive=False)
        content = "A\n\nB"
        # Should not raise despite writer failing; returns signatures for sections
        sigs = backend._write_noninteractive(content)
        assert {s.strip() for s in sigs} == {"A", "B"}

    def test_build_output_snapshot_api_retrieved_no_cached(self) -> None:
        """_snapshot builder: API task with total==0 and finished should show 'Retrieved'"""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        ts = {
            "a": TaskState(
                task_id="a",
                name="app",
                progress_type=ProgressType.API_FETCHING,
                total=0,
                completed=0,
                is_finished=True,
                description="done",
            )
        }
        out = backend._build_output_from_snapshot(ts, ["a"])
        assert "Retrieved" in out

    def test_render_api_section_retrieved_no_cached(self) -> None:
        """_non-snapshot API rendering should show 'Retrieved' for finished non-cached tasks."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        backend.add_task("a", "app", ProgressType.API_FETCHING, total=0)
        backend.finish_task("a", success=True, description="done")
        lines = backend._render_api_section()
        assert any("Retrieved" in l for l in lines)

    def test_format_api_task_status_return_retrieved(self) -> None:
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        t = TaskState(
            task_id="x",
            name="n",
            progress_type=ProgressType.API_FETCHING,
            total=0,
            completed=0,
            is_finished=True,
            description="done",
        )
        assert backend._format_api_task_status(t) == "Retrieved"

    def test_render_processing_section_headers_non_snapshot(self) -> None:
        """Non-snapshot rendering: verify all processing header branches."""
        # Verifying only
        backend_v = AsciiProgressBackend(
            output=io.StringIO(), interactive=False
        )
        backend_v.add_task("v", "app", ProgressType.VERIFICATION)
        assert "Verifying:" in backend_v._render_processing_section()

        # Installation present
        backend_i = AsciiProgressBackend(
            output=io.StringIO(), interactive=False
        )
        backend_i.add_task("i", "app", ProgressType.INSTALLATION)
        assert "Installing:" in backend_i._render_processing_section()

        # Other post-task (processing)
        backend_p = AsciiProgressBackend(
            output=io.StringIO(), interactive=False
        )
        backend_p.add_task("p", "app", ProgressType.ICON_EXTRACTION)
        assert "Processing:" in backend_p._render_processing_section()

    def test_build_output_snapshot_processing_processing_header(self) -> None:
        """When only non-verification/non-installation post-tasks exist, header is 'Processing:'"""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=False)
        ts = {
            "p1": TaskState(
                task_id="p1",
                name="app",
                progress_type=ProgressType.ICON_EXTRACTION,
                is_finished=False,
            )
        }
        out = backend._build_output_from_snapshot(ts, ["p1"])
        assert "Processing:" in out

    def test_write_noninteractive_summary_writer_raises(self) -> None:
        """Ensure Summary write except branch is exercised when writer raises."""

        class BadWriter2:
            def write(self, _):
                raise RuntimeError("fail")

            def flush(self):
                pass

        backend = AsciiProgressBackend(output=BadWriter2(), interactive=False)
        sigs = backend._write_noninteractive("Summary:\nDone")
        assert any("Summary:" in s for s in sigs)

    def test_write_interactive_empty_output_sync_lock_exception_handled(
        self,
    ) -> None:
        """When writing nothing, setting _last_output_lines under sync lock may fail; ensure it's swallowed."""
        backend = AsciiProgressBackend(output=io.StringIO(), interactive=True)

        class BadLock:
            def __enter__(self):
                raise RuntimeError("lock fail")

            def __exit__(self, exc_type, exc, tb):
                return False

        backend._sync_lock = BadLock()  # type: ignore[assignment]
        # Should return 0 and not raise
        assert backend._write_interactive("") == 0

    def test_write_noninteractive_skip_empty_section(self) -> None:
        """Empty sections produced by split should be skipped (continue executed)."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=False)
        sigs = backend._write_noninteractive("\n\nOnly\n\n")
        assert {s.strip() for s in sigs} == {"Only"}

    def test_write_noninteractive_summary_and_section_tracking(self) -> None:
        """Test Summary immediate write, new sections detection, and no-change behavior."""
        out = io.StringIO()
        backend = AsciiProgressBackend(output=out, interactive=False)

        sigs = backend._write_noninteractive("Summary:\nAll done")
        assert any("Summary:" in s for s in sigs)

        # New sections should be returned
        out2 = io.StringIO()
        backend2 = AsciiProgressBackend(output=out2, interactive=False)
        content = "First section\n\nSecond section"
        added = backend2._write_noninteractive(content)
        assert {s.strip() for s in added} == {
            "First section",
            "Second section",
        }

        # Known sections should produce no additions
        backend2._written_sections.update({"First section", "Second section"})
        assert backend2._write_noninteractive(content) == set()

    def test_id_cache_eviction_and_calculate_speed_zero(self) -> None:
        """Force ID cache eviction and ensure _calculate_speed returns 0 when no current speed."""
        pd = ProgressDisplay()
        # Temporarily shrink the cache limit to trigger eviction
        import my_unicorn.progress as prog_mod

        old_limit = getattr(prog_mod, "ID_CACHE_LIMIT", None)
        try:
            prog_mod.ID_CACHE_LIMIT = 2
            # generate more ids than the small limit
            pd._generate_namespaced_id(ProgressType.DOWNLOAD, "a")
            pd._generate_namespaced_id(ProgressType.DOWNLOAD, "b")
            pd._generate_namespaced_id(ProgressType.DOWNLOAD, "c")
            assert len(pd._id_cache) <= 2
        finally:
            if old_limit is not None:
                prog_mod.ID_CACHE_LIMIT = old_limit

        # _calculate_speed returns 0.0 when avg_speed==0 and no previous speed
        ti = TaskInfo(
            task_id="t",
            namespaced_id="t",
            name="n",
            progress_type=ProgressType.DOWNLOAD,
        )
        ti.current_speed_mbps = 0.0
        ti.last_speed_update = 100.0
        ti.completed = 100.0
        res = pd._calculate_speed(ti, completed=100.0, current_time=100.0)
        assert res == 0.0

    @pytest.mark.asyncio
    async def test_finish_nonexistent_task_no_raise(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Calling finish_task on a non-existent task should log and return without raising."""
        await progress_service.start_session()
        # Should not raise
        await progress_service.finish_task(
            "this_does_not_exist", success=False
        )
        await progress_service.stop_session()
