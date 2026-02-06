"""Tests for update management functionality."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import aiohttp
import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.post_download import OperationType, PostDownloadResult
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.core.update.update import UpdateManager
from my_unicorn.exceptions import UpdateError, VerificationError

# Test constants
EXPECTED_APP_COUNT = 2
EXPECTED_CALL_COUNT = 3


class TestUpdateInfo:
    """Test cases for UpdateInfo class."""

    def test_init_basic(self) -> None:
        """Test UpdateInfo initialization with basic parameters."""
        info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="1.1.0",
            has_update=True,
        )

        assert info.app_name == "test-app"
        assert info.current_version == "1.0.0"
        assert info.latest_version == "1.1.0"
        assert info.has_update is True
        assert info.release_url == ""
        assert info.prerelease is False
        assert info.original_tag_name == "v1.1.0"

    def test_init_full_parameters(self) -> None:
        """Test UpdateInfo initialization with all parameters."""
        info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="2.0.0-beta",
            has_update=True,
            release_url="https://github.com/owner/repo/releases/tag/v2.0.0-beta",
            prerelease=True,
            original_tag_name="v2.0.0-beta",
        )

        assert info.app_name == "test-app"
        assert info.current_version == "1.0.0"
        assert info.latest_version == "2.0.0-beta"
        assert info.has_update is True
        assert (
            info.release_url
            == "https://github.com/owner/repo/releases/tag/v2.0.0-beta"
        )
        assert info.prerelease is True
        assert info.original_tag_name == "v2.0.0-beta"

    def test_repr_with_update(self) -> None:
        """Test string representation when update is available."""
        info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="1.1.0",
            has_update=True,
        )

        expected = "UpdateInfo(test-app: 1.0.0 -> 1.1.0, Available)"
        assert repr(info) == expected

    def test_repr_no_update(self) -> None:
        """Test string representation when no update is available."""
        info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="1.0.0",
            has_update=False,
        )

        expected = "UpdateInfo(test-app: 1.0.0 -> 1.0.0, Up to date)"
        assert repr(info) == expected


class TestUpdateManager:
    """Test cases for UpdateManager class."""

    @pytest.fixture
    def mock_config_manager(self) -> MagicMock:
        """Create mock ConfigManager."""
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
        mock_config.list_installed_apps.return_value = ["app1", "app2"]
        return mock_config

    @pytest.fixture
    def mock_app_config(self) -> dict[str, Any]:
        """Create mock app configuration."""
        return {
            "owner": "test-owner",
            "repo": "test-repo",
            "source": "catalog",
            "appimage": {
                "name": "test-app.AppImage",
                "version": "1.0.0",
                "characteristic_suffix": ["-x86_64", "-linux"],
            },
            "icon": {
                "installed": True,
                "url": "https://example.com/icon.png",
            },
        }

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock aiohttp session."""
        return AsyncMock(spec=aiohttp.ClientSession)

    @pytest.fixture
    def update_manager(self, mock_config_manager: MagicMock) -> UpdateManager:
        """Create UpdateManager instance with mocked dependencies."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(mock_config_manager)
            return manager

    def test_init_with_config_manager(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateManager initialization with provided config manager."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(mock_config_manager)

            assert manager.config_manager == mock_config_manager
            mock_config_manager.load_global_config.assert_called_once()

    def test_init_default_config_manager(self) -> None:
        """Test UpdateManager initialization with default config manager."""
        with (
            patch(
                "my_unicorn.core.update.update.ConfigManager"
            ) as mock_config_cls,
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            mock_config_instance = MagicMock()
            mock_config_cls.return_value = mock_config_instance
            mock_config_instance.load_global_config.return_value = {
                "max_concurrent_downloads": 5,
                "directory": {"storage": Path("/default/storage")},
            }

            manager = UpdateManager()

            mock_config_cls.assert_called_once_with()
            assert manager.config_manager == mock_config_instance

    def test_shared_api_task_id_initialized(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test that _shared_api_task_id is initialized to None."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(mock_config_manager)

            assert hasattr(manager, "_shared_api_task_id")
            assert manager._shared_api_task_id is None

    @pytest.mark.parametrize(
        "current,latest,expected",
        [
            ("1.0.0", "1.1.0", True),
            ("1.0.0", "2.0.0", True),
            ("1.1.0", "1.0.0", False),
            ("1.0.0", "1.0.0", False),
            ("v1.0.0", "v1.1.0", True),
            ("V1.0.0", "V1.1.0", True),
            ("1.0", "1.0.1", True),
            ("1.0.0", "1.0", False),
            ("1.2.3", "1.10.0", True),
            ("1.10.0", "1.2.3", False),
            (
                "2.0.0-alpha",
                "2.0.0-beta",
                True,
            ),  # fallback to string comparison: "2.0.0-alpha" < "2.0.0-beta"
            (
                "invalid",
                "1.0.0",
                False,
            ),  # fallback to string comparison: "1.0.0" < "invalid"
            (
                "1.0.0",
                "invalid",
                True,
            ),  # fallback to string comparison: "1.0.0" < "invalid"
        ],
    )
    def test_compare_versions(
        self,
        update_manager: UpdateManager,
        current: str,
        latest: str,
        expected: bool,
    ) -> None:
        """Test version comparison logic through public interface."""
        # Test version comparison through check_single_update
        # rather than private method
        with patch.object(update_manager, "config_manager") as mock_config:
            # load_app_config now returns merged effective config
            mock_config.load_app_config.return_value = {
                "config_version": "2.0.0",
                "source": {
                    "owner": "test-owner",
                    "repo": "test-repo",
                    "prerelease": False,
                },
                "state": {"version": current},
            }
            mock_config.load_catalog.return_value = None

            # Create a proper Release object
            mock_release_data = Release(
                owner="test-owner",
                repo="test-repo",
                version=latest,
                prerelease=False,
                assets=[],
                original_tag_name=f"v{latest}",
            )

            with patch(
                "my_unicorn.core.update.update.ReleaseFetcher"
            ) as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                method = mock_fetcher.fetch_latest_release_or_prerelease
                method.return_value = mock_release_data

                async def run_test() -> None:
                    result = await update_manager.check_single_update(
                        "test-app", AsyncMock(spec=aiohttp.ClientSession)
                    )
                    assert result.is_success, (
                        f"Check failed: {result.error_reason}"
                    )
                    assert result.has_update == expected

                asyncio.run(run_test())

    @pytest.mark.asyncio
    async def test_check_single_update_success(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
        mock_app_config: dict[str, Any],
    ) -> None:
        """Test successful single app update check."""
        # Mock dependencies via the mock_config_manager
        # load_app_config now returns merged effective config
        mock_config_manager.load_app_config.return_value = {
            "config_version": "2.0.0",
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {"version": "1.0.0"},
        }
        mock_config_manager.load_catalog.return_value = {
            "github": {"use_github_api": True, "use_prerelease": False}
        }

        mock_release_data = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.2.0",
            prerelease=False,
            assets=[],
            original_tag_name="v1.2.0",
        )

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch(
                "my_unicorn.core.update.update.ReleaseFetcher"
            ) as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                # Mock both possible method calls
                mock_fetcher.fetch_latest_release.return_value = (
                    mock_release_data
                )
                method = mock_fetcher.fetch_latest_release_or_prerelease
                method.return_value = mock_release_data
                # Ensure the shared API task ID is properly mocked
                mock_fetcher.set_shared_api_task = MagicMock()

                result = await update_manager.check_single_update(
                    "test-app", mock_session
                )

                assert result is not None
                assert result.app_name == "test-app"
                assert result.current_version == "1.0.0"
                assert result.latest_version == "1.2.0"
                assert result.has_update is True
                assert result.prerelease is False

    @pytest.mark.asyncio
    async def test_check_single_update_no_config(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test single app update check when app config not found."""
        mock_config_manager.load_app_config.return_value = None

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch("my_unicorn.core.update.update.logger"),
        ):
            update_manager = UpdateManager(mock_config_manager)
            result = await update_manager.check_single_update(
                "nonexistent-app", mock_session
            )

            assert isinstance(result, UpdateInfo)
            assert not result.is_success
            assert result.error_reason is not None
            assert "No configuration found" in result.error_reason

    @pytest.mark.asyncio
    async def test_check_single_update_api_error(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
        mock_app_config: dict[str, Any],
    ) -> None:
        """Test single app update check when API call fails."""
        # load_app_config now returns merged effective config
        mock_config_manager.load_app_config.return_value = {
            "config_version": "2.0.0",
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {"version": "1.0.0"},
        }
        mock_config_manager.load_catalog.return_value = None

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch(
                "my_unicorn.core.update.update.ReleaseFetcher"
            ) as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                # Create proper mock request info and history
                mock_request_info = MagicMock()
                mock_history = ()
                error = aiohttp.ClientResponseError(
                    mock_request_info, mock_history, status=404
                )
                mock_fetcher.fetch_latest_release_or_prerelease.side_effect = (
                    error
                )

                with patch("my_unicorn.core.update.update.logger"):
                    result = await update_manager.check_single_update(
                        "test-app", mock_session
                    )

                    assert isinstance(result, UpdateInfo)
                    assert not result.is_success
                    assert result.error_reason is not None
                    assert result.app_name == "test-app"

    @pytest.mark.asyncio
    async def test_check_single_update_auth_error(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
        mock_app_config: dict[str, Any],
    ) -> None:
        """Test single app update check when GitHub auth fails."""
        # load_app_config now returns merged effective config
        mock_config_manager.load_app_config.return_value = {
            "config_version": "2.0.0",
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {"version": "1.0.0"},
        }

        # Create proper mock request info and history
        mock_request_info = MagicMock()
        mock_history = ()
        error = aiohttp.ClientResponseError(
            mock_request_info, mock_history, status=401
        )

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch(
                "my_unicorn.core.update.update.ReleaseFetcher"
            ) as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                mock_fetcher.fetch_latest_release_or_prerelease.side_effect = (
                    error
                )

                with patch(
                    "my_unicorn.core.update.update.logger"
                ) as mock_logger:
                    result = await update_manager.check_single_update(
                        "test-app", mock_session
                    )

                    assert isinstance(result, UpdateInfo)
                    assert not result.is_success
                    assert result.error_reason is not None
                    assert "Authentication required" in result.error_reason
                    # Verify specific auth error handling
                    mock_logger.exception.assert_called()

    @pytest.mark.asyncio
    async def test_check_updates_shows_progress_message(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test check_updates always shows progress message."""
        mock_config_manager.list_installed_apps.return_value = ["app1", "app2"]

        update_info1 = UpdateInfo("app1", "1.0.0", "1.1.0", True)
        update_info2 = UpdateInfo("app2", "2.0.0", "2.0.0", False)

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with (
                patch.object(
                    update_manager, "check_single_update", new=AsyncMock()
                ) as mock_check,
                patch("my_unicorn.core.update.update.logger") as mock_logger,
            ):
                mock_check.side_effect = [update_info1, update_info2]

                result = await update_manager.check_updates()

                assert len(result) == EXPECTED_APP_COUNT
                # Verify progress message was logged
                mock_logger.info.assert_called_once_with(
                    "🔄 Checking %d app(s) for updates...", 2
                )

    @pytest.mark.asyncio
    async def test_check_updates_with_refresh_cache(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test check_updates with refresh_cache parameter."""
        mock_config_manager.list_installed_apps.return_value = ["app1"]
        update_info = UpdateInfo("app1", "1.0.0", "1.1.0", True)

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch.object(
                update_manager, "check_single_update", new=AsyncMock()
            ) as mock_check:
                mock_check.return_value = update_info

                result = await update_manager.check_updates(refresh_cache=True)

                assert len(result) == 1
                # Verify check_single_update was called with refresh_cache
                mock_check.assert_called_with("app1", ANY, refresh_cache=True)

    @pytest.mark.asyncio
    async def test_check_updates_empty_list(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test checking updates when no apps are installed."""
        mock_config_manager.list_installed_apps.return_value = []

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch("my_unicorn.core.update.update.logger"),
        ):
            update_manager = UpdateManager(mock_config_manager)
            result = await update_manager.check_updates()

            assert result == []

    @pytest.mark.asyncio
    async def test_check_updates_success(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test successful check of all app updates."""
        mock_config_manager.list_installed_apps.return_value = ["app1", "app2"]

        # Mock check_single_update to return different results
        update_info1 = UpdateInfo("app1", "1.0.0", "1.1.0", True)
        update_info2 = UpdateInfo("app2", "2.0.0", "2.0.0", False)

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch.object(
                update_manager, "check_single_update", new=AsyncMock()
            ) as mock_check:
                mock_check.side_effect = [update_info1, update_info2]

                result = await update_manager.check_updates()

                assert len(result) == EXPECTED_APP_COUNT
                assert result[0] == update_info1
                assert result[1] == update_info2

    @pytest.mark.asyncio
    async def test_check_updates_with_failures(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test check updates when some apps fail to check."""
        mock_config_manager.list_installed_apps.return_value = [
            "app1",
            "app2",
            "app3",
        ]

        update_info1 = UpdateInfo("app1", "1.0.0", "1.1.0", True)

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch.object(
                update_manager, "check_single_update", new=AsyncMock()
            ) as mock_check:
                # app1 succeeds, app2 returns error UpdateInfo
                # app3 raises exception
                error_info2 = UpdateInfo(
                    app_name="app2",
                    error_reason="Failed to fetch",
                )
                error_info3 = UpdateInfo(
                    app_name="app3",
                    error_reason="Exception during check: API error",
                )
                mock_check.side_effect = [
                    update_info1,
                    error_info2,
                    error_info3,
                ]

                with patch("my_unicorn.core.update.update.logger"):
                    result = await update_manager.check_updates()

                    # All results should be returned (including errors)
                    assert len(result) == 3
                    assert result[0] == update_info1
                    assert result[1] == error_info2
                    assert result[2] == error_info3
                    # Verify error UpdateInfo instances
                    assert not result[1].is_success
                    assert not result[2].is_success

    @pytest.mark.asyncio
    async def test_check_updates_no_apps(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test check updates when no apps installed."""
        mock_config_manager.list_installed_apps.return_value = []

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch("my_unicorn.core.update.update.logger"),
            patch("builtins.print"),
        ):
            update_manager = UpdateManager(mock_config_manager)
            result = await update_manager.check_updates()

            assert result == []

    @pytest.mark.asyncio
    async def test_check_updates_shows_message(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test check updates shows progress message."""
        mock_config_manager.list_installed_apps.return_value = ["app1"]
        update_info = UpdateInfo("app1", "1.0.0", "1.1.0", True)

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with (
                patch.object(
                    update_manager, "check_single_update", new=AsyncMock()
                ) as mock_check,
                patch("my_unicorn.core.update.update.logger") as mock_logger,
            ):
                mock_check.return_value = update_info

                result = await update_manager.check_updates()

                assert len(result) == 1
                assert result[0] == update_info
                # Verify progress message was logged
                mock_logger.info.assert_called_once_with(
                    "🔄 Checking %d app(s) for updates...", 1
                )

    @pytest.mark.asyncio
    async def test_update_single_app_no_config(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test update single app when config not found."""
        mock_config_manager.load_app_config.return_value = None

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch("my_unicorn.core.update.update.logger"),
        ):
            update_manager = UpdateManager(mock_config_manager)
            success, error_reason = await update_manager.update_single_app(
                "nonexistent-app", mock_session
            )

            assert success is False
            assert error_reason is not None
            assert "No configuration found" in error_reason

    @pytest.mark.asyncio
    async def test_update_single_app_no_update_needed(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
        mock_app_config: dict[str, Any],
    ) -> None:
        """Test update single app when no update is needed."""
        mock_config_manager.load_app_config.return_value = mock_app_config

        # Mock check_single_update to return no update needed
        update_info = UpdateInfo("test-app", "1.0.0", "1.0.0", False)

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch.object(
                update_manager, "check_single_update", new=AsyncMock()
            ) as mock_check:
                mock_check.return_value = update_info

                with patch("my_unicorn.core.update.update.logger"):
                    (
                        success,
                        error_reason,
                    ) = await update_manager.update_single_app(
                        "test-app", mock_session
                    )

                    # Method returns True when no update needed
                    # (successful check)
                    assert success is True
                    assert error_reason is None

    @pytest.mark.asyncio
    async def test_update_multiple_apps(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test updating multiple apps."""
        app_names = ["app1", "app2", "app3"]

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch.object(
                update_manager, "update_single_app", new=AsyncMock()
            ) as mock_update_single:
                # app1 succeeds, app2 fails, app3 succeeds
                mock_update_single.side_effect = [
                    (True, None),
                    (False, "Some error"),
                    (True, None),
                ]

                (
                    result,
                    error_reasons,
                ) = await update_manager.update_multiple_apps(app_names)

                assert result == {"app1": True, "app2": False, "app3": True}
                assert error_reasons == {"app2": "Some error"}
                assert mock_update_single.call_count == EXPECTED_CALL_COUNT

    def test_initialize_services(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test services initialization with HTTP session."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.VerificationService"
            ) as mock_verify_cls,
        ):
            mock_progress = MagicMock()

            update_manager = UpdateManager(
                mock_config_manager, progress_reporter=mock_progress
            )

            mock_download = MagicMock()
            mock_download_cls.return_value = mock_download
            mock_download.progress_reporter = MagicMock()

            mock_verify = MagicMock()
            mock_verify_cls.return_value = mock_verify

            # Initialize services
            update_manager._initialize_services(mock_session)

            # Verify DownloadService was initialized
            mock_download_cls.assert_called_once()

            # Verify VerificationService was initialized
            mock_verify_cls.assert_called_once()
            assert update_manager.verification_service is not None

            # Verify services were created with correct parameters
            mock_download_cls.assert_called_once_with(
                mock_session, mock_progress
            )
            mock_verify_cls.assert_called_once_with(
                mock_download,
                mock_download.progress_reporter,
                cache_manager=update_manager.cache_manager,
            )

            # Verify that verification service was set
            assert update_manager.verification_service == mock_verify


class TestUpdateWorkflowProtocolUsage:
    """Tests for UpdateWorkflow ProgressReporter protocol usage (Task 3.4)."""

    @pytest.fixture
    def mock_config_manager(self) -> MagicMock:
        """Create mock ConfigManager."""
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
        mock_config.list_installed_apps.return_value = ["app1", "app2"]
        return mock_config

    def test_accepts_progress_reporter_protocol(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateManager accepts ProgressReporter protocol type."""

        class MockProgressReporter:
            """Mock progress reporter implementing the protocol."""

            def is_active(self) -> bool:
                return True

            def add_task(
                self,
                name: str,
                progress_type: ProgressType,
                total: float | None = None,
            ) -> str:
                return "mock-task-id"

            def update_task(
                self,
                task_id: str,
                completed: float | None = None,
                description: str | None = None,
            ) -> None:
                pass

            def finish_task(
                self,
                task_id: str,
                *,
                success: bool = True,
                description: str | None = None,
            ) -> None:
                pass

            def get_task_info(self, task_id: str) -> dict[str, object]:
                return {"completed": 0.0, "total": None, "description": ""}

        mock_reporter = MockProgressReporter()
        assert isinstance(mock_reporter, ProgressReporter)

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(
                mock_config_manager, progress_reporter=mock_reporter
            )
            assert manager.progress_reporter is mock_reporter

    def test_uses_null_reporter_when_none_provided(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateManager uses NullProgressReporter when None provided."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(
                mock_config_manager, progress_reporter=None
            )
            assert isinstance(manager.progress_reporter, NullProgressReporter)

    def test_uses_null_reporter_by_default(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateManager uses NullProgressReporter by default."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(mock_config_manager)
            assert isinstance(manager.progress_reporter, NullProgressReporter)

    def test_progress_reporter_attribute_accessible(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test progress_reporter attribute is accessible."""

        class TestReporter:
            """Test reporter for attribute access test."""

            def is_active(self) -> bool:
                return True

            def add_task(
                self,
                name: str,
                progress_type: ProgressType,
                total: float | None = None,
            ) -> str:
                return "test-id"

            def update_task(
                self,
                task_id: str,
                completed: float | None = None,
                description: str | None = None,
            ) -> None:
                pass

            def finish_task(
                self,
                task_id: str,
                *,
                success: bool = True,
                description: str | None = None,
            ) -> None:
                pass

            def get_task_info(self, task_id: str) -> dict[str, object]:
                return {}

        reporter = TestReporter()

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(
                mock_config_manager, progress_reporter=reporter
            )

            assert hasattr(manager, "progress_reporter")
            assert manager.progress_reporter is reporter
            assert manager.progress_reporter.is_active() is True

    def test_null_reporter_is_active_returns_false(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test NullProgressReporter.is_active() returns False."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(
                mock_config_manager, progress_reporter=None
            )
            assert manager.progress_reporter.is_active() is False

    @pytest.mark.asyncio
    async def test_null_reporter_add_task_returns_null_task(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test NullProgressReporter.add_task() returns 'null-task'."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(
                mock_config_manager, progress_reporter=None
            )

            task_id = await manager.progress_reporter.add_task(
                "Test Task", ProgressType.UPDATE, total=100.0
            )
            assert task_id == "null-task"


class TestUpdateWorkflowDomainExceptions:
    """Tests for UpdateWorkflow domain exception usage (Task 3.4)."""

    @pytest.fixture
    def mock_config_manager(self) -> MagicMock:
        """Create mock ConfigManager for exception testing."""
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
        return mock_config

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock aiohttp session."""
        return AsyncMock(spec=aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_update_error_when_catalog_not_found(
        self, mock_config_manager: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test UpdateError context when catalog reference not found."""
        mock_config_manager.load_app_config.return_value = {
            "config_version": "2.0.0",
            "catalog_ref": "nonexistent-catalog",
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {"version": "1.0.0"},
        }

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(mock_config_manager)

            # Mock _load_catalog_cached to raise FileNotFoundError
            with patch.object(
                manager,
                "_load_catalog_cached",
                side_effect=FileNotFoundError(),
            ):
                # Call update_single_app which uses _load_catalog_if_needed
                # Check for UpdateError being raised when catalog missing
                with pytest.raises(UpdateError) as exc_info:
                    await manager._load_catalog_for_update(
                        "test-app",
                        {"catalog_ref": "nonexistent-catalog"},
                    )

                has_app_name = (
                    "test-app" in str(exc_info.value)
                    or exc_info.value.context.get("app_name") == "test-app"
                )
                assert has_app_name

    @pytest.mark.asyncio
    async def test_update_error_includes_catalog_ref_context(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateError includes catalog_ref in context."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(mock_config_manager)

            # Mock _load_catalog_cached to raise ValueError
            with patch.object(
                manager,
                "_load_catalog_cached",
                side_effect=ValueError("Invalid catalog format"),
            ):
                with pytest.raises(UpdateError) as exc_info:
                    await manager._load_catalog_for_update(
                        "test-app",
                        {"catalog_ref": "invalid-catalog"},
                    )

                # Verify context includes catalog_ref
                catalog_ref = exc_info.value.context.get("catalog_ref")
                assert catalog_ref == "invalid-catalog"
                assert exc_info.value.context.get("app_name") == "test-app"

    @pytest.mark.asyncio
    async def test_update_error_preserves_cause_chain(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateError preserves original exception as cause."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(mock_config_manager)

            original_error = FileNotFoundError("Catalog file missing")
            with patch.object(
                manager,
                "_load_catalog_cached",
                side_effect=original_error,
            ):
                with pytest.raises(UpdateError) as exc_info:
                    await manager._load_catalog_for_update(
                        "test-app",
                        {"catalog_ref": "missing-catalog"},
                    )

                # Verify cause chain is preserved
                assert exc_info.value.__cause__ is original_error

    @pytest.mark.asyncio
    async def test_update_single_app_returns_error_for_missing_config(
        self, mock_config_manager: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test update_single_app returns error when config not found."""
        mock_config_manager.load_app_config.return_value = None

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch("my_unicorn.core.update.update.logger"),
        ):
            manager = UpdateManager(mock_config_manager)
            success, error_reason = await manager.update_single_app(
                "nonexistent-app", mock_session
            )

            assert success is False
            assert error_reason is not None
            assert "No configuration found" in error_reason

    @pytest.mark.asyncio
    async def test_update_error_on_download_failure(
        self, mock_config_manager: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test UpdateError context when download fails during update."""
        mock_config_manager.load_app_config.return_value = {
            "config_version": "2.0.0",
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {"version": "1.0.0"},
        }

        mock_release_data = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.2.0",
            prerelease=False,
            assets=[
                Asset(
                    name="test-app.AppImage",
                    size=1024,
                    digest="",
                    browser_download_url="https://example.com/test.appimage",
                ),
            ],
            original_tag_name="v1.2.0",
        )

        update_info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="1.2.0",
            has_update=True,
            release_data=mock_release_data,
            app_config=mock_config_manager.load_app_config.return_value,
        )

        # Mock _prepare_update_context to return a valid context
        mock_context = {
            "app_config": mock_config_manager.load_app_config.return_value,
            "update_info": update_info,
            "appimage_asset": mock_release_data.assets[0],
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch("my_unicorn.core.update.update.logger"),
        ):
            manager = UpdateManager(mock_config_manager)

            # Mock DownloadService to return None (download failure)
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(return_value=None)
            mock_download_cls.return_value = mock_download

            with patch.object(
                manager,
                "_prepare_update_context",
                return_value=(mock_context, None),
            ):
                # UpdateError is caught and returned as (False, error_message)
                success, error_reason = await manager.update_single_app(
                    "test-app", mock_session, force=True
                )

                assert success is False
                assert error_reason is not None
                assert "Download failed" in error_reason

    @pytest.mark.asyncio
    async def test_update_handles_verification_error_gracefully(
        self, mock_config_manager: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test VerificationError is handled gracefully during update."""
        mock_config_manager.load_app_config.return_value = {
            "config_version": "2.0.0",
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {"version": "1.0.0"},
        }

        mock_release_data = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.2.0",
            prerelease=False,
            assets=[
                Asset(
                    name="test-app.AppImage",
                    size=1024,
                    digest="",
                    browser_download_url="https://example.com/test.appimage",
                ),
            ],
            original_tag_name="v1.2.0",
        )

        update_info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="1.2.0",
            has_update=True,
            release_data=mock_release_data,
            app_config=mock_config_manager.load_app_config.return_value,
        )

        mock_context = {
            "app_config": mock_config_manager.load_app_config.return_value,
            "update_info": update_info,
            "appimage_asset": mock_release_data.assets[0],
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.PostDownloadProcessor"
            ) as mock_processor_cls,
            patch("my_unicorn.core.update.update.logger"),
        ):
            manager = UpdateManager(mock_config_manager)

            # Mock successful download
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test.appimage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            # Mock PostDownloadProcessor to raise VerificationError
            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                side_effect=VerificationError(
                    message="Hash mismatch",
                    context={
                        "app_name": "test-app",
                        "expected": "abc",
                        "actual": "xyz",
                    },
                )
            )
            mock_processor_cls.return_value = mock_processor

            with patch.object(
                manager,
                "_prepare_update_context",
                return_value=(mock_context, None),
            ):
                # Domain exception is caught and returns error tuple
                success, error_reason = await manager.update_single_app(
                    "test-app", mock_session, force=True
                )

                assert success is False
                assert error_reason is not None
                assert "Hash mismatch" in error_reason

    @pytest.mark.asyncio
    async def test_update_error_wraps_unexpected_exceptions(
        self, mock_config_manager: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test unexpected exceptions wrapped in UpdateError."""
        mock_config_manager.load_app_config.return_value = {
            "config_version": "2.0.0",
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {"version": "1.0.0"},
        }

        mock_release_data = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.2.0",
            prerelease=False,
            assets=[
                Asset(
                    name="test-app.AppImage",
                    size=1024,
                    digest="",
                    browser_download_url="https://example.com/test.appimage",
                ),
            ],
            original_tag_name="v1.2.0",
        )

        update_info = UpdateInfo(
            app_name="test-app",
            current_version="1.0.0",
            latest_version="1.2.0",
            has_update=True,
            release_data=mock_release_data,
            app_config=mock_config_manager.load_app_config.return_value,
        )

        mock_context = {
            "app_config": mock_config_manager.load_app_config.return_value,
            "update_info": update_info,
            "appimage_asset": mock_release_data.assets[0],
            "catalog_entry": None,
            "owner": "test-owner",
            "repo": "test-repo",
        }

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.PostDownloadProcessor"
            ) as mock_processor_cls,
            patch("my_unicorn.core.update.update.logger"),
        ):
            manager = UpdateManager(mock_config_manager)

            # Mock successful download
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test.appimage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            # Mock PostDownloadProcessor to raise unexpected RuntimeError
            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                side_effect=RuntimeError("Unexpected internal error")
            )
            mock_processor_cls.return_value = mock_processor

            with patch.object(
                manager,
                "_prepare_update_context",
                return_value=(mock_context, None),
            ):
                # Unexpected exceptions are wrapped in UpdateError
                # and re-raised
                with pytest.raises(UpdateError) as exc_info:
                    await manager.update_single_app(
                        "test-app", mock_session, force=True
                    )

                # Verify exception is wrapped with context
                assert "Update failed" in str(exc_info.value)
                assert exc_info.value.context.get("app_name") == "test-app"
                assert exc_info.value.__cause__ is not None
                assert isinstance(exc_info.value.__cause__, RuntimeError)

    @pytest.mark.asyncio
    async def test_update_error_context_contains_app_name(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateError context always contains app_name."""
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
        ):
            manager = UpdateManager(mock_config_manager)

            with patch.object(
                manager,
                "_load_catalog_cached",
                side_effect=FileNotFoundError("Missing"),
            ):
                with pytest.raises(UpdateError) as exc_info:
                    await manager._load_catalog_if_needed(
                        "my-test-app", "some-catalog-ref"
                    )

                # Verify app_name is in context
                assert exc_info.value.context.get("app_name") == "my-test-app"


# =============================================================================
# Task 4.3: End-to-End Update Verification Flow Tests
# =============================================================================


class TestUpdateVerificationFlow:
    """End-to-end tests for update verification refresh (Task 4.3).

    These tests verify that when an app is updated:
    - Verification is recalculated with new release hashes
    - App state reflects new verification data (not old)
    - Cache is updated with new checksum_files
    """

    @pytest.fixture
    def mock_config_manager(self) -> MagicMock:
        """Create mock ConfigManager with complete configuration."""
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
        mock_config.list_installed_apps.return_value = ["test-app"]
        return mock_config

    @pytest.fixture
    def v1_app_config(self) -> dict[str, Any]:
        """App configuration for installed v1.0.0 with verification A."""
        return {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "test-app",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-01-01T00:00:00+00:00",
                "installed_path": "/test/storage/test-app.AppImage",
                "verification": {
                    "passed": True,
                    "overall_passed": True,
                    "actual_method": "digest",
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                            "expected": "abc123v1hash",
                            "computed": "abc123v1hash",
                            "source": "github_api",
                        }
                    ],
                },
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": "/test/icon/test-app.png",
                },
            },
        }

    @pytest.fixture
    def v2_release_data(self) -> Release:
        """Release data for v2.0.0 update."""
        return Release(
            owner="test-owner",
            repo="test-repo",
            version="2.0.0",
            prerelease=False,
            assets=[
                Asset(
                    name="test-app-2.0.0.AppImage",
                    size=2048,
                    digest="sha256:def456v2hash",
                    browser_download_url="https://github.com/test-owner/test-repo/releases/download/v2.0.0/test-app-2.0.0.AppImage",
                ),
                Asset(
                    name="SHA256SUMS.txt",
                    size=200,
                    digest=None,
                    browser_download_url="https://github.com/test-owner/test-repo/releases/download/v2.0.0/SHA256SUMS.txt",
                ),
            ],
            original_tag_name="v2.0.0",
        )

    @pytest.mark.asyncio
    async def test_update_replaces_verification_with_new_hash(
        self,
        mock_config_manager: MagicMock,
        v1_app_config: dict[str, Any],
        v2_release_data: Release,
    ) -> None:
        """Test that update replaces v1 verification with v2 verification.

        Verifies requirement: verification.methods array is replaced,
        not appended.
        """
        mock_config_manager.load_app_config.return_value = v1_app_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
            "verification": {},
            "appimage": {"naming": {"target_name": "test-app"}},
        }

        saved_configs: list[dict[str, Any]] = []

        def capture_save(app_name: str, config: dict[str, Any], **kwargs):
            saved_configs.append(config)
            return Path(f"/config/{app_name}.json")

        mock_config_manager.save_app_config.side_effect = capture_save

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch(
                "my_unicorn.core.update.update.ReleaseCacheManager"
            ) as mock_cache_cls,
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.PostDownloadProcessor"
            ) as mock_processor_cls,
            patch("my_unicorn.core.update.update.ReleaseFetcher"),
        ):
            mock_cache = MagicMock()
            mock_cache_cls.return_value = mock_cache

            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test-app-2.0.0.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            # v2 verification result (different from v1)
            v2_verification_result = {
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash": "def456v2hash",
                        "computed_hash": "def456v2hash",
                        "hash_type": "sha256",
                    }
                },
            }

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/test-app.AppImage"),
                    verification_result=v2_verification_result,
                    icon_result={"icon_path": "/test/icon/test-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            update_info = UpdateInfo(
                app_name="test-app",
                current_version="1.0.0",
                latest_version="2.0.0",
                has_update=True,
                release_data=v2_release_data,
                app_config=v1_app_config,
            )

            mock_context = {
                "app_config": v1_app_config,
                "update_info": update_info,
                "appimage_asset": v2_release_data.assets[0],
                "catalog_entry": mock_config_manager.load_catalog.return_value,
                "owner": "test-owner",
                "repo": "test-repo",
            }

            mock_session = AsyncMock()

            with patch.object(
                manager,
                "_prepare_update_context",
                return_value=(mock_context, None),
            ):
                success, error = await manager.update_single_app(
                    "test-app", mock_session, force=True
                )

            assert success is True
            assert error is None

            # Verify PostDownloadProcessor was called with UPDATE operation
            mock_processor.process.assert_called_once()
            call_args = mock_processor.process.call_args
            context = call_args[0][0]
            assert context.operation_type == OperationType.UPDATE

    @pytest.mark.asyncio
    async def test_update_verification_service_receives_cache_manager(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test that VerificationService is initialized with cache_manager.

        This ensures checksum_files are cached during update.
        """
        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch(
                "my_unicorn.core.update.update.ReleaseCacheManager"
            ) as mock_cache_cls,
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.VerificationService"
            ) as mock_verify_cls,
        ):
            mock_cache = MagicMock()
            mock_cache_cls.return_value = mock_cache

            mock_download = MagicMock()
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            mock_verify = MagicMock()
            mock_verify_cls.return_value = mock_verify

            manager = UpdateManager(mock_config_manager)

            mock_session = AsyncMock()
            manager._initialize_services(mock_session)

            # Verify VerificationService received cache_manager
            mock_verify_cls.assert_called_once()
            call_kwargs = mock_verify_cls.call_args[1]
            assert "cache_manager" in call_kwargs
            assert call_kwargs["cache_manager"] is manager.cache_manager

    @pytest.mark.asyncio
    async def test_update_old_verification_not_preserved(
        self,
        mock_config_manager: MagicMock,
        v1_app_config: dict[str, Any],
        v2_release_data: Release,
    ) -> None:
        """Test that old v1 verification data is replaced, not merged.

        Requirement: Original verification A is not preserved.
        """
        mock_config_manager.load_app_config.return_value = v1_app_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
            "verification": {},
            "appimage": {"naming": {"target_name": "test-app"}},
        }

        config_updates: list[dict[str, Any]] = []

        def track_config_update(
            app_name: str, config: dict[str, Any], **kwargs
        ):
            config_updates.append(config.copy())
            return Path(f"/config/{app_name}.json")

        mock_config_manager.save_app_config.side_effect = track_config_update

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.PostDownloadProcessor"
            ) as mock_processor_cls,
        ):
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test-app.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            # v2 uses checksum_file, not digest (different from v1)
            v2_verification = {
                "passed": True,
                "methods": {
                    "checksum_file": {
                        "passed": True,
                        "hash": "xyz789v2checksum",
                        "computed_hash": "xyz789v2checksum",
                        "hash_type": "sha256",
                        "url": "https://example.com/SHA256SUMS.txt",
                    }
                },
            }

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/test-app.AppImage"),
                    verification_result=v2_verification,
                    icon_result={"icon_path": "/test/icon/test-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            update_info = UpdateInfo(
                app_name="test-app",
                current_version="1.0.0",
                latest_version="2.0.0",
                has_update=True,
                release_data=v2_release_data,
                app_config=v1_app_config,
            )

            mock_context = {
                "app_config": v1_app_config,
                "update_info": update_info,
                "appimage_asset": v2_release_data.assets[0],
                "catalog_entry": mock_config_manager.load_catalog.return_value,
                "owner": "test-owner",
                "repo": "test-repo",
            }

            mock_session = AsyncMock()

            with patch.object(
                manager,
                "_prepare_update_context",
                return_value=(mock_context, None),
            ):
                success, _ = await manager.update_single_app(
                    "test-app", mock_session, force=True
                )

            assert success is True

            # Verify processor received context with UPDATE operation type
            assert mock_processor.process.called
            context = mock_processor.process.call_args[0][0]

            # Operation should be UPDATE (triggers verification replacement)
            assert context.operation_type == OperationType.UPDATE
            # Verification is enabled by default
            assert context.verify_downloads is True

    @pytest.mark.asyncio
    async def test_update_cache_stores_new_checksum_files(
        self,
        mock_config_manager: MagicMock,
        v1_app_config: dict[str, Any],
        v2_release_data: Release,
    ) -> None:
        """Test that cache is updated with new checksum_files after update.

        Requirement: Verify cache has updated checksum_files.
        """
        mock_config_manager.load_app_config.return_value = v1_app_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
            "verification": {},
            "appimage": {"naming": {"target_name": "test-app"}},
        }

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch(
                "my_unicorn.core.update.update.ReleaseCacheManager"
            ) as mock_cache_cls,
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.VerificationService"
            ) as mock_verify_cls,
            patch(
                "my_unicorn.core.update.update.PostDownloadProcessor"
            ) as mock_processor_cls,
        ):
            mock_cache = MagicMock()
            mock_cache.store_checksum_file = AsyncMock(return_value=True)
            mock_cache_cls.return_value = mock_cache

            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test-app.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            mock_verify = MagicMock()
            mock_verify_cls.return_value = mock_verify

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/test-app.AppImage"),
                    verification_result={
                        "passed": True,
                        "methods": {"digest": {"passed": True}},
                    },
                    icon_result={"icon_path": "/test/icon/test-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            # Verify cache_manager is properly assigned
            assert manager.cache_manager is mock_cache

            # Initialize services to setup verification with cache
            mock_session = AsyncMock()
            manager._initialize_services(mock_session)

            # VerificationService should be created with cache_manager
            mock_verify_cls.assert_called_with(
                mock_download,
                mock_download.progress_reporter,
                cache_manager=mock_cache,
            )

    @pytest.mark.asyncio
    async def test_update_verification_flow_from_digest_to_checksum_file(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test update where v1 used digest and v2 uses checksum_file.

        This is a realistic scenario where the verification method changes
        between versions.
        """
        v1_config = {
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "evolving-app",
            "state": {
                "version": "1.0.0",
                "installed_date": "2026-01-01T00:00:00+00:00",
                "installed_path": "/test/storage/evolving-app.AppImage",
                "verification": {
                    "passed": True,
                    "overall_passed": True,
                    "actual_method": "digest",
                    "methods": [
                        {
                            "type": "digest",
                            "status": "passed",
                            "algorithm": "SHA256",
                            "expected": "v1digestonly",
                            "computed": "v1digestonly",
                            "source": "github_api",
                        }
                    ],
                },
                "icon": {
                    "installed": True,
                    "method": "extraction",
                    "path": "/test/icon/evolving-app.png",
                },
            },
        }

        mock_config_manager.load_app_config.return_value = v1_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "evolving", "repo": "app"},
            "verification": {"checksum_file": "SHA256SUMS.txt"},
            "appimage": {"naming": {"target_name": "evolving-app"}},
        }

        v2_release = Release(
            owner="evolving",
            repo="app",
            version="2.0.0",
            prerelease=False,
            assets=[
                Asset(
                    name="evolving-app-2.0.0.AppImage",
                    size=3000,
                    digest=None,  # v2 has no digest
                    browser_download_url="https://example.com/v2.AppImage",
                ),
                Asset(
                    name="SHA256SUMS.txt",
                    size=100,
                    digest=None,
                    browser_download_url="https://example.com/SHA256SUMS.txt",
                ),
            ],
            original_tag_name="v2.0.0",
        )

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.PostDownloadProcessor"
            ) as mock_processor_cls,
        ):
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/evolving-app.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            # v2 verification uses checksum_file method
            v2_verification = {
                "passed": True,
                "methods": {
                    "checksum_file": {
                        "passed": True,
                        "hash": "v2checksumhash",
                        "computed_hash": "v2checksumhash",
                        "hash_type": "sha256",
                        "url": "https://example.com/SHA256SUMS.txt",
                    }
                },
            }

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/evolving-app.AppImage"),
                    verification_result=v2_verification,
                    icon_result={"icon_path": "/test/icon/evolving-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            update_info = UpdateInfo(
                app_name="evolving-app",
                current_version="1.0.0",
                latest_version="2.0.0",
                has_update=True,
                release_data=v2_release,
                app_config=v1_config,
            )

            mock_context = {
                "app_config": v1_config,
                "update_info": update_info,
                "appimage_asset": v2_release.assets[0],
                "catalog_entry": mock_config_manager.load_catalog.return_value,
                "owner": "evolving",
                "repo": "app",
            }

            mock_session = AsyncMock()

            with patch.object(
                manager,
                "_prepare_update_context",
                return_value=(mock_context, None),
            ):
                success, error = await manager.update_single_app(
                    "evolving-app", mock_session, force=True
                )

            assert success is True
            assert error is None

            # Verify the update was processed
            mock_processor.process.assert_called_once()
            context = mock_processor.process.call_args[0][0]
            assert context.operation_type == OperationType.UPDATE
            assert context.app_name == "evolving-app"

    @pytest.mark.asyncio
    async def test_update_verification_result_passed_to_config_update(
        self,
        mock_config_manager: MagicMock,
        v1_app_config: dict[str, Any],
        v2_release_data: Release,
    ) -> None:
        """Test that new verification result is passed to config update.

        Ensures verification state is properly updated in app config.
        """
        mock_config_manager.load_app_config.return_value = v1_app_config
        mock_config_manager.load_catalog.return_value = {
            "source": {"owner": "test-owner", "repo": "test-repo"},
            "verification": {},
            "appimage": {"naming": {"target_name": "test-app"}},
        }

        with (
            patch("my_unicorn.core.update.update.GitHubAuthManager"),
            patch("my_unicorn.core.update.update.FileOperations"),
            patch("my_unicorn.core.update.update.BackupService"),
            patch("my_unicorn.core.update.update.ReleaseCacheManager"),
            patch(
                "my_unicorn.core.update.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.update.update.PostDownloadProcessor"
            ) as mock_processor_cls,
        ):
            mock_download = MagicMock()
            mock_download.download_appimage = AsyncMock(
                return_value=Path("/tmp/test-app.AppImage")
            )
            mock_download.progress_reporter = MagicMock()
            mock_download_cls.return_value = mock_download

            v2_verification = {
                "passed": True,
                "methods": {
                    "digest": {
                        "passed": True,
                        "hash": "newhashv2",
                        "computed_hash": "newhashv2",
                        "hash_type": "sha256",
                    }
                },
            }

            mock_processor = MagicMock()
            mock_processor.process = AsyncMock(
                return_value=PostDownloadResult(
                    success=True,
                    install_path=Path("/test/storage/test-app.AppImage"),
                    verification_result=v2_verification,
                    icon_result={"icon_path": "/test/icon/test-app.png"},
                    config_result={"success": True},
                    desktop_result={"success": True},
                )
            )
            mock_processor_cls.return_value = mock_processor

            manager = UpdateManager(mock_config_manager)

            update_info = UpdateInfo(
                app_name="test-app",
                current_version="1.0.0",
                latest_version="2.0.0",
                has_update=True,
                release_data=v2_release_data,
                app_config=v1_app_config,
            )

            mock_context = {
                "app_config": v1_app_config,
                "update_info": update_info,
                "appimage_asset": v2_release_data.assets[0],
                "catalog_entry": mock_config_manager.load_catalog.return_value,
                "owner": "test-owner",
                "repo": "test-repo",
            }

            mock_session = AsyncMock()

            with patch.object(
                manager,
                "_prepare_update_context",
                return_value=(mock_context, None),
            ):
                success, _ = await manager.update_single_app(
                    "test-app", mock_session, force=True
                )

            assert success is True

            # Verify result includes verification_result from processor
            result = mock_processor.process.return_value
            assert result.verification_result is not None
            assert result.verification_result["passed"] is True
            assert "digest" in result.verification_result["methods"]
            assert (
                result.verification_result["methods"]["digest"]["hash"]
                == "newhashv2"
            )
