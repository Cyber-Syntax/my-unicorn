"""Tests for update workflow utilities."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.utils.update_utils import process_post_download


class TestProcessPostDownload:
    """Tests for process_post_download function."""

    @pytest.fixture
    def mock_asset(self) -> Asset:
        """Create a mock Asset object."""
        return Asset(
            name="test-app.AppImage",
            browser_download_url="https://example.com/test.AppImage",
            size=1024,
            digest="",
        )

    @pytest.fixture
    def mock_release(self) -> Release:
        """Create a mock Release object."""
        return Release(
            owner="test",
            repo="test-repo",
            version="1.0.0",
            prerelease=False,
            assets=[],
            original_tag_name="v1.0.0",
        )

    @pytest.fixture
    def app_config(self) -> dict:
        """Create a sample app config."""
        return {
            "version": "2.0.0",
            "state": {"installed_path": "/opt/test-app.AppImage"},
            "verification": {},
        }

    @pytest.fixture
    def mock_services(self) -> dict:
        """Create mock services for testing."""
        verification_service = Mock()
        storage_service = Mock()
        config_manager = Mock()
        backup_service = Mock()
        progress_service = Mock()

        # Setup mock returns
        storage_service.move_to_install_dir.return_value = Path(
            "/opt/test-app.AppImage"
        )
        progress_service.is_active.return_value = False

        # Mock config_manager to return proper dict
        config_manager.load_raw_app_config.return_value = {
            "version": "2.0.0",
            "state": {"installed_path": "/opt/test-app.AppImage"},
        }

        return {
            "verification_service": verification_service,
            "storage_service": storage_service,
            "config_manager": config_manager,
            "backup_service": backup_service,
            "progress_service": progress_service,
        }

    @pytest.mark.asyncio
    async def test_process_post_download_success(
        self, mock_asset, mock_release, app_config, mock_services, tmp_path
    ) -> None:
        """Test successful post-download processing."""
        downloaded_path = tmp_path / "test.AppImage"
        downloaded_path.touch()

        # Mock async functions
        mock_verify = AsyncMock(
            return_value={"methods": {}, "updated_config": {}}
        )
        mock_setup_icon = AsyncMock(
            return_value={
                "source": "extracted",
                "installed": True,
                "path": str(tmp_path / "icon.png"),
                "extraction": True,
                "name": "test-app",
            }
        )
        mock_rename = Mock(return_value=tmp_path / "test-app.AppImage")

        # Patch the imported functions
        import my_unicorn.utils.update_utils

        original_verify = (
            my_unicorn.utils.update_utils.verify_appimage_download
        )
        original_setup = my_unicorn.utils.update_utils.setup_appimage_icon
        original_rename = my_unicorn.utils.update_utils.rename_appimage

        my_unicorn.utils.update_utils.verify_appimage_download = mock_verify
        my_unicorn.utils.update_utils.setup_appimage_icon = mock_setup_icon
        my_unicorn.utils.update_utils.rename_appimage = mock_rename

        try:
            result = await process_post_download(
                app_name="test-app",
                app_config=app_config,
                latest_version="1.0.0",
                owner="test",
                repo="test-repo",
                catalog_entry=None,
                appimage_asset=mock_asset,
                release_data=mock_release,
                icon_dir=tmp_path / "icons",
                storage_dir=tmp_path / "apps",
                downloaded_path=downloaded_path,
                verification_service=mock_services["verification_service"],
                storage_service=mock_services["storage_service"],
                config_manager=mock_services["config_manager"],
                backup_service=mock_services["backup_service"],
                progress_service=None,
            )

            assert result is True
            mock_services[
                "storage_service"
            ].make_executable.assert_called_once()
            mock_services[
                "storage_service"
            ].move_to_install_dir.assert_called_once()
            mock_services[
                "backup_service"
            ].cleanup_old_backups.assert_called_once_with("test-app")

        finally:
            # Restore original functions
            my_unicorn.utils.update_utils.verify_appimage_download = (
                original_verify
            )
            my_unicorn.utils.update_utils.setup_appimage_icon = original_setup
            my_unicorn.utils.update_utils.rename_appimage = original_rename

    @pytest.mark.asyncio
    async def test_process_post_download_with_progress(
        self, mock_asset, mock_release, app_config, mock_services, tmp_path
    ) -> None:
        """Test post-download processing with progress service."""
        downloaded_path = tmp_path / "test.AppImage"
        downloaded_path.touch()

        # Enable progress service
        mock_services["progress_service"].is_active.return_value = True
        mock_services[
            "progress_service"
        ].create_installation_workflow = AsyncMock(
            return_value=("verify_task", "install_task")
        )
        mock_services["progress_service"].finish_task = AsyncMock()

        # Mock async functions
        mock_verify = AsyncMock(
            return_value={"methods": {}, "updated_config": {}}
        )
        mock_setup_icon = AsyncMock(
            return_value={
                "source": "none",
                "installed": False,
                "path": None,
                "extraction": False,
                "name": "",
            }
        )
        mock_rename = Mock(return_value=tmp_path / "test-app.AppImage")

        import my_unicorn.utils.update_utils

        original_verify = (
            my_unicorn.utils.update_utils.verify_appimage_download
        )
        original_setup = my_unicorn.utils.update_utils.setup_appimage_icon
        original_rename = my_unicorn.utils.update_utils.rename_appimage

        my_unicorn.utils.update_utils.verify_appimage_download = mock_verify
        my_unicorn.utils.update_utils.setup_appimage_icon = mock_setup_icon
        my_unicorn.utils.update_utils.rename_appimage = mock_rename

        try:
            result = await process_post_download(
                app_name="test-app",
                app_config=app_config,
                latest_version="1.0.0",
                owner="test",
                repo="test-repo",
                catalog_entry=None,
                appimage_asset=mock_asset,
                release_data=mock_release,
                icon_dir=tmp_path / "icons",
                storage_dir=tmp_path / "apps",
                downloaded_path=downloaded_path,
                verification_service=mock_services["verification_service"],
                storage_service=mock_services["storage_service"],
                config_manager=mock_services["config_manager"],
                backup_service=mock_services["backup_service"],
                progress_service=mock_services["progress_service"],
            )

            assert result is True
            mock_services[
                "progress_service"
            ].create_installation_workflow.assert_called_once_with(
                "test-app", with_verification=True
            )
            mock_services["progress_service"].finish_task.assert_called_once()

        finally:
            my_unicorn.utils.update_utils.verify_appimage_download = (
                original_verify
            )
            my_unicorn.utils.update_utils.setup_appimage_icon = original_setup
            my_unicorn.utils.update_utils.rename_appimage = original_rename
