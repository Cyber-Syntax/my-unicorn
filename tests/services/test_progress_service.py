"""Tests for the progress service module."""

import asyncio
from pathlib import Path

import pytest

from my_unicorn.services.progress import (
    ProgressConfig,
    ProgressService,
    ProgressType,
    get_progress_service,
    progress_session,
    set_progress_service,
)


class TestProgressService:
    """Test cases for ProgressService."""

    def test_progress_service_initialization(self):
        """Test progress service can be initialized."""
        service = ProgressService()
        assert service is not None
        assert not service.is_active()

    def test_progress_config(self):
        """Test progress configuration."""
        config = ProgressConfig(
            refresh_per_second=20,
            show_overall=False,
            show_downloads=True,
        )

        assert config.refresh_per_second == 20
        assert not config.show_overall
        assert config.show_downloads

    @pytest.mark.asyncio
    async def test_basic_progress_operations(self):
        """Test basic progress operations without Rich display."""
        service = ProgressService()

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

    @pytest.mark.asyncio
    async def test_convenience_methods(self):
        """Test convenience methods for creating tasks."""
        service = ProgressService()
        await service.start_session()

        # Test download task creation
        download_task = await service.create_download_task("test.AppImage", 50.0)
        task_info = service.get_task_info(download_task)
        assert task_info.progress_type == ProgressType.DOWNLOAD
        assert task_info.total == 50.0

        # Test verification task creation
        verify_task = await service.create_verification_task("test.AppImage")
        task_info = service.get_task_info(verify_task)
        assert task_info.progress_type == ProgressType.VERIFICATION
        assert task_info.total == 100.0

        # Test icon extraction task creation
        icon_task = await service.create_icon_extraction_task("TestApp")
        task_info = service.get_task_info(icon_task)
        assert task_info.progress_type == ProgressType.ICON_EXTRACTION

        # Test installation task creation
        install_task = await service.create_installation_task("TestApp")
        task_info = service.get_task_info(install_task)
        assert task_info.progress_type == ProgressType.INSTALLATION

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test progress service context manager."""
        async with progress_session(total_operations=2) as service:
            assert service.is_active()

            task_id = await service.add_task(
                "context_test",
                ProgressType.VERIFICATION,
                total=100.0,
            )

            await service.update_task(task_id, completed=100.0)
            await service.finish_task(task_id, success=True)

        # Service should be cleaned up automatically
        assert not service.is_active()

    @pytest.mark.asyncio
    async def test_session_context_manager(self):
        """Test using session method as context manager."""
        service = ProgressService()

        async with service.session(total_operations=1):
            assert service.is_active()

            task_id = await service.create_download_task("test.bin", 10.0)
            await service.update_task(task_id, completed=10.0)
            await service.finish_task(task_id, success=True)

        assert not service.is_active()

    @pytest.mark.asyncio
    async def test_task_failure_handling(self):
        """Test handling of failed tasks."""
        service = ProgressService()
        await service.start_session(total_operations=1)

        task_id = await service.create_verification_task("failing_test.AppImage")

        # Simulate failure
        await service.finish_task(
            task_id, success=False, final_description="❌ Verification failed"
        )

        task_info = service.get_task_info(task_id)
        assert task_info.success is False

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_tasks(self):
        """Test handling multiple concurrent tasks."""
        service = ProgressService()
        await service.start_session(total_operations=3)

        # Create multiple tasks of different types
        tasks = [
            await service.create_download_task("app1.AppImage", 25.0),
            await service.create_verification_task("app1.AppImage"),
            await service.create_installation_task("App1"),
        ]

        # Update all tasks concurrently
        update_tasks = [
            service.update_task(tasks[0], completed=25.0),
            service.update_task(tasks[1], completed=100.0),
            service.update_task(tasks[2], completed=100.0),
        ]
        await asyncio.gather(*update_tasks)

        # Finish all tasks
        finish_tasks = [service.finish_task(task_id, success=True) for task_id in tasks]
        await asyncio.gather(*finish_tasks)

        await service.stop_session()

    def test_global_progress_service(self):
        """Test global progress service management."""
        # Get default global service
        service1 = get_progress_service()
        service2 = get_progress_service()
        assert service1 is service2  # Should be the same instance

        # Set custom global service
        custom_service = ProgressService()
        set_progress_service(custom_service)

        service3 = get_progress_service()
        assert service3 is custom_service
        assert service3 is not service1

    @pytest.mark.asyncio
    async def test_invalid_task_operations(self):
        """Test operations on invalid task IDs."""
        service = ProgressService()
        await service.start_session()

        # Try to update non-existent task (should not raise exception)
        await service.update_task("invalid_id", completed=50.0)
        await service.finish_task("invalid_id", success=True)

        # Task info should return None for invalid ID
        task_info = service.get_task_info("invalid_id")
        assert task_info is None

        await service.stop_session()

    @pytest.mark.asyncio
    async def test_progress_with_path_objects(self):
        """Test progress service with Path objects."""
        service = ProgressService()
        await service.start_session()

        file_path = Path("/tmp/test.AppImage")
        task_id = await service.create_download_task(str(file_path), 30.0)

        task_info = service.get_task_info(task_id)
        assert task_info.name == "test.AppImage"  # Should extract filename

        await service.finish_task(task_id, success=True)
        await service.stop_session()

    @pytest.mark.asyncio
    async def test_progress_update_methods(self):
        """Test different progress update methods."""
        service = ProgressService()
        await service.start_session()

        task_id = await service.create_verification_task("test.AppImage")

        # Test absolute completion update
        await service.update_task(task_id, completed=25.0)

        # Test advance update
        await service.update_task(task_id, advance=25.0)

        # Test description update
        await service.update_task(
            task_id, description="🔍 Checking integrity...", completed=75.0
        )

        await service.finish_task(task_id, success=True)
        await service.stop_session()

    @pytest.mark.asyncio
    async def test_session_reuse_prevention(self):
        """Test that starting an already active session shows warning."""
        service = ProgressService()

        await service.start_session(total_operations=1)
        assert service.is_active()

        # Starting again should not crash (but may log warning)
        await service.start_session(total_operations=2)
        assert service.is_active()

        await service.stop_session()
        assert not service.is_active()

        # Stopping inactive session should not crash
        await service.stop_session()
        assert not service.is_active()


class TestProgressIntegration:
    """Integration tests for progress service."""

    @pytest.mark.asyncio
    async def test_realistic_download_simulation(self):
        """Test realistic download progress simulation."""

        async def simulate_download(service: ProgressService, filename: str, size_mb: float):
            task_id = await service.create_download_task(filename, size_mb)

            # Simulate chunked download
            downloaded = 0.0
            chunk_size = 0.5  # 0.5 MB chunks

            while downloaded < size_mb:
                chunk = min(chunk_size, size_mb - downloaded)
                downloaded += chunk

                await service.update_task(task_id, completed=downloaded)
                await asyncio.sleep(0.01)  # Simulate network delay

            await service.finish_task(task_id, success=True)
            return True

        async with progress_session(total_operations=2) as service:
            # Simulate two concurrent downloads
            results = await asyncio.gather(
                simulate_download(service, "firefox.AppImage", 5.0),
                simulate_download(service, "vscode.AppImage", 7.0),
            )

            assert all(results)

    @pytest.mark.asyncio
    async def test_complete_app_workflow(self):
        """Test complete application installation workflow."""

        async def complete_workflow(service: ProgressService, app_name: str):
            # Download phase
            download_task = await service.create_download_task(f"{app_name}.AppImage", 10.0)
            for i in range(0, 101, 10):
                await service.update_task(download_task, completed=i * 0.1)
                await asyncio.sleep(0.01)
            await service.finish_task(download_task, success=True)

            # Verification phase
            verify_task = await service.create_verification_task(f"{app_name}.AppImage")
            for i in range(0, 101, 20):
                await service.update_task(verify_task, completed=i)
                await asyncio.sleep(0.01)
            await service.finish_task(verify_task, success=True)

            # Icon extraction phase
            icon_task = await service.create_icon_extraction_task(app_name)
            for i in range(0, 101, 25):
                await service.update_task(icon_task, completed=i)
                await asyncio.sleep(0.01)
            await service.finish_task(icon_task, success=True)

            # Installation phase
            install_task = await service.create_installation_task(app_name)
            steps = [
                ("Creating directories", 25),
                ("Copying files", 50),
                ("Creating desktop entry", 75),
                ("Finalizing", 100),
            ]

            for description, progress in steps:
                await service.update_task(
                    install_task, completed=progress, description=f"🔧 {description}..."
                )
                await asyncio.sleep(0.01)

            await service.finish_task(install_task, success=True)
            return True

        async with progress_session(total_operations=1) as service:
            result = await complete_workflow(service, "TestApp")
            assert result is True
