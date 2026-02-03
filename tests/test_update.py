"""Tests for update management functionality."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import aiohttp
import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
    ProgressType,
)
from my_unicorn.core.workflows.update import UpdateInfo, UpdateManager
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
        ):
            manager = UpdateManager(mock_config_manager)
            return manager

    def test_init_with_config_manager(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateManager initialization with provided config manager."""
        with (
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
        ):
            manager = UpdateManager(mock_config_manager)

            assert manager.config_manager == mock_config_manager
            mock_config_manager.load_global_config.assert_called_once()

    def test_init_default_config_manager(self) -> None:
        """Test UpdateManager initialization with default config manager."""
        with (
            patch(
                "my_unicorn.core.workflows.update.ConfigManager"
            ) as mock_config_cls,
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
                "my_unicorn.core.workflows.update.ReleaseFetcher"
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch(
                "my_unicorn.core.workflows.update.ReleaseFetcher"
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch("my_unicorn.core.workflows.update.logger"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch(
                "my_unicorn.core.workflows.update.ReleaseFetcher"
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

                with patch("my_unicorn.core.workflows.update.logger"):
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch(
                "my_unicorn.core.workflows.update.ReleaseFetcher"
            ) as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                mock_fetcher.fetch_latest_release_or_prerelease.side_effect = (
                    error
                )

                with patch(
                    "my_unicorn.core.workflows.update.logger"
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with (
                patch.object(
                    update_manager, "check_single_update", new=AsyncMock()
                ) as mock_check,
                patch(
                    "my_unicorn.core.workflows.update.logger"
                ) as mock_logger,
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch("my_unicorn.core.workflows.update.logger"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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

                with patch("my_unicorn.core.workflows.update.logger"):
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch("my_unicorn.core.workflows.update.logger"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with (
                patch.object(
                    update_manager, "check_single_update", new=AsyncMock()
                ) as mock_check,
                patch(
                    "my_unicorn.core.workflows.update.logger"
                ) as mock_logger,
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch("my_unicorn.core.workflows.update.logger"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch.object(
                update_manager, "check_single_update", new=AsyncMock()
            ) as mock_check:
                mock_check.return_value = update_info

                with patch("my_unicorn.core.workflows.update.logger"):
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch(
                "my_unicorn.core.workflows.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.workflows.update.VerificationService"
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
                mock_download, mock_download.progress_reporter
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch("my_unicorn.core.workflows.update.logger"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch(
                "my_unicorn.core.workflows.update.DownloadService"
            ) as mock_download_cls,
            patch("my_unicorn.core.workflows.update.logger"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch(
                "my_unicorn.core.workflows.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.workflows.update.PostDownloadProcessor"
            ) as mock_processor_cls,
            patch("my_unicorn.core.workflows.update.logger"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch(
                "my_unicorn.core.workflows.update.DownloadService"
            ) as mock_download_cls,
            patch(
                "my_unicorn.core.workflows.update.PostDownloadProcessor"
            ) as mock_processor_cls,
            patch("my_unicorn.core.workflows.update.logger"),
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
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
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
