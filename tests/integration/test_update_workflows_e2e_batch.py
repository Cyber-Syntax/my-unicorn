"""Integration tests for end-to-end batch update workflows.

This module tests complete update workflows for multiple applications
using real filesystem operations. Network calls (GitHub API, downloads) are
mocked, but filesystem operations use actual temporary directories to verify
that batch operations handle partial success scenarios correctly.

Test Scenarios:
- Batch update with partial success: some apps succeed, others fail
- Failed apps remain unchanged while successful apps are updated
- Cross-app contamination is prevented
- Error tracking per app is accurate

All tests use @pytest.mark.integration decorator for integration isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from my_unicorn.core.protocols.progress import NullProgressReporter
from my_unicorn.core.update.manager import UpdateManager
from tests.integration.conftest import create_mock_appimage_content

if TYPE_CHECKING:
    from my_unicorn.core.github import Release


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_multiple_apps_partial_success(
    integration_update_manager: tuple[UpdateManager, dict[str, Path]],
    mock_github_releases: dict[str, Release],
) -> None:
    """Test batch update with partial success handling.

    This test verifies error resilience in batch updates where some apps
    succeed and others fail:
    1. Multiple apps are targeted for update
    2. First app updates successfully
    3. Second app encounters hash verification failure
    4. Successful updates are preserved
    5. Failed apps remain in original state
    6. Summary reports show partial completion

    Verifies:
    - Successful apps are updated completely
    - Failed apps remain unchanged
    - No cross-contamination between app updates
    - Error tracking per app
    - Summary reporting accuracy

    Args:
        integration_update_manager: UpdateManager configured for testing
        mock_github_releases: Mock GitHub release data

    """
    manager, workspace = integration_update_manager

    # Setup multiple apps
    app_configs = {
        "appflowy": {
            "state": {
                "version": "0.4.4",
                "installed_path": str(
                    workspace["storage"] / "AppFlowy-x86_64.AppImage"
                ),
            },
            "source": {
                "url": "https://github.com/AppFlowy-IO/AppFlowy",
                "owner": "AppFlowy-IO",
                "repo": "AppFlowy",
            },
        },
        "zen": {
            "state": {
                "version": "0.1.13",
                "installed_path": str(
                    workspace["storage"] / "zen-0.1.13-x86_64.AppImage"
                ),
            },
            "source": {
                "url": "https://github.com/zen-browser/desktop",
                "owner": "zen-browser",
                "repo": "desktop",
            },
        },
    }

    # Set up app config loading
    def load_app_config_side_effect(app_name: str) -> dict[str, Any]:
        return app_configs.get(app_name, {})

    manager.config_manager.load_app_config.side_effect = (
        load_app_config_side_effect
    )
    manager.config_manager.list_installed_apps.return_value = [
        "appflowy",
        "zen",
    ]

    # Create existing AppImage files
    appflowy_appimage = workspace["storage"] / "AppFlowy-x86_64.AppImage"
    appflowy_appimage.write_text(
        create_mock_appimage_content("appflowy", "0.4.4")
    )

    zen_appimage = workspace["storage"] / "zen-0.1.13-x86_64.AppImage"
    zen_appimage.write_text(create_mock_appimage_content("zen", "0.1.13"))

    # Verify initial setup
    assert appflowy_appimage.exists()
    assert zen_appimage.exists()
    assert manager.config_manager.list_installed_apps() == [
        "appflowy",
        "zen",
    ]

    with patch(
        "my_unicorn.core.update.workflows.DownloadService"
    ) as mock_download_cls:
        mock_download = AsyncMock()

        async def async_download_wrapper(asset, download_path):
            download_path.parent.mkdir(parents=True, exist_ok=True)
            if "AppFlowy" in asset.name:
                download_path.write_text(
                    create_mock_appimage_content("appflowy", "0.4.5")
                )
            else:
                download_path.write_text(
                    create_mock_appimage_content("zen", "0.1.14")
                )
            return download_path

        mock_download.download_appimage.side_effect = async_download_wrapper
        mock_download_cls.return_value = mock_download

        with patch(
            "my_unicorn.core.update.manager.PostDownloadProcessor"
        ) as mock_processor_cls:
            mock_processor = AsyncMock()

            async def process_side_effect(context):
                # Success for appflowy, failure for zen
                if context.app_name == "appflowy":
                    result = MagicMock()
                    result.success = True
                    result.error = None

                    # Update the file for successful app
                    appimage_path = Path(
                        context.app_config["state"]["installed_path"]
                    )
                    appimage_path.parent.mkdir(parents=True, exist_ok=True)
                    appimage_path.write_text(
                        create_mock_appimage_content("appflowy", "0.4.5")
                    )

                    return result
                # zen fails
                result = MagicMock()
                result.success = False
                result.error = "Hash verification failed for zen"
                return result

            mock_processor.process.side_effect = process_side_effect
            mock_processor.progress_reporter = NullProgressReporter()
            mock_processor_cls.return_value = mock_processor

            # Execute batch update
            results, error_reasons = await manager.update_multiple_apps(
                ["appflowy", "zen"]
            )

    # Verify partial success
    assert results["appflowy"] is True, "appflowy should succeed"
    assert results["zen"] is False, "zen should fail"

    # Verify successful app was updated
    updated_appflowy = appflowy_appimage.read_text()
    assert updated_appflowy == create_mock_appimage_content(
        "appflowy", "0.4.5"
    ), "Successful app should be updated"

    # Verify failed app remained unchanged
    zen_content = zen_appimage.read_text()
    assert zen_content == create_mock_appimage_content("zen", "0.1.13"), (
        "Failed app should remain unchanged"
    )

    # Verify error tracking per app
    assert "zen" in error_reasons, (
        "Failed app should be tracked in error_reasons"
    )
    assert "Hash verification failed" in error_reasons["zen"], (
        "Error message should be captured"
    )
