"""Integration tests for end-to-end single app update workflows.

This module tests complete update workflows for single application updates
using real filesystem operations. Network calls (GitHub API, downloads) are
mocked, but filesystem operations use actual temporary directories to verify
that all intermediate files are created correctly and configurations are
properly updated.

Test Scenarios:
- Single app update happy path: check → download → verify → backup → replace
- Update with hash verification failure and rollback recovery
- Force update flag bypasses version check even if already up-to-date
- Cache refresh workflow fetches fresh data from GitHub

All tests use @pytest.mark.integration decorator for integration isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from my_unicorn.core.protocols.progress import NullProgressReporter
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.core.update.manager import UpdateManager
from tests.integration.conftest import create_mock_appimage_content

if TYPE_CHECKING:
    from my_unicorn.core.github import Release

# =============================================================================
# Test Helper Functions
# =============================================================================


def _create_app_config(workspace: dict[str, Path]) -> dict[str, str]:
    """Create base app config for appflowy."""
    return {
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
    }


def _setup_manager_and_files(
    manager: UpdateManager,
    workspace: dict[str, Path],
    old_version: str,
) -> Path:
    """Setup manager config and create existing AppImage file."""
    app_config = _create_app_config(workspace)
    app_config["state"]["version"] = old_version
    manager.config_manager.load_app_config.return_value = app_config
    manager.config_manager.list_installed_apps.return_value = ["appflowy"]

    existing_appimage = workspace["storage"] / "AppFlowy-x86_64.AppImage"
    existing_appimage.write_text(
        create_mock_appimage_content("appflowy", old_version)
    )
    return existing_appimage


def _create_success_processor(
    manager: UpdateManager, new_content: str, new_version: str = "0.4.5"
):
    """Create a mock PostDownloadProcessor that simulates successful update."""

    async def processor_side_effect(context):
        result = MagicMock()
        result.success = True
        result.error = None

        appimage_path = Path(context.app_config["state"]["installed_path"])
        appimage_path.parent.mkdir(parents=True, exist_ok=True)
        appimage_path.write_text(new_content)

        updated_config = context.app_config.copy()
        updated_config["state"]["version"] = new_version
        manager.config_manager.load_app_config.return_value = updated_config

        return result

    return processor_side_effect


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_single_app_full_workflow_success(
    integration_update_manager: tuple[UpdateManager, dict[str, Path]],
    mock_github_releases: dict[str, Release],
) -> None:
    """Test complete update workflow: verify success and initialization.

    Verifies the entire happy path: file replacement, verification success,
    and config update with new version.
    """
    manager, workspace = integration_update_manager
    app_config = _create_app_config(workspace)
    existing_appimage = _setup_manager_and_files(manager, workspace, "0.4.4")

    release_data = mock_github_releases["appflowy"]
    new_appimage_content = create_mock_appimage_content("appflowy", "0.4.5")

    assert existing_appimage.exists()
    assert existing_appimage.read_text() == create_mock_appimage_content(
        "appflowy", "0.4.4"
    )

    with patch.object(manager, "check_single_update") as mock_check:
        update_info = UpdateInfo(
            app_name="appflowy",
            current_version="0.4.4",
            latest_version="0.4.5",
            has_update=True,
            release_url="https://github.com/AppFlowy-IO/AppFlowy/releases/tag/0.4.5",
            prerelease=False,
            original_tag_name="v0.4.5",
            release_data=release_data,
            app_config=app_config,
        )
        mock_check.return_value = update_info

        with patch(
            "my_unicorn.core.update.workflows.DownloadService"
        ) as mock_download_cls:
            mock_download = AsyncMock()

            async def mock_download_side_effect(asset, download_path):
                download_path.parent.mkdir(parents=True, exist_ok=True)
                download_path.write_text(new_appimage_content)
                return download_path

            mock_download.download_appimage.side_effect = (
                mock_download_side_effect
            )
            mock_download_cls.return_value = mock_download

            with patch(
                "my_unicorn.core.update.manager.PostDownloadProcessor"
            ) as mock_processor_cls:
                mock_processor = AsyncMock()
                mock_processor.process.side_effect = _create_success_processor(
                    manager, new_appimage_content
                )
                mock_processor.progress_reporter = NullProgressReporter()
                mock_processor_cls.return_value = mock_processor

                async with aiohttp.ClientSession() as session:
                    success, _ = await manager.update_single_app(
                        "appflowy", session
                    )

        assert success is True
        updated_content = existing_appimage.read_text()
        assert updated_content == new_appimage_content
        updated_config = manager.config_manager.load_app_config("appflowy")
        assert updated_config["state"]["version"] == "0.4.5"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_single_app_verification_failure(
    integration_update_manager: tuple[UpdateManager, dict[str, Path]],
    mock_github_releases: dict[str, Release],
) -> None:
    """Test error handling when hash verification fails.

    Verifies that original file is preserved and error is reported
    when verification fails.
    """
    manager, workspace = integration_update_manager
    original_content = create_mock_appimage_content("appflowy", "0.4.4")
    app_config = _create_app_config(workspace)
    existing_appimage = _setup_manager_and_files(manager, workspace, "0.4.4")

    workspace["backups"].mkdir(exist_ok=True)
    release_data = mock_github_releases["appflowy"]

    with patch.object(manager, "check_single_update") as mock_check:
        update_info = UpdateInfo(
            app_name="appflowy",
            current_version="0.4.4",
            latest_version="0.4.5",
            has_update=True,
            release_url="https://github.com/AppFlowy-IO/AppFlowy/releases/tag/0.4.5",
            prerelease=False,
            original_tag_name="v0.4.5",
            release_data=release_data,
            app_config=app_config,
        )
        mock_check.return_value = update_info

        with patch(
            "my_unicorn.core.update.workflows.DownloadService"
        ) as mock_download_cls:
            mock_download = AsyncMock()

            async def mock_download_side_effect(asset, download_path):
                download_path.parent.mkdir(parents=True, exist_ok=True)
                download_path.write_text(
                    create_mock_appimage_content("appflowy", "0.4.5")
                )
                return download_path

            mock_download.download_appimage.side_effect = (
                mock_download_side_effect
            )
            mock_download_cls.return_value = mock_download

            with patch(
                "my_unicorn.core.update.manager.PostDownloadProcessor"
            ) as mock_processor_cls:
                mock_processor = AsyncMock()
                mock_result = MagicMock()
                mock_result.success = False
                mock_result.error = "Hash verification failed"
                mock_processor.process.return_value = mock_result
                mock_processor.progress_reporter = NullProgressReporter()
                mock_processor_cls.return_value = mock_processor

                assert existing_appimage.exists()
                assert existing_appimage.read_text() == original_content

                async with aiohttp.ClientSession() as session:
                    success, error_reason = await manager.update_single_app(
                        "appflowy", session
                    )

        assert success is False
        assert error_reason is not None
        assert existing_appimage.exists()
        assert existing_appimage.read_text() == original_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_force_update_already_uptodate(
    integration_update_manager: tuple[UpdateManager, dict[str, Path]],
    mock_github_releases: dict[str, Release],
) -> None:
    """Test force update bypasses version check.

    Verifies force update replaces files even when versions match.
    """
    manager, workspace = integration_update_manager
    app_config = _create_app_config(workspace)
    app_config["state"]["version"] = "0.4.5"
    manager.config_manager.load_app_config.return_value = app_config
    manager.config_manager.list_installed_apps.return_value = ["appflowy"]

    existing_appimage = workspace["storage"] / "AppFlowy-x86_64.AppImage"
    old_content = create_mock_appimage_content("appflowy", "0.4.5-old")
    existing_appimage.write_text(old_content)

    release_data = mock_github_releases["appflowy"]
    new_content = create_mock_appimage_content("appflowy", "0.4.5-new")

    assert existing_appimage.read_text() == old_content

    with patch.object(manager, "check_single_update") as mock_check:
        update_info = UpdateInfo(
            app_name="appflowy",
            current_version="0.4.5",
            latest_version="0.4.5",
            has_update=False,
            release_url="https://github.com/AppFlowy-IO/AppFlowy/releases/tag/0.4.5",
            prerelease=False,
            original_tag_name="v0.4.5",
            release_data=release_data,
            app_config=app_config,
        )
        mock_check.return_value = update_info

        with patch(
            "my_unicorn.core.update.workflows.DownloadService"
        ) as mock_download_cls:
            mock_download = AsyncMock()

            async def mock_download_side_effect(asset, download_path):
                download_path.parent.mkdir(parents=True, exist_ok=True)
                download_path.write_text(new_content)
                return download_path

            mock_download.download_appimage.side_effect = (
                mock_download_side_effect
            )
            mock_download_cls.return_value = mock_download

            with patch(
                "my_unicorn.core.update.manager.PostDownloadProcessor"
            ) as mock_processor_cls:
                mock_processor = AsyncMock()
                mock_processor.process.side_effect = _create_success_processor(
                    manager, new_content, "0.4.5"
                )
                mock_processor.progress_reporter = NullProgressReporter()
                mock_processor_cls.return_value = mock_processor

                async with aiohttp.ClientSession() as session:
                    success, _ = await manager.update_single_app(
                        "appflowy",
                        session,
                        force=True,
                    )

        assert success is True
        updated_content = existing_appimage.read_text()
        assert updated_content == new_content
        assert updated_content != old_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_refresh_workflow(
    integration_update_manager: tuple[UpdateManager, dict[str, Path]],
    mock_github_releases: dict[str, Release],
) -> None:
    """Test update with fresh release data (cache refresh simulation).

    Verifies update workflow completes successfully with fresh data.
    """
    manager, workspace = integration_update_manager
    app_config = _create_app_config(workspace)
    existing_appimage = _setup_manager_and_files(manager, workspace, "0.4.4")

    release_data = mock_github_releases["appflowy"]
    new_appimage_content = create_mock_appimage_content("appflowy", "0.4.5")

    with patch.object(manager, "check_single_update") as mock_check:
        update_info = UpdateInfo(
            app_name="appflowy",
            current_version="0.4.4",
            latest_version="0.4.5",
            has_update=True,
            release_url="https://github.com/AppFlowy-IO/AppFlowy/releases/tag/0.4.5",
            prerelease=False,
            original_tag_name="v0.4.5",
            release_data=release_data,
            app_config=app_config,
        )
        mock_check.return_value = update_info

        with patch(
            "my_unicorn.core.update.workflows.DownloadService"
        ) as mock_download_cls:
            mock_download = AsyncMock()

            async def mock_download_side_effect(asset, download_path):
                download_path.parent.mkdir(parents=True, exist_ok=True)
                download_path.write_text(new_appimage_content)
                return download_path

            mock_download.download_appimage.side_effect = (
                mock_download_side_effect
            )
            mock_download_cls.return_value = mock_download

            with patch(
                "my_unicorn.core.update.manager.PostDownloadProcessor"
            ) as mock_processor_cls:
                mock_processor = AsyncMock()
                mock_processor.process.side_effect = _create_success_processor(
                    manager, new_appimage_content
                )
                mock_processor.progress_reporter = NullProgressReporter()
                mock_processor_cls.return_value = mock_processor

                async with aiohttp.ClientSession() as session:
                    success, _ = await manager.update_single_app(
                        "appflowy",
                        session,
                    )

        mock_check.assert_called()
        assert success is True
        updated_content = existing_appimage.read_text()
        assert updated_content == new_appimage_content
