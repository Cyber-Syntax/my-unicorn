"""Tests for edge case error handling in UpdateManager.check_single_update.

This module tests error handling for unexpected exceptions, HTTP errors,
and edge cases in the update checking workflow.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from my_unicorn.core.update.manager import UpdateManager


class TestCheckSingleUpdateEdgeCases:
    """Test cases for edge case error handling in check_single_update."""

    @pytest.fixture
    def update_manager(self) -> UpdateManager:
        """Create UpdateManager instance with mocked dependencies.

        Returns:
            UpdateManager with all external dependencies mocked.

        """
        with (
            patch("my_unicorn.core.update.manager.ConfigManager"),
            patch("my_unicorn.core.update.manager.GitHubAuthManager"),
            patch("my_unicorn.core.update.manager.FileOperations"),
            patch("my_unicorn.core.update.manager.BackupService"),
            patch("my_unicorn.core.update.manager.ReleaseCacheManager"),
        ):
            # Create a minimal config manager mock
            mock_config = MagicMock()
            mock_config.load_global_config.return_value = {
                "max_concurrent_downloads": 3,
                "directory": {
                    "storage": Path("/test/storage"),
                    "download": Path("/test/download"),
                    "backup": Path("/test/backup"),
                    "icon": Path("/test/icon"),
                    "cache": Path("/test/cache"),
                },
            }
            with patch(
                "my_unicorn.core.update.manager.ConfigManager"
            ) as mock_config_cls:
                mock_config_cls.return_value = mock_config
                return UpdateManager()

    @pytest.mark.asyncio
    async def test_check_single_update_unexpected_exception(
        self, update_manager: UpdateManager
    ) -> None:
        """Verify generic exception handler catches unexpected errors.

        This test verifies that when an unexpected RuntimeError occurs
        during the check flow (e.g., during context preparation), the
        generic exception handler at lines 358-361 properly:

        1. Catches the exception
        2. Logs it with logger.exception
        3. Returns UpdateInfo.create_error() with proper error message

        """
        mock_session = AsyncMock(spec=aiohttp.ClientSession)

        with patch.object(
            update_manager, "_load_app_config_or_fail"
        ) as mock_load_config:
            # Configure to raise an unexpected RuntimeError
            mock_load_config.side_effect = RuntimeError(
                "Unexpected failure in context"
            )

            with patch("my_unicorn.core.update.manager.logger") as mock_logger:
                # Call check_single_update
                result = await update_manager.check_single_update(
                    "test-app",
                    session=mock_session,
                    refresh_cache=False,
                )

                # Verify result is error UpdateInfo
                assert result.app_name == "test-app"
                assert result.is_success is False
                assert result.error_reason is not None
                assert "Unexpected error" in result.error_reason

                # Verify logger.exception was called
                mock_logger.exception.assert_called()
                call_args = mock_logger.exception.call_args
                # Check first positional arg contains the message format
                assert "Failed to check updates for" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_check_updates_no_installed_apps(
        self, update_manager: UpdateManager
    ) -> None:
        """Verify check_updates handles empty app list gracefully.

        This test verifies that when check_updates is called with an
        empty apps list (lines 391-393), the method:

        1. Returns empty list without errors
        2. Logs info message about no apps
        3. Makes no cache or GitHub API calls

        """
        with patch.object(
            update_manager.config_manager, "list_installed_apps"
        ) as mock_list_apps:
            # Configure to return empty list (no apps installed)
            mock_list_apps.return_value = []

            with patch("my_unicorn.core.update.manager.logger") as mock_logger:
                # Call check_updates with None (uses installed apps)
                result = await update_manager.check_updates(
                    app_names=None, refresh_cache=False
                )

                # Verify result is empty list
                assert result == []
                assert len(result) == 0

                # Verify logger.info was called about no apps
                mock_logger.info.assert_called()
                call_args = [
                    call[0] for call in mock_logger.info.call_args_list
                ]
                # Check for "No installed apps found" message
                assert any(
                    "No installed apps" in str(arg) for arg in call_args
                )

    @pytest.mark.asyncio
    async def test_check_single_update_unauthorized_401(
        self, update_manager: UpdateManager
    ) -> None:
        """Verify 401 Unauthorized error handling (lines 335-345).

        This test verifies that when GitHub API returns HTTP 401
        (unauthorized/invalid token), the error handler properly:

        1. Catches aiohttp.ClientResponseError with status=401
        2. Creates UpdateInfo error with "Authentication required" message
        3. Logs the error with logger.exception
        4. Suggests setting GitHub token in error message

        """
        mock_session = AsyncMock(spec=aiohttp.ClientSession)

        with patch.object(
            update_manager, "_load_app_config_or_fail"
        ) as mock_load_config:
            # Setup valid config with proper source section
            mock_load_config.return_value = {
                "source": {"owner": "test-owner", "repo": "test-repo"}
            }

            with patch.object(
                update_manager, "_fetch_release_data"
            ) as mock_fetch:
                # Simulate 401 Unauthorized error
                error_401 = aiohttp.ClientResponseError(
                    request_info=MagicMock(),
                    history=(),
                    status=401,
                    message="Unauthorized",
                    headers=None,
                )
                mock_fetch.side_effect = error_401

                with patch(
                    "my_unicorn.core.update.manager.logger"
                ) as mock_logger:
                    # Call check_single_update
                    result = await update_manager.check_single_update(
                        "test-app",
                        session=mock_session,
                        refresh_cache=False,
                    )

                    # Verify result is error UpdateInfo
                    assert result.app_name == "test-app"
                    assert result.is_success is False
                    assert result.error_reason is not None
                    assert "Authentication required" in result.error_reason

                    # Verify logger.exception was called with 401 context
                    mock_logger.exception.assert_called()
                    call_args = mock_logger.exception.call_args[0]
                    assert "Unauthorized (401)" in call_args[0]
                    assert "GitHub Personal Access Token (PAT)" in call_args[0]

    @pytest.mark.asyncio
    async def test_check_single_update_http_error_not_401(
        self, update_manager: UpdateManager
    ) -> None:
        """Verify non-401 HTTP error handling (lines 344-350).

        This test verifies that when GitHub API returns HTTP errors
        other than 401 (e.g., 403 Forbidden, 404 Not Found), the error
        handler properly:

        1. Catches aiohttp.ClientResponseError with status != 401
        2. Creates UpdateInfo error with "HTTP {status} error" message
        3. Logs the error with logger.exception
        4. Includes HTTP status code in error log

        """
        mock_session = AsyncMock(spec=aiohttp.ClientSession)

        with patch.object(
            update_manager, "_load_app_config_or_fail"
        ) as mock_load_config:
            # Setup valid config with proper source section
            mock_load_config.return_value = {
                "source": {"owner": "test-owner", "repo": "test-repo"}
            }

            with patch.object(
                update_manager, "_fetch_release_data"
            ) as mock_fetch:
                # Simulate 403 Forbidden error
                error_403 = aiohttp.ClientResponseError(
                    request_info=MagicMock(),
                    history=(),
                    status=403,
                    message="Forbidden",
                    headers=None,
                )
                mock_fetch.side_effect = error_403

                with patch(
                    "my_unicorn.core.update.manager.logger"
                ) as mock_logger:
                    # Call check_single_update
                    result = await update_manager.check_single_update(
                        "test-app",
                        session=mock_session,
                        refresh_cache=False,
                    )

                    # Verify result is error UpdateInfo
                    assert result.app_name == "test-app"
                    assert result.is_success is False
                    assert result.error_reason is not None
                    assert "HTTP 403 error" in result.error_reason

                    # Verify logger.exception was called with HTTP status
                    mock_logger.exception.assert_called()
                    call_args = mock_logger.exception.call_args[0]
                    assert "Failed to check updates for" in call_args[0]
                    # The logger.exception is called with format string and
                    # separate args. Verify correct format for non-401 errors
                    assert "HTTP %d" in call_args[0]
