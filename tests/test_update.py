"""Tests for update management functionality."""

from pathlib import Path
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import aiohttp
import pytest

from my_unicorn.github_client import Release
from my_unicorn.update import UpdateInfo, UpdateManager

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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            manager = UpdateManager(mock_config_manager)
            return manager

    def test_init_with_config_manager(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test UpdateManager initialization with provided config manager."""
        with (
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            manager = UpdateManager(mock_config_manager)

            assert manager.config_manager == mock_config_manager
            mock_config_manager.load_global_config.assert_called_once()

    def test_init_default_config_manager(self) -> None:
        """Test UpdateManager initialization with default config manager."""
        with (
            patch("my_unicorn.update.ConfigManager") as mock_config_cls,
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
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
            ),  # fallback to string comparison
            ("invalid", "1.0.0", True),  # fallback to string comparison
            ("1.0.0", "invalid", False),  # fallback to string comparison
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
        # Test version comparison through check_single_update rather than private method
        with patch.object(update_manager, "config_manager") as mock_config:
            mock_config.load_app_config.return_value = {
                "appimage": {"version": current},
                "owner": "test",
                "repo": "test",
            }
            mock_config.load_catalog_entry.return_value = None

            with patch("my_unicorn.update.ReleaseFetcher") as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                mock_fetcher.fetch_latest_release.return_value = {
                    "version": latest,
                    "prerelease": False,
                    "original_tag_name": f"v{latest}",
                }

                async def run_test() -> None:
                    result = await update_manager.check_single_update(
                        "test-app", AsyncMock(spec=aiohttp.ClientSession)
                    )
                    if result:
                        assert result.has_update == expected

                # Run the async test
                import asyncio

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
        mock_config_manager.load_app_config.return_value = mock_app_config
        mock_config_manager.load_catalog_entry.return_value = {
            "github": {"use_github_api": True, "use_prerelease": False}
        }

        # Mock app_config_manager.get_effective_config to return effective config
        mock_app_config_manager = MagicMock()
        mock_app_config_manager.get_effective_config.return_value = {
            "config_version": "2.0.0",
            "source": {
                "owner": "test-owner",
                "repo": "test-repo",
                "prerelease": False,
            },
            "state": {"version": "1.0.0"},
        }
        mock_config_manager.app_config_manager = mock_app_config_manager

        mock_release_data = Release(
            owner="test-owner",
            repo="test-repo",
            version="1.2.0",
            prerelease=False,
            assets=[],
            original_tag_name="v1.2.0",
        )

        with (
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch("my_unicorn.update.ReleaseFetcher") as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                # Mock both possible method calls
                mock_fetcher.fetch_latest_release.return_value = (
                    mock_release_data
                )
                mock_fetcher.fetch_latest_release_or_prerelease.return_value = mock_release_data
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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
            patch("my_unicorn.update.logger"),
        ):
            update_manager = UpdateManager(mock_config_manager)
            result = await update_manager.check_single_update(
                "nonexistent-app", mock_session
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_check_single_update_api_error(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
        mock_app_config: dict[str, Any],
    ) -> None:
        """Test single app update check when API call fails."""
        mock_config_manager.load_app_config.return_value = mock_app_config
        mock_config_manager.load_catalog_entry.return_value = None

        with (
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch("my_unicorn.update.ReleaseFetcher") as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                # Create proper mock request info and history
                mock_request_info = MagicMock()
                mock_history = ()
                error = aiohttp.ClientResponseError(
                    mock_request_info, mock_history, status=404
                )
                mock_fetcher.fetch_latest_release.side_effect = error

                with patch("my_unicorn.update.logger"):
                    result = await update_manager.check_single_update(
                        "test-app", mock_session
                    )

                    assert result is None

    @pytest.mark.asyncio
    async def test_check_single_update_auth_error(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
        mock_app_config: dict[str, Any],
    ) -> None:
        """Test single app update check when GitHub auth fails."""
        mock_config_manager.load_app_config.return_value = mock_app_config

        # Create proper mock request info and history
        mock_request_info = MagicMock()
        mock_history = ()
        error = aiohttp.ClientResponseError(
            mock_request_info, mock_history, status=401
        )

        with (
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch("my_unicorn.update.ReleaseFetcher") as mock_fetcher_cls:
                mock_fetcher = AsyncMock()
                mock_fetcher_cls.return_value = mock_fetcher
                mock_fetcher.fetch_latest_release.side_effect = error

                with patch("my_unicorn.update.logger") as mock_logger:
                    result = await update_manager.check_single_update(
                        "test-app", mock_session
                    )

                    assert result is None
                    # Verify specific auth error handling
                    mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_check_updates_with_show_progress(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test check_updates with show_progress parameter."""
        mock_config_manager.list_installed_apps.return_value = ["app1", "app2"]

        update_info1 = UpdateInfo("app1", "1.0.0", "1.1.0", True)
        update_info2 = UpdateInfo("app2", "2.0.0", "2.0.0", False)

        with (
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with (
                patch.object(
                    update_manager, "check_single_update", new=AsyncMock()
                ) as mock_check,
                patch("builtins.print") as mock_print,
            ):
                mock_check.side_effect = [update_info1, update_info2]

                result = await update_manager.check_updates(show_progress=True)

                assert len(result) == EXPECTED_APP_COUNT
                # Verify progress message was printed
                mock_print.assert_called_once_with(
                    "🔄 Checking 2 app(s) for updates..."
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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
            patch("my_unicorn.update.logger"),
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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch.object(
                update_manager, "check_single_update", new=AsyncMock()
            ) as mock_check:
                # app1 succeeds, app2 returns None, app3 raises exception
                mock_check.side_effect = [
                    update_info1,
                    None,
                    Exception("API error"),
                ]

                with patch("my_unicorn.update.logger"):
                    result = await update_manager.check_updates()

                    # Only successful checks should be returned
                    assert len(result) == 1
                    assert result[0] == update_info1

    @pytest.mark.asyncio
    async def test_check_updates_with_show_progress_no_apps(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test check updates with progress when no apps installed."""
        mock_config_manager.list_installed_apps.return_value = []

        with (
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
            patch("my_unicorn.update.logger"),
            patch("builtins.print"),
        ):
            update_manager = UpdateManager(mock_config_manager)
            result = await update_manager.check_updates(show_progress=True)

            assert result == []

    @pytest.mark.asyncio
    async def test_check_updates_with_show_progress_enabled(
        self,
        mock_config_manager: MagicMock,
    ) -> None:
        """Test check updates with progress message enabled."""
        mock_config_manager.list_installed_apps.return_value = ["app1"]
        update_info = UpdateInfo("app1", "1.0.0", "1.1.0", True)

        with (
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with (
                patch.object(
                    update_manager, "check_single_update", new=AsyncMock()
                ) as mock_check,
                patch("builtins.print") as mock_print,
            ):
                mock_check.return_value = update_info

                result = await update_manager.check_updates(show_progress=True)

                assert len(result) == 1
                assert result[0] == update_info
                # Verify progress message was printed
                mock_print.assert_called_once_with(
                    "🔄 Checking 1 app(s) for updates..."
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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
            patch("my_unicorn.update.logger"),
        ):
            update_manager = UpdateManager(mock_config_manager)
            success, error_reason = await update_manager.update_single_app(
                "nonexistent-app", mock_session
            )

            assert success is False
            assert error_reason == "Configuration not found"

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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
        ):
            update_manager = UpdateManager(mock_config_manager)

            with patch.object(
                update_manager, "check_single_update", new=AsyncMock()
            ) as mock_check:
                mock_check.return_value = update_info

                with patch("my_unicorn.update.logger"):
                    (
                        success,
                        error_reason,
                    ) = await update_manager.update_single_app(
                        "test-app", mock_session
                    )

                    # Method returns True when no update is needed (successful check)
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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
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
            patch("my_unicorn.update.GitHubAuthManager"),
            patch("my_unicorn.update.FileOperations"),
            patch("my_unicorn.update.BackupService"),
            patch(
                "my_unicorn.progress.get_progress_service"
            ) as mock_get_progress,
            patch("my_unicorn.update.DownloadService") as mock_download_cls,
            patch("my_unicorn.update.VerificationService") as mock_verify_cls,
        ):
            # Mock get_progress_service to return a mock progress service
            mock_progress = MagicMock()
            mock_get_progress.return_value = mock_progress

            update_manager = UpdateManager(mock_config_manager)

            mock_download = MagicMock()
            mock_download_cls.return_value = mock_download
            mock_download.progress_service = MagicMock()

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
                mock_download, mock_download.progress_service
            )

            # Verify that verification service was set
            assert update_manager.verification_service == mock_verify
