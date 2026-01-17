"""Tests for missing AppImage scenario in update command.

This test suite validates handling of releases where AppImages are not yet
available (still building). Based on real-world AppFlowy 0.10.2 scenario.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.workflows.update import UpdateInfo, UpdateManager


class TestMissingAppImageUpdate:
    """Test update command with missing AppImage scenarios."""

    @pytest.fixture
    def mock_config_manager(self) -> MagicMock:
        """Create mock configuration manager."""
        mock_cm = MagicMock()
        mock_cm.load_global_config.return_value = {
            "directory": {
                "storage": "/tmp/storage",
                "backup": "/tmp/backup",
                "icon": "/tmp/icon",
                "download": "/tmp/download",
            },
            "max_concurrent_downloads": 3,
        }
        return mock_cm

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock aiohttp session."""
        return AsyncMock()

    @pytest.fixture
    def mock_release_without_appimage(self) -> dict:
        """Create mock release data without AppImage assets.

        Based on AppFlowy 0.10.2 release that was published but
        AppImages were still building.
        """
        return {
            "url": "https://api.github.com/repos/AppFlowy-IO/AppFlowy/releases/256916097",
            "id": 256916097,
            "tag_name": "0.10.2",
            "name": "v0.10.2",
            "draft": False,
            "prerelease": False,
            "created_at": "2025-09-12T08:21:32Z",
            "updated_at": "2025-10-24T07:49:54Z",
            "published_at": "2025-10-24T07:49:54Z",
            "assets": [],  # No assets yet - builds still in progress!
            "tarball_url": "https://api.github.com/repos/AppFlowy-IO/AppFlowy/tarball/0.10.2",
            "zipball_url": "https://api.github.com/repos/AppFlowy-IO/AppFlowy/zipball/0.10.2",
            "body": "Release notes",
        }

    @pytest.mark.asyncio
    async def test_update_with_empty_assets_list(
        self,
        mock_config_manager: MagicMock,
        mock_session: AsyncMock,
        mock_release_without_appimage: dict,
    ) -> None:
        """Test update fails gracefully when release has no assets.

        This is the most common scenario - release is published but
        GitHub Actions is still building the AppImages.
        """
        mock_app_config = {
            "owner": "AppFlowy-IO",
            "repo": "AppFlowy",
            "appimage": {"name": "appflowy.AppImage"},
        }
        mock_config_manager.load_app_config.return_value = mock_app_config

        # Create mock Release object with no assets
        from my_unicorn.core.github import Release

        mock_release = Release(
            owner="AppFlowy-IO",
            repo="AppFlowy",
            version="0.10.2",
            prerelease=False,
            assets=[],  # No assets
            original_tag_name="0.10.2",
        )

        update_info = UpdateInfo(
            app_name="appflowy",
            current_version="0.10.1",
            latest_version="0.10.2",
            has_update=True,
            release_data=mock_release,
        )

        with (
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch("my_unicorn.core.workflows.update.logger"),
            patch.object(
                UpdateManager,
                "check_single_update",
                return_value=update_info,
            ),
            patch(
                "my_unicorn.core.workflows.update.select_best_appimage_asset",
                return_value=None,
            ),
        ):
            update_manager = UpdateManager(mock_config_manager)
            success, error_reason = await update_manager.update_single_app(
                "appflowy", mock_session, update_info=update_info
            )

            # Should fail gracefully
            assert success is False
            assert error_reason is not None

            # Should have context-aware error message
            assert "AppImage not found" in error_reason
            assert "may still be building" in error_reason

    @pytest.mark.asyncio
    async def test_update_multiple_apps_some_missing(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test updating multiple apps where some have missing AppImages.

        Realistic scenario: updating multiple apps, some releases
        are complete, others are still building.
        """
        with (
            patch("my_unicorn.core.workflows.update.GitHubAuthManager"),
            patch("my_unicorn.core.workflows.update.FileOperations"),
            patch("my_unicorn.core.workflows.update.BackupService"),
            patch.object(
                UpdateManager, "update_single_app", new=AsyncMock()
            ) as mock_update_single,
        ):
            update_manager = UpdateManager(mock_config_manager)

            # app1 succeeds, app2 missing AppImage, app3 succeeds
            mock_update_single.side_effect = [
                (True, None),
                (
                    False,
                    "AppImage not found in release - may still be building",
                ),
                (True, None),
            ]

            results, error_reasons = await update_manager.update_multiple_apps(
                ["app1", "app2", "app3"]
            )

            # Should have 3 results
            assert len(results) == 3

            # app1 should succeed
            assert results["app1"] is True

            # app2 should fail with helpful message
            assert results["app2"] is False
            assert "app2" in error_reasons
            assert "AppImage not found" in error_reasons["app2"]
            assert "may still be building" in error_reasons["app2"]

            # app3 should succeed
            assert results["app3"] is True
            assert "app3" not in error_reasons

    @pytest.mark.asyncio
    async def test_error_reason_stored_in_update_info(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test that error reasons are properly stored in UpdateInfo."""
        # Create UpdateInfo with error
        info = UpdateInfo(
            app_name="appflowy",
            current_version="0.10.1",
            latest_version="0.10.2",
            has_update=True,
            error_reason="AppImage not found in release - may still be building",
        )

        # Verify error reason is stored
        assert info.error_reason is not None
        assert "AppImage not found" in info.error_reason
        assert "may still be building" in info.error_reason

        # Verify it doesn't break repr
        repr_str = repr(info)
        assert "appflowy" in repr_str
