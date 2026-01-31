"""Tests for installation verification failure handling.

This test suite ensures that verification failures are properly handled
and prevent installation of corrupted or tampered AppImages.

These tests verify TASK-001 from Phase 1: Fix missing raise statement after
verification failure to prevent corrupted AppImages from being installed.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from my_unicorn.core.workflows.install import InstallHandler
from my_unicorn.exceptions import InstallationError


class TestVerificationFailure:
    """Test cases for verification failure handling."""

    @pytest.mark.asyncio
    async def test_verify_appimage_download_failure_raises_exception(
        self,
    ) -> None:
        """Test that verification failure raises InstallationError.

        This is a critical security test ensuring that the raise statement
        added in Phase 1 (TASK-001) properly prevents corrupted or tampered
        AppImages from being installed.
        """
        download_service = Mock()
        storage_service = Mock()
        config_manager = Mock()
        github_client = Mock()

        handler = InstallHandler(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            github_client=github_client,
        )

        # Mock download to return a path
        download_service.download_appimage = AsyncMock(
            return_value=Path("/tmp/test.appimage")
        )
        # Mock progress service methods
        download_service.progress_service = Mock()
        download_service.progress_service.create_installation_workflow = (
            AsyncMock(return_value=("verify_id", "install_id"))
        )
        download_service.progress_service.finish_task = AsyncMock()

        # Mock verify_appimage_download to fail
        with patch(
            "my_unicorn.utils.appimage_utils.verify_appimage_download"
        ) as mock_verify:
            mock_verify.return_value = {
                "passed": False,
                "error": "SHA256 checksum mismatch",
            }

            # Mock release and asset
            from my_unicorn.core.github import Asset, Release

            asset = Asset(
                name="test.appimage",
                size=1024,
                digest="sha256:abc123",
                browser_download_url="https://example.com/test.appimage",
            )
            release = Release(
                owner="test-owner",
                repo="test-repo",
                version="1.0.0",
                prerelease=False,
                assets=[asset],
                original_tag_name="v1.0.0",
            )

            app_config = {
                "name": "test-app",
                "owner": "test-owner",
                "repo": "test-repo",
            }

            # This should raise InstallationError due to verification failure
            with pytest.raises(InstallationError, match="Verification failed"):
                await handler._install_workflow(
                    app_name="test-app",
                    asset=asset,
                    release=release,
                    app_config=app_config,
                    source="catalog",
                )

    @pytest.mark.asyncio
    async def test_verification_success_allows_installation(self) -> None:
        """Test that successful verification allows installation to continue.

        Ensures the happy path still works after the verification failure fix.
        """
        download_service = Mock()
        download_service.download_appimage = AsyncMock(
            return_value=Path("/tmp/test.appimage")
        )
        # Mock progress service methods
        download_service.progress_service = Mock()
        download_service.progress_service.create_installation_workflow = (
            AsyncMock(return_value=("verify_id", "install_id"))
        )
        download_service.progress_service.finish_task = AsyncMock()

        storage_service = Mock()
        storage_service.move_to_install_dir = Mock(
            return_value=Path("/install/test.appimage")
        )

        config_manager = Mock()
        config_manager.load_global_config = Mock(
            return_value={
                "directory": {
                    "icon": "/tmp/icons",
                    "install": "/tmp/install",
                    "desktop": "/tmp/desktop",
                },
            }
        )

        github_client = Mock()

        handler = InstallHandler(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            github_client=github_client,
        )

        # Mock successful verification - patch where it's imported
        with (
            patch(
                "my_unicorn.core.workflows.install.verify_appimage_download",
                new_callable=AsyncMock,
            ) as mock_verify,
            patch(
                "my_unicorn.core.workflows.install.rename_appimage"
            ) as mock_rename,
            patch(
                "my_unicorn.core.workflows.install.setup_appimage_icon",
                new_callable=AsyncMock,
            ) as mock_icon,
            patch(
                "my_unicorn.core.workflows.install.create_app_config_v2"
            ) as mock_config,
            patch(
                "my_unicorn.core.workflows.install.create_desktop_entry"
            ) as mock_desktop,
        ):
            mock_verify.return_value = {"passed": True, "method": "digest"}
            mock_rename.return_value = Path("/install/test.appimage")
            mock_icon.return_value = {"icon_path": "/tmp/icons/test.png"}
            mock_config.return_value = Path("/config/test.json")
            mock_desktop.return_value = {
                "desktop_path": "/tmp/desktop/test.desktop"
            }

            from my_unicorn.core.github import Asset, Release

            asset = Asset(
                name="test.appimage",
                size=1024,
                digest="sha256:abc123",
                browser_download_url="https://example.com/test.appimage",
            )
            release = Release(
                owner="test-owner",
                repo="test-repo",
                version="1.0.0",
                prerelease=False,
                assets=[asset],
                original_tag_name="v1.0.0",
            )

            app_config = {
                "name": "test-app",
                "owner": "test-owner",
                "repo": "test-repo",
            }

            # Should complete successfully
            result = await handler._install_workflow(
                app_name="test-app",
                asset=asset,
                release=release,
                app_config=app_config,
                source="catalog",
            )

            # Verify successful result
            assert result["success"] is True
            assert result["name"] == "test-app"

            # Verify verification was called
            mock_verify.assert_called_once()
