import os
import asyncio
import tempfile
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Any, List, Set, Tuple, Optional, Generator

from src.commands.update_all_async import UpdateAsyncCommand
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager


class TestUpdateAsyncCommand:
    """Tests for the UpdateAsyncCommand class."""

    @pytest.fixture
    def update_command(self) -> UpdateAsyncCommand:
        """Create an UpdateAsyncCommand instance for testing.

        Returns:
            UpdateAsyncCommand: A command instance
        """
        with patch.object(AppConfigManager, "__init__", return_value=None), patch.object(
            GlobalConfigManager, "__init__", return_value=None
        ):
            command = UpdateAsyncCommand()
            command.console = MagicMock()
            command.max_concurrent_updates = 2
            return command

    @pytest.fixture
    def mock_app_configs(self) -> List[Dict[str, Any]]:
        """Create mock app configurations for testing.

        Returns:
            List[Dict[str, Any]]: List of app config dictionaries
        """
        return [
            {
                "name": "app1",
                "config_file": "app1.json",
                "current": "1.0.0",
                "latest": "1.1.0",
            },
            {
                "name": "app2",
                "config_file": "app2.json",
                "current": "2.0.0",
                "latest": "2.1.0",
            },
            {
                "name": "app3",
                "config_file": "app3.json",
                "current": "3.0.0",
                "latest": "3.1.0",
            },
            {
                "name": "app4",
                "config_file": "app4.json",
                "current": "4.0.0",
                "latest": "4.1.0",
            },
        ]

    def test_init(self, update_command: UpdateAsyncCommand) -> None:
        """Test initialization of the command."""
        assert update_command.max_concurrent_updates == 2
        assert update_command.semaphore is None

    def test_check_rate_limits(
        self, update_command: UpdateAsyncCommand, mock_app_configs: List[Dict[str, Any]]
    ) -> None:
        """Test rate limit checking functionality."""
        # Test with sufficient rate limits
        with patch(
            "src.commands.update_all_async.GitHubAuthManager.get_rate_limit_info"
        ) as mock_rate_limits:
            mock_rate_limits.return_value = (
                100,
                100,
                "reset_time",
                True,
            )  # 100 remaining, 100 limit

            can_proceed, filtered_apps, message = update_command._check_rate_limits(
                mock_app_configs
            )

            # Should be able to proceed with all apps
            assert can_proceed is True
            assert len(filtered_apps) == 4
            assert "Sufficient" in message

        # Test with insufficient rate limits (but enough for some)
        with patch(
            "src.commands.update_all_async.GitHubAuthManager.get_rate_limit_info"
        ) as mock_rate_limits:
            mock_rate_limits.return_value = (6, 100, "reset_time", True)  # 6 remaining, 100 limit

            can_proceed, filtered_apps, message = update_command._check_rate_limits(
                mock_app_configs
            )

            # Should not be able to proceed with all apps, but can with some
            assert can_proceed is False
            assert len(filtered_apps) == 2  # 6 limits ÷ 3 requests per app = 2 apps
            assert "Insufficient" in message

        # Test with not enough rate limits for any app
        with patch(
            "src.commands.update_all_async.GitHubAuthManager.get_rate_limit_info"
        ) as mock_rate_limits:
            mock_rate_limits.return_value = (2, 100, "reset_time", True)  # 2 remaining, 100 limit

            can_proceed, filtered_apps, message = update_command._check_rate_limits(
                mock_app_configs
            )

            # Should not be able to proceed with any apps
            assert can_proceed is False
            assert len(filtered_apps) == 0
            assert "Insufficient" in message
            assert "Cannot process any apps" in message

    @pytest.mark.asyncio
    async def test_update_app_async(self, update_command: UpdateAsyncCommand) -> None:
        """Test the update_app_async method."""
        # Create a mock event loop and semaphore
        loop = asyncio.get_event_loop()
        update_command.semaphore = asyncio.Semaphore(2)

        # Mock app data
        app_data = {
            "name": "test_app",
            "config_file": "test_app.json",
            "current": "1.0.0",
            "latest": "1.1.0",
        }

        # Mock successful update
        with patch.object(
            update_command, "_update_single_app_async", return_value=True
        ) as mock_update:
            result, data = await update_command._update_app_async.call(app_data, 1)

            # Verify update was successful
            assert result is True
            assert data["status"] == "success"
            mock_update.assert_called_once_with(app_data, is_batch=True, app_index=1, total_apps=0)
            update_command.console.print.assert_called_once()
            assert "Successfully updated" in update_command.console.print.call_args[0][0]

        # Mock failed update
        update_command.console.print.reset_mock()
        with patch.object(
            update_command, "_update_single_app_async", return_value=False
        ) as mock_update:
            result, data = await update_command._update_app_async.call(app_data, 1)

            # Verify update failed
            assert result is False
            assert data["status"] == "failed"
            mock_update.assert_called_once_with(app_data, is_batch=True, app_index=1, total_apps=0)
            update_command.console.print.assert_called_once()
            assert "Failed to update" in update_command.console.print.call_args[0][0]

        # Mock update with exception
        update_command.console.print.reset_mock()
        with patch.object(
            update_command, "_update_single_app_async", side_effect=Exception("Test error")
        ) as mock_update:
            result, data = await update_command._update_app_async.call(app_data, 1)

            # Verify exception was handled
            assert result is False
            assert data["status"] == "error"
            assert data["message"] == "Test error"
            mock_update.assert_called_once_with(app_data, is_batch=True, app_index=1, total_apps=0)
            update_command.console.print.assert_called_once()
            assert "Error updating" in update_command.console.print.call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_apps_async(
        self, update_command: UpdateAsyncCommand, mock_app_configs: List[Dict[str, Any]]
    ) -> None:
        """Test the _update_apps_async method."""
        # Mock asyncio.gather to return mock update results
        update_results = [
            (True, {"status": "success", "message": "Updated app1", "elapsed": 1.0}),
            (False, {"status": "failed", "message": "Failed to update app2", "elapsed": 1.0}),
            (Exception("Test error")),  # Simulate an escaped exception
            (True, {"status": "success", "message": "Updated app4", "elapsed": 1.0}),
        ]

        # Mock the event loop and asyncio.gather
        with patch("asyncio.get_event_loop") as mock_get_loop, patch(
            "asyncio.gather", return_value=update_results
        ) as mock_gather, patch.object(
            update_command, "_update_app_async"
        ) as mock_update_app, patch.object(
            update_command, "_display_rate_limit_info_rich"
        ) as mock_display_limits:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_until_complete = lambda x: x

            # Call the method
            update_command._update_apps_async(mock_app_configs)

            # Verify the event loop and gather were used correctly
            mock_get_loop.assert_called_once()
            mock_gather.assert_called_once()

            # Verify update tasks were created for each app
            assert mock_update_app.call_count == 4

            # Verify results were processed
            assert update_command.console.print.call_count > 0

            # Verify summary was displayed
            summary_call = [
                call
                for call in update_command.console.print.call_args_list
                if "=== Update Summary ===" in call[0][0]
            ]
            assert len(summary_call) > 0

            # Verify rate limits were displayed
            mock_display_limits.assert_called_once()

    def test_update_single_app_async(self, update_command: UpdateAsyncCommand) -> None:
        """Test the _update_single_app_async method."""
        # Create test data
        app_data = {
            "name": "test_app",
            "config_file": "test_app.json",
        }

        # Mock required objects
        with patch.object(
            AppConfigManager, "load_appimage_config"
        ) as mock_load_config, patch.object(
            GitHubAPI, "__init__", return_value=None
        ) as mock_github_init, patch.object(
            GitHubAPI, "get_response", return_value=(True, "response")
        ) as mock_get_response, patch.object(
            GitHubAPI, "appimage_name", "test.AppImage", create=True
        ), patch.object(
            GitHubAPI, "appimage_url", "https://example.com/test.AppImage", create=True
        ), patch.object(GitHubAPI, "version", "1.1.0", create=True), patch.object(
            DownloadManager, "__init__", return_value=None
        ) as mock_download_init, patch.object(DownloadManager, "download") as mock_download, patch(
            "os.path.exists", return_value=True
        ), patch("os.path.join", return_value="/tmp/test.AppImage"), patch("os.remove"), patch(
            "shutil.copy2"
        ), patch("os.chmod"), patch("os.stat"), patch.object(
            update_command, "_verify_appimage", return_value=True
        ) as mock_verify, patch.object(
            update_command, "_create_file_handler"
        ) as mock_create_handler, patch(
            "src.icon_manager.IconManager", return_value=MagicMock()
        ) as mock_icon_manager_class:
            # Mock IconManager
            mock_icon_manager = MagicMock()
            mock_icon_manager.ensure_app_icon.return_value = (True, "/path/to/icon.png")

            with patch(
                "src.icon_manager.IconManager", return_value=mock_icon_manager
            ) as mock_icon_manager_class:
                # Mock file handler
                mock_file_handler = MagicMock()
                mock_file_handler.download_app_icon.return_value = True
                mock_file_handler.handle_appimage_operations.return_value = True
                mock_create_handler.return_value = mock_file_handler

                # Mock app config updates
                mock_app_config = MagicMock()
                mock_load_config.return_value = mock_app_config

                # Call the method
                result = update_command._update_single_app_async(
                    app_data, is_batch=True, app_index=1, total_apps=4
                )

                # Verify successful update
                assert result is True

                # Verify the correct sequence of operations
                mock_load_config.assert_called_once_with(app_data["config_file"])
                mock_get_response.assert_called_once()
                mock_download_init.assert_called_once()
                mock_download.assert_called_once()
                mock_verify.assert_called_once()
                mock_icon_manager.ensure_app_icon.assert_called_once_with(
                    mock_app_config.owner, mock_app_config.repo
                )
                mock_file_handler.handle_appimage_operations.assert_called_once()
                mock_app_config.update_version.assert_called_once()

    def test_update_single_app_async_errors(self, update_command: UpdateAsyncCommand) -> None:
        """Test error handling in _update_single_app_async method."""
        # Create test data
        app_data = {
            "name": "test_app",
            "config_file": "test_app.json",
        }

        # Test API error
        with patch.object(AppConfigManager, "load_appimage_config"), patch.object(
            GitHubAPI, "__init__", return_value=None
        ), patch.object(GitHubAPI, "get_response", return_value=(False, "API error")):
            result = update_command._update_single_app_async(app_data)
            assert result is False

        # Test missing AppImage info
        with patch.object(AppConfigManager, "load_appimage_config"), patch.object(
            GitHubAPI, "__init__", return_value=None
        ), patch.object(GitHubAPI, "get_response", return_value=(True, "response")), patch.object(
            GitHubAPI, "appimage_name", None, create=True
        ), patch.object(GitHubAPI, "appimage_url", None, create=True):
            result = update_command._update_single_app_async(app_data)
            assert result is False

        # Test download error
        with patch.object(AppConfigManager, "load_appimage_config"), patch.object(
            GitHubAPI, "__init__", return_value=None
        ), patch.object(GitHubAPI, "get_response", return_value=(True, "response")), patch.object(
            GitHubAPI, "appimage_name", "test.AppImage", create=True
        ), patch.object(
            GitHubAPI, "appimage_url", "https://example.com/test.AppImage", create=True
        ), patch.object(DownloadManager, "__init__", return_value=None), patch.object(
            DownloadManager, "download", side_effect=Exception("Download error")
        ):
            result = update_command._update_single_app_async(app_data)
            assert result is False

        # Test verification failure
        with patch.object(AppConfigManager, "load_appimage_config"), patch.object(
            GitHubAPI, "__init__", return_value=None
        ), patch.object(GitHubAPI, "get_response", return_value=(True, "response")), patch.object(
            GitHubAPI, "appimage_name", "test.AppImage", create=True
        ), patch.object(
            GitHubAPI, "appimage_url", "https://example.com/test.AppImage", create=True
        ), patch.object(DownloadManager, "__init__", return_value=None), patch.object(
            DownloadManager, "download"
        ), patch("os.path.exists", return_value=True), patch(
            "os.path.join", return_value="/tmp/test.AppImage"
        ), patch("shutil.copy2"), patch("os.chmod"), patch.object(
            update_command, "_verify_appimage", return_value=False
        ):
            result = update_command._update_single_app_async(app_data)
            assert result is False
