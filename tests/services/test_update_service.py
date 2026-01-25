"""Tests for UpdateApplicationService.

Tests the update application service layer that orchestrates update workflows.
"""

# ruff: noqa: ANN001, ANN201, SLF001, RUF059

from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.workflows.services.update_service import (
    UpdateApplicationService,
)
from my_unicorn.core.workflows.update import UpdateInfo


@pytest.fixture
def mock_config_manager():
    """Create a mock config manager."""
    mock = MagicMock()
    mock.list_installed_apps.return_value = ["app1", "app2"]
    return mock


@pytest.fixture
def mock_update_manager():
    """Create a mock update manager."""
    manager = AsyncMock()
    manager._shared_api_task_id = None
    return manager


@pytest.fixture
def mock_progress_service():
    """Create a mock progress service."""
    progress = AsyncMock()
    progress.create_api_fetching_task.return_value = "task-123"
    return progress


@pytest.fixture
def update_service(
    mock_config_manager, mock_update_manager, mock_progress_service
):
    """Create an update service with mocks."""
    return UpdateApplicationService(
        config_manager=mock_config_manager,
        update_manager=mock_update_manager,
        progress_service=mock_progress_service,
    )


class TestUpdateApplicationService:
    """Test suite for UpdateApplicationService."""

    @pytest.mark.asyncio
    async def test_check_updates_success(
        self, update_service, mock_update_manager
    ):
        """Test successful update check."""
        # Arrange
        expected_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
            UpdateInfo(
                "app2", "2.0.0", "2.0.0", has_update=False, release_url="url2"
            ),
        ]
        mock_update_manager.check_updates.return_value = expected_infos

        # Act
        result = await update_service.check_updates()

        # Assert
        assert result == expected_infos
        mock_update_manager.check_updates.assert_called_once_with(
            app_names=None,
            refresh_cache=False,
        )

    @pytest.mark.asyncio
    async def test_check_updates_with_app_names(
        self, update_service, mock_update_manager
    ):
        """Test update check with specific app names."""
        # Arrange
        app_names = ["app1", "app2"]
        expected_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
        ]
        mock_update_manager.check_updates.return_value = expected_infos

        # Act
        result = await update_service.check_updates(app_names=app_names)

        # Assert
        assert result == expected_infos
        mock_update_manager.check_updates.assert_called_once_with(
            app_names=app_names,
            refresh_cache=False,
        )

    @pytest.mark.asyncio
    async def test_check_updates_with_refresh_cache(
        self, update_service, mock_update_manager
    ):
        """Test update check with cache refresh."""
        # Arrange
        expected_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
        ]
        mock_update_manager.check_updates.return_value = expected_infos

        # Act
        result = await update_service.check_updates(refresh_cache=True)

        # Assert
        assert result == expected_infos
        mock_update_manager.check_updates.assert_called_once_with(
            app_names=None,
            refresh_cache=True,
        )

    @pytest.mark.asyncio
    async def test_update_no_infos(self, update_service, mock_update_manager):
        """Test update when no update info is available."""
        # Arrange
        mock_update_manager.check_updates.return_value = []

        # Act
        updated, failed, up_to_date, infos = await update_service.update()

        # Assert
        assert updated == []
        assert failed == []
        assert up_to_date == []
        assert infos == []
        mock_update_manager.update_multiple_apps.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_all_up_to_date(
        self, update_service, mock_update_manager
    ):
        """Test update when all apps are up to date."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.0.0", has_update=False, release_url="url1"
            ),
            UpdateInfo(
                "app2", "2.0.0", "2.0.0", has_update=False, release_url="url2"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos

        # Act
        updated, failed, up_to_date, infos = await update_service.update()

        # Assert
        assert updated == []
        assert failed == []
        assert up_to_date == ["app1", "app2"]
        assert infos == update_infos
        mock_update_manager.update_multiple_apps.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_successful_updates(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test successful updates."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
            UpdateInfo(
                "app2", "2.0.0", "2.1.0", has_update=True, release_url="url2"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": True, "app2": True},
            {},
        )

        # Act
        updated, failed, up_to_date, infos = await update_service.update()

        # Assert
        assert updated == ["app1", "app2"]
        assert failed == []
        assert up_to_date == []
        assert infos == update_infos

        # Verify progress management
        mock_progress_service.create_api_fetching_task.assert_called_once()
        mock_progress_service.update_task.assert_called_once()
        mock_progress_service.finish_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_partial_success(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test updates with partial success."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
            UpdateInfo(
                "app2", "2.0.0", "2.1.0", has_update=True, release_url="url2"
            ),
            UpdateInfo(
                "app3", "3.0.0", "3.1.0", has_update=True, release_url="url3"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": True, "app2": False, "app3": True},
            {"app2": "Download failed"},
        )

        # Act
        updated, failed, up_to_date, infos = await update_service.update()

        # Assert
        assert updated == ["app1", "app3"]
        assert failed == ["app2"]
        assert up_to_date == []

        # Verify error reason was attached
        app2_info = next(i for i in infos if i.app_name == "app2")
        assert app2_info.error_reason == "Download failed"

    @pytest.mark.asyncio
    async def test_update_mixed_status(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test updates with mixed status (some need updates, some don't)."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
            UpdateInfo(
                "app2", "2.0.0", "2.0.0", has_update=False, release_url="url2"
            ),
            UpdateInfo(
                "app3", "3.0.0", "3.1.0", has_update=True, release_url="url3"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": True, "app3": True},
            {},
        )

        # Act
        updated, failed, up_to_date, infos = await update_service.update()

        # Assert
        assert updated == ["app1", "app3"]
        assert failed == []
        assert up_to_date == ["app2"]

        # Only apps needing updates should be processed
        mock_update_manager.update_multiple_apps.assert_called_once()
        call_args = mock_update_manager.update_multiple_apps.call_args
        assert call_args[0][0] == ["app1", "app3"]

    @pytest.mark.asyncio
    async def test_update_with_force(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test update with force flag."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.0.0", has_update=False, release_url="url1"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": True},
            {},
        )

        # Act
        updated, failed, up_to_date, infos = await update_service.update(
            force=True
        )

        # Assert
        assert updated == ["app1"]
        assert failed == []
        assert up_to_date == []

        # App should be updated even without has_update flag
        mock_update_manager.update_multiple_apps.assert_called_once()
        call_args = mock_update_manager.update_multiple_apps.call_args
        assert call_args[1]["force"] is True

    @pytest.mark.asyncio
    async def test_update_with_specific_apps(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test update with specific app names."""
        # Arrange
        app_names = ["app1", "app2"]
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
            UpdateInfo(
                "app2", "2.0.0", "2.1.0", has_update=True, release_url="url2"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": True, "app2": True},
            {},
        )

        # Act
        updated, failed, up_to_date, infos = await update_service.update(
            app_names=app_names
        )

        # Assert
        assert updated == ["app1", "app2"]
        mock_update_manager.check_updates.assert_called_once_with(
            app_names=app_names,
            refresh_cache=False,
        )

    @pytest.mark.asyncio
    async def test_update_progress_lifecycle(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test progress lifecycle management during update."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": True},
            {},
        )

        # Act
        await update_service.update()

        # Assert - verify progress task lifecycle
        mock_progress_service.create_api_fetching_task.assert_called_once_with(
            name="GitHub Releases",
            description="🌐 Fetching release information...",
        )
        mock_progress_service.update_task.assert_called_once_with(
            "task-123", total=1.0, completed=0.0
        )
        mock_progress_service.finish_task.assert_called_once_with(
            "task-123", success=True
        )

    @pytest.mark.asyncio
    async def test_update_progress_cleanup_on_error(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test progress cleanup on error."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.side_effect = RuntimeError(
            "Test error"
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="Test error"):
            await update_service.update()

        # Progress should be cleaned up
        mock_progress_service.finish_task.assert_called_once_with(
            "task-123", success=False
        )

    @pytest.mark.asyncio
    async def test_update_shared_api_task_cleanup(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test shared API task ID cleanup."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": True},
            {},
        )

        # Act
        await update_service.update()

        # Assert - shared API task should be cleaned up
        assert mock_update_manager._shared_api_task_id is None

    @pytest.mark.asyncio
    async def test_update_error_reasons_attached(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test that error reasons are attached to UpdateInfo objects."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
            UpdateInfo(
                "app2", "2.0.0", "2.1.0", has_update=True, release_url="url2"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": False, "app2": False},
            {
                "app1": "Network error",
                "app2": "Invalid checksum",
            },
        )

        # Act
        _, _, _, infos = await update_service.update()

        # Assert
        app1_info = next(i for i in infos if i.app_name == "app1")
        app2_info = next(i for i in infos if i.app_name == "app2")
        assert app1_info.error_reason == "Network error"
        assert app2_info.error_reason == "Invalid checksum"

    @pytest.mark.asyncio
    async def test_update_infos_passed_to_manager(
        self, update_service, mock_update_manager, mock_progress_service
    ):
        """Test that update_infos are passed to manager for optimization."""
        # Arrange
        update_infos = [
            UpdateInfo(
                "app1", "1.0.0", "1.1.0", has_update=True, release_url="url1"
            ),
        ]
        mock_update_manager.check_updates.return_value = update_infos
        mock_update_manager.update_multiple_apps.return_value = (
            {"app1": True},
            {},
        )

        # Act
        await update_service.update()

        # Assert - update_infos should be passed for optimization
        call_args = mock_update_manager.update_multiple_apps.call_args
        assert call_args[1]["update_infos"] == update_infos
