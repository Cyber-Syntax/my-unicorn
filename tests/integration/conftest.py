"""Pytest configuration and fixtures for integration tests."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from my_unicorn.config import ConfigManager
from my_unicorn.core.github import Asset, Release
from my_unicorn.core.protocols.progress import NullProgressReporter
from my_unicorn.core.update.manager import UpdateManager

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def temp_workspace(tmp_path: Path) -> dict[str, Path]:
    """Create real temporary workspace structure for integration testing.

    Uses pytest's tmp_path fixture to create actual temporary directories
    that persist for the duration of the test. Includes subdirectories for
    storage, cache, backups, and downloads.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        Dictionary with paths:
            - root: Root temporary workspace
            - storage: AppImage storage directory
            - cache: Release cache directory
            - backups: Backup storage directory
            - downloads: Download staging directory
            - config: Configuration directory

    """
    storage_dir = tmp_path / "storage"
    cache_dir = tmp_path / "cache"
    backup_dir = tmp_path / "backups"
    downloads_dir = tmp_path / "downloads"
    config_dir = tmp_path / "config"

    storage_dir.mkdir()
    cache_dir.mkdir()
    backup_dir.mkdir()
    downloads_dir.mkdir()
    config_dir.mkdir()

    return {
        "root": tmp_path,
        "storage": storage_dir,
        "cache": cache_dir,
        "backups": backup_dir,
        "downloads": downloads_dir,
        "config": config_dir,
    }


@pytest.fixture
def mock_github_releases() -> dict[str, Release]:
    """Create mock GitHub release data for testing.

    Returns realistic Release objects that mock common GitHub API responses
    for testing update scenarios.

    Returns:
        Dictionary mapping app identifiers to Release objects

    """
    appflowy_asset = Asset(
        name="AppFlowy-x86_64.AppImage",
        browser_download_url=(
            "https://example.com/releases/AppFlowy-x86_64.AppImage"
        ),
        size=150000000,
        digest="sha256:abc123def456",
    )
    appflowy_checksum_asset = Asset(
        name="AppFlowy-x86_64.AppImage.sha256",
        browser_download_url=(
            "https://example.com/releases/AppFlowy-x86_64.AppImage.sha256"
        ),
        size=64,
        digest="",
    )

    appflowy_release = Release(
        owner="AppFlowy-IO",
        repo="AppFlowy",
        version="0.4.5",
        prerelease=False,
        assets=[appflowy_asset, appflowy_checksum_asset],
        original_tag_name="v0.4.5",
    )

    zen_asset = Asset(
        name="zen-0.1.14-x86_64.AppImage",
        browser_download_url=(
            "https://example.com/releases/zen-0.1.14-x86_64.AppImage"
        ),
        size=200000000,
        digest="sha256:def456ghi789",
    )
    zen_checksum_asset = Asset(
        name="zen-0.1.14-x86_64.AppImage.sha256",
        browser_download_url=(
            "https://example.com/releases/zen-0.1.14-x86_64.AppImage.sha256"
        ),
        size=64,
        digest="",
    )

    zen_release = Release(
        owner="zen-browser",
        repo="desktop",
        version="0.1.14",
        prerelease=False,
        assets=[zen_asset, zen_checksum_asset],
        original_tag_name="v0.1.14",
    )

    return {
        "appflowy": appflowy_release,
        "zen": zen_release,
    }


@pytest.fixture
def integration_update_manager(
    temp_workspace: dict[str, Path],
) -> tuple[UpdateManager, dict[str, Path]]:
    """Create UpdateManager configured for integration testing with config.

    Creates a real UpdateManager with real config manager pointing to
    test directories. This allows actual filesystem operations and
    services to work correctly.

    Args:
        temp_workspace: Temporary workspace fixture

    Returns:
        Tuple of (UpdateManager instance, workspace paths dict)

    """
    # Create a mocked ConfigManager pointing to test directories
    mock_config = MagicMock(spec=ConfigManager)
    mock_config.load_global_config.return_value = {
        "directory": {
            "storage": temp_workspace["storage"],
            "cache": temp_workspace["cache"],
            "backup": temp_workspace["backups"],
            "download": temp_workspace["downloads"],
            "icon": temp_workspace["storage"],
        },
        "max_concurrent_downloads": 3,
        "max_backup": 5,
    }
    mock_config.list_installed_apps.return_value = []
    mock_config.app_config_manager = MagicMock()

    # Create real manager with actual services
    manager = UpdateManager(
        config_manager=mock_config,
        progress_reporter=NullProgressReporter(),
    )

    return manager, temp_workspace


def create_mock_appimage_content(app_name: str, version: str) -> str:
    """Create realistic mock AppImage file content for testing.

    Args:
        app_name: Name of the application
        version: Version number

    Returns:
        Mock content string

    """
    return f"Mock {app_name} AppImage version {version} content"


def create_checksum(content: str) -> str:
    """Create mock SHA256 checksum for content.

    Args:
        content: Content to checksum

    Returns:
        Mock checksum string

    """
    return hashlib.sha256(content.encode()).hexdigest()
