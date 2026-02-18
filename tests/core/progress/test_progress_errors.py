import asyncio
from unittest.mock import patch

import pytest

from my_unicorn.core.progress.progress import ProgressDisplay, ProgressType


class TestErrorScenarios:
    """Test various error scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_multiple_session_starts(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test starting multiple sessions doesn't break anything."""
        await progress_service.start_session()
        first_render_task = progress_service._session_manager._render_task

        await progress_service.start_session()  # Should be no-op
        await progress_service.start_session()  # Should be no-op

        # Should still have the same render task
        assert (
            progress_service._session_manager._render_task == first_render_task
        )

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
        assert not progress_service._session_manager._active

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
        task = progress_service._task_registry.get_task_info_full_sync(task_id)
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

        task = progress_service._task_registry.get_task_info_full_sync(task_id)
        assert task.completed == 150.0

        await progress_service.stop_session()

    def test_task_counter_isolation(
        self, progress_service: ProgressDisplay
    ) -> None:
        """Test that task counters are isolated per progress type."""
        # Generate IDs for different types
        download_id1 = progress_service._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "file1"
        )
        download_id2 = progress_service._id_generator.generate_namespaced_id(
            ProgressType.DOWNLOAD, "file2"
        )
        api_id1 = progress_service._id_generator.generate_namespaced_id(
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
        from my_unicorn.core.progress.display_workflows import (
            create_verification_task,
        )

        await progress_service.start_session()

        task_id = await create_verification_task(
            progress_service, "test.AppImage"
        )

        # Test absolute completion update
        await progress_service.update_task(task_id, completed=25.0)

        # Test description update with completion
        await progress_service.update_task(
            task_id, description="🔍 Checking integrity...", completed=75.0
        )

        task_info = progress_service.get_task_info_full(task_id)
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

        # Test task info - use get_task_info_full for full TaskInfo
        task_info = service.get_task_info_full(task_id)
        assert task_info is not None
        assert task_info.name == "test_task"
        assert task_info.progress_type == ProgressType.DOWNLOAD

        # Test task completion
        await service.finish_task(task_id, success=True)

        # Test session cleanup
        await service.stop_session()
        assert not service.is_active()

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

        task_info = service.get_task_info_full(task_id)
        assert task_info is not None
        # Speed should be calculated from history
        assert task_info.current_speed_mbps > 0

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_create_post_processing_task(self) -> None:
        """Test creating post-processing tasks."""
        service = ProgressDisplay()

        await service.start_session()

        task_id = await service.add_task(
            name="MyApp",
            progress_type=ProgressType.UPDATE,
            description="Updating MyApp",
        )

        assert task_id is not None
        task_info = service.get_task_info_full(task_id)
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

        from my_unicorn.core.progress.display_workflows import (
            create_api_fetching_task,
        )

        api_task = await create_api_fetching_task(service, "GitHub API")

        # Verify tasks were created - use get_task_info_full to check existence
        assert service.get_task_info_full(dl_task) is not None
        assert service.get_task_info_full(api_task) is not None

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
