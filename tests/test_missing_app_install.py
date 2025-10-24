"""Tests for missing AppImage scenario in install command.

This test suite validates handling of releases where AppImages are not yet
available (still building). Based on real-world AppFlowy 0.10.2 scenario.
"""

from unittest.mock import MagicMock, patch

import pytest

from my_unicorn.install import InstallHandler


class TestMissingAppImageInstall:
    """Test install command with missing AppImage scenarios."""

    @pytest.fixture
    def mock_catalog_manager(self) -> MagicMock:
        """Create mock catalog manager."""
        mock_cm = MagicMock()
        mock_cm.get_app_config.return_value = {
            "name": "appflowy",
            "owner": "AppFlowy-IO",
            "repo": "AppFlowy",
            "appimage": {
                "rename": "appflowy",
                "characteristic_suffix": ["x86_64"],
            },
        }
        return mock_cm

    @pytest.fixture
    def install_handler(
        self, mock_catalog_manager: MagicMock
    ) -> InstallHandler:
        """Create install handler with mocked dependencies."""
        mock_download = MagicMock()
        mock_storage = MagicMock()
        mock_config = MagicMock()
        mock_github = MagicMock()

        return InstallHandler(
            download_service=mock_download,
            storage_service=mock_storage,
            config_manager=mock_config,
            github_client=mock_github,
            catalog_manager=mock_catalog_manager,
        )

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

    @pytest.fixture
    def mock_release_with_non_appimage_assets(self) -> dict:
        """Create mock release with assets but no AppImage files."""
        return {
            "tag_name": "0.10.2",
            "published_at": "2025-10-24T07:49:54Z",
            "assets": [
                {
                    "name": "checksums.txt",
                    "size": 1024,
                    "browser_download_url": "https://example.com/checksums.txt",
                    "content_type": "text/plain",
                },
                {
                    "name": "release-notes.md",
                    "size": 2048,
                    "browser_download_url": "https://example.com/notes.md",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_install_with_empty_assets_list(
        self,
        install_handler: InstallHandler,
        mock_release_without_appimage: dict,
    ) -> None:
        """Test install fails gracefully when release has no assets.

        This is the most common scenario - release is published but
        GitHub Actions is still building the AppImages.
        """
        with (
            patch.object(
                install_handler,
                "_fetch_release_for_catalog",
                return_value=mock_release_without_appimage,
            ),
        ):
            result = await install_handler.install_from_catalog(
                "appflowy",
                verify_downloads=False,
                show_progress=False,
            )

            # Should fail gracefully
            assert result["success"] is False
            assert result["name"] == "appflowy"
            assert result["source"] == "catalog"

            # Should have context-aware error message
            error_msg = result["error"]
            assert (
                "No assets found" in error_msg
                or "AppImage not found" in error_msg
            )
            assert "may still be building" in error_msg

    @pytest.mark.asyncio
    async def test_install_with_non_appimage_assets(
        self,
        install_handler: InstallHandler,
        mock_release_with_non_appimage_assets: dict,
    ) -> None:
        """Test install when release has assets but no AppImage files."""
        with (
            patch.object(
                install_handler,
                "_fetch_release_for_catalog",
                return_value=mock_release_with_non_appimage_assets,
            ),
        ):
            result = await install_handler.install_from_catalog(
                "appflowy",
                verify_downloads=False,
                show_progress=False,
            )

            # Should fail gracefully
            assert result["success"] is False
            assert result["name"] == "appflowy"

            # Should have helpful error message
            error_msg = result["error"]
            assert (
                "AppImage not found" in error_msg
                or "No assets found" in error_msg
            )
            assert "may still be building" in error_msg

    @pytest.mark.asyncio
    async def test_install_multiple_apps_some_missing(
        self, mock_catalog_manager: MagicMock
    ) -> None:
        """Test installing multiple apps where some have missing AppImages.

        Realistic scenario: installing multiple apps, some releases
        are complete, others are still building.
        """
        # Setup mocks
        mock_download = MagicMock()
        mock_storage = MagicMock()
        mock_config = MagicMock()
        mock_github = MagicMock()

        install_handler = InstallHandler(
            download_service=mock_download,
            storage_service=mock_storage,
            config_manager=mock_config,
            github_client=mock_github,
            catalog_manager=mock_catalog_manager,
        )

        # Mock catalog to return configs for multiple apps
        def get_app_config_side_effect(app_name: str) -> dict:
            configs = {
                "app1": {
                    "name": "app1",
                    "owner": "owner1",
                    "repo": "repo1",
                    "appimage": {"rename": "app1"},
                },
                "app2": {
                    "name": "app2",
                    "owner": "owner2",
                    "repo": "repo2",
                    "appimage": {"rename": "app2"},
                },
                "app3": {
                    "name": "app3",
                    "owner": "owner3",
                    "repo": "repo3",
                    "appimage": {"rename": "app3"},
                },
            }
            return configs.get(app_name)

        mock_catalog_manager.get_app_config.side_effect = (
            get_app_config_side_effect
        )

        # Mock fetch_release to return different scenarios
        async def fetch_release_side_effect(owner: str, repo: str) -> dict:
            if repo == "repo1":
                # Has AppImage
                return {
                    "tag_name": "v1.0.0",
                    "published_at": "2025-10-24T07:00:00Z",
                    "assets": [
                        {
                            "name": "app1-x86_64.AppImage",
                            "size": 100000000,
                            "browser_download_url": "https://example.com/app1.AppImage",
                        }
                    ],
                }
            elif repo == "repo2":
                # No assets yet - still building
                return {
                    "tag_name": "v2.0.0",
                    "published_at": "2025-10-24T07:49:54Z",
                    "assets": [],
                }
            else:  # repo3
                # Has non-AppImage assets only
                return {
                    "tag_name": "v3.0.0",
                    "published_at": "2025-10-24T07:45:00Z",
                    "assets": [
                        {
                            "name": "checksums.txt",
                            "size": 1024,
                            "browser_download_url": "https://example.com/checksums.txt",
                        }
                    ],
                }

        with (
            patch.object(
                install_handler,
                "_fetch_release_for_catalog",
                side_effect=fetch_release_side_effect,
            ),
            patch.object(
                install_handler,
                "_install_workflow",
                return_value={
                    "success": True,
                    "name": "app1",
                    "version": "v1.0.0",
                },
            ),
        ):
            results = await install_handler.install_multiple(
                catalog_apps=["app1", "app2", "app3"],
                url_apps=[],
                concurrent=3,
                verify_downloads=False,
                show_progress=False,
            )

            # Should have 3 results
            assert len(results) == 3

            # Find results by name
            results_by_name = {r["name"]: r for r in results}

            # app1 should succeed (has AppImage)
            assert results_by_name["app1"]["success"] is True

            # app2 should fail with helpful message (no assets)
            assert results_by_name["app2"]["success"] is False
            app2_error = results_by_name["app2"]["error"]
            assert (
                "AppImage not found" in app2_error
                or "No assets found" in app2_error
            )
            assert "may still be building" in app2_error

            # app3 should fail with helpful message (no AppImage assets)
            assert results_by_name["app3"]["success"] is False
            app3_error = results_by_name["app3"]["error"]
            assert (
                "AppImage not found" in app3_error
                or "No assets found" in app3_error
            )
            assert "may still be building" in app3_error

    @pytest.mark.asyncio
    async def test_install_result_structure(
        self, mock_catalog_manager: MagicMock
    ) -> None:
        """Test that install result has proper structure for error display.

        Validates that the result dict contains all fields needed for
        clean summary display.
        """
        mock_download = MagicMock()
        mock_storage = MagicMock()
        mock_config = MagicMock()
        mock_github = MagicMock()

        install_handler = InstallHandler(
            download_service=mock_download,
            storage_service=mock_storage,
            config_manager=mock_config,
            github_client=mock_github,
            catalog_manager=mock_catalog_manager,
        )

        with (
            patch.object(
                install_handler,
                "_fetch_release_for_catalog",
                return_value={
                    "tag_name": "0.10.2",
                    "published_at": "2025-10-24T07:49:54Z",
                    "assets": [],
                },
            ),
        ):
            result = await install_handler.install_from_catalog(
                "appflowy",
                verify_downloads=False,
                show_progress=False,
            )

            # Verify result structure matches display requirements
            assert "success" in result
            assert "name" in result
            assert "error" in result
            assert "source" in result

            # Verify values
            assert result["success"] is False
            assert result["name"] == "appflowy"
            assert result["source"] == "catalog"

            # Verify error message is helpful
            error_msg = result["error"]
            assert (
                "AppImage not found" in error_msg
                or "No assets found" in error_msg
            )
            assert "may still be building" in error_msg
