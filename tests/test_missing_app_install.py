"""Tests for missing AppImage scenario in install command.

This test suite validates handling of releases where AppImages are not yet
available (still building). Based on real-world AppFlowy 0.10.2 scenario.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.install.install import InstallHandler


class TestMissingAppImageInstall:
    """Test install command with missing AppImage scenarios."""

    @pytest.fixture
    def mock_config_manager(self) -> MagicMock:
        """Create mock config manager."""
        mock_cm = MagicMock()
        mock_cm.load_catalog.return_value = {
            "metadata": {
                "name": "appflowy",
            },
            "source": {
                "owner": "AppFlowy-IO",
                "repo": "AppFlowy",
            },
            "appimage": {
                "naming": {
                    "target_name": "appflowy",
                    "architectures": ["x86_64"],
                },
            },
        }
        return mock_cm

    @pytest.fixture
    def install_handler(
        self, mock_config_manager: MagicMock
    ) -> InstallHandler:
        """Create install handler with mocked dependencies."""
        mock_download = MagicMock()
        mock_storage = MagicMock()
        mock_github = MagicMock()
        mock_processor = MagicMock()

        return InstallHandler(
            download_service=mock_download,
            storage_service=mock_storage,
            config_manager=mock_config_manager,
            github_client=mock_github,
            post_download_processor=mock_processor,
        )

    @pytest.fixture
    def mock_release_without_appimage(self) -> Release:
        """Create mock release data without AppImage assets.

        Based on AppFlowy 0.10.2 release that was published but
        AppImages were still building.
        """
        return Release(
            owner="AppFlowy-IO",
            repo="AppFlowy",
            version="0.10.2",
            prerelease=False,
            assets=[],  # No assets yet - builds still in progress!
            original_tag_name="0.10.2",
        )

    @pytest.fixture
    def mock_release_with_non_appimage_assets(self) -> Release:
        """Create mock release with assets but no AppImage files."""
        return Release(
            owner="test",
            repo="test",
            version="0.10.2",
            prerelease=False,
            assets=[
                Asset(
                    name="checksums.txt",
                    size=1024,
                    browser_download_url="https://example.com/checksums.txt",
                    digest=None,
                ),
                Asset(
                    name="release-notes.md",
                    size=2048,
                    browser_download_url="https://example.com/notes.md",
                    digest=None,
                ),
            ],
            original_tag_name="0.10.2",
        )

    @pytest.mark.asyncio
    async def test_install_with_empty_assets_list(
        self,
        install_handler: InstallHandler,
        mock_release_without_appimage: Release,
    ) -> None:
        """Test install fails gracefully when release has no assets.

        This is the most common scenario - release is published but
        GitHub Actions is still building the AppImages.
        """
        mock_fetch = AsyncMock(return_value=mock_release_without_appimage)
        with patch.object(install_handler, "_fetch_release", mock_fetch):
            result = await install_handler.install_from_catalog(
                "appflowy",
                verify_downloads=False,
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
        mock_fetch = AsyncMock(
            return_value=mock_release_with_non_appimage_assets
        )
        with patch.object(install_handler, "_fetch_release", mock_fetch):
            result = await install_handler.install_from_catalog(
                "appflowy",
                verify_downloads=False,
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
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test installing multiple apps where some have missing AppImages.

        Realistic scenario: installing multiple apps, some releases
        are complete, others are still building.
        """
        # Setup mocks
        mock_download = MagicMock()
        mock_storage = MagicMock()
        mock_github = MagicMock()

        install_handler = InstallHandler(
            post_download_processor=Mock(),
            download_service=mock_download,
            storage_service=mock_storage,
            config_manager=mock_config_manager,
            github_client=mock_github,
        )

        # Mock catalog to return configs for multiple apps
        def get_app_config_side_effect(app_name: str) -> dict:
            configs = {
                "app1": {
                    "config_version": "2.0.0",
                    "metadata": {
                        "name": "app1",
                        "display_name": "App1",
                        "description": "",
                    },
                    "source": {
                        "type": "github",
                        "owner": "owner1",
                        "repo": "repo1",
                        "prerelease": False,
                    },
                    "appimage": {
                        "naming": {
                            "template": "",
                            "target_name": "",
                            "architectures": [],
                        }
                    },
                    "verification": {"method": "skip"},
                    "icon": {"method": "extraction", "filename": ""},
                },
                "app2": {
                    "config_version": "2.0.0",
                    "metadata": {
                        "name": "app2",
                        "display_name": "App2",
                        "description": "",
                    },
                    "source": {
                        "type": "github",
                        "owner": "owner2",
                        "repo": "repo2",
                        "prerelease": False,
                    },
                    "appimage": {
                        "naming": {
                            "template": "",
                            "target_name": "",
                            "architectures": [],
                        }
                    },
                    "verification": {"method": "skip"},
                    "icon": {"method": "extraction", "filename": ""},
                },
                "app3": {
                    "config_version": "2.0.0",
                    "metadata": {
                        "name": "app3",
                        "display_name": "App3",
                        "description": "",
                    },
                    "source": {
                        "type": "github",
                        "owner": "owner3",
                        "repo": "repo3",
                        "prerelease": False,
                    },
                    "appimage": {
                        "naming": {
                            "template": "",
                            "target_name": "",
                            "architectures": [],
                        }
                    },
                    "verification": {"method": "skip"},
                    "icon": {"method": "extraction", "filename": ""},
                },
            }
            return configs.get(app_name)

        mock_config_manager.load_catalog.side_effect = (
            get_app_config_side_effect
        )

        # Mock fetch_release to return different scenarios
        async def fetch_release_side_effect(owner: str, repo: str) -> Release:
            if repo == "repo1":
                # Has AppImage
                return Release(
                    owner=owner,
                    repo=repo,
                    version="v1.0.0",
                    prerelease=False,
                    assets=[
                        Asset(
                            name="app1-x86_64.AppImage",
                            size=100000000,
                            browser_download_url="https://example.com/app1.AppImage",
                            digest=None,
                        )
                    ],
                    original_tag_name="v1.0.0",
                )
            if repo == "repo2":
                # No assets yet - still building
                return Release(
                    owner=owner,
                    repo=repo,
                    version="v2.0.0",
                    prerelease=False,
                    assets=[],
                    original_tag_name="v2.0.0",
                )
            # repo3
            # Has non-AppImage assets only
            return Release(
                owner=owner,
                repo=repo,
                version="v3.0.0",
                prerelease=False,
                assets=[
                    Asset(
                        name="checksums.txt",
                        size=1024,
                        browser_download_url="https://example.com/checksums.txt",
                        digest=None,
                    )
                ],
                original_tag_name="v3.0.0",
            )

        mock_fetch = AsyncMock(side_effect=fetch_release_side_effect)
        mock_workflow = AsyncMock(
            return_value={
                "success": True,
                "name": "app1",
                "version": "v1.0.0",
            }
        )
        with (
            patch.object(install_handler, "_fetch_release", mock_fetch),
            patch.object(install_handler, "_install_workflow", mock_workflow),
        ):
            results = await install_handler.install_multiple(
                catalog_apps=["app1", "app2", "app3"],
                url_apps=[],
                concurrent=3,
                verify_downloads=False,
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
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test that install result has proper structure for error display.

        Validates that the result dict contains all fields needed for
        clean summary display.
        """
        mock_download = MagicMock()
        mock_storage = MagicMock()
        mock_github = MagicMock()

        install_handler = InstallHandler(
            post_download_processor=Mock(),
            download_service=mock_download,
            storage_service=mock_storage,
            config_manager=mock_config_manager,
            github_client=mock_github,
        )

        mock_fetch = AsyncMock(
            return_value=Release(
                owner="AppFlowy-IO",
                repo="AppFlowy",
                version="0.10.2",
                prerelease=False,
                assets=[],
                original_tag_name="0.10.2",
            )
        )
        with patch.object(install_handler, "_fetch_release", mock_fetch):
            result = await install_handler.install_from_catalog(
                "appflowy",
                verify_downloads=False,
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
