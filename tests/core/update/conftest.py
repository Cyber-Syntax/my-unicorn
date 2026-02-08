"""Pytest configuration and fixtures for update module tests.

This module provides shared test fixtures and helper utilities for update
module testing, including mocked external dependencies, core services,
and test data factories.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.update.info import UpdateInfo

# =============================================================================
# Mock External Dependencies
# =============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Provide AsyncMock for aiohttp.ClientSession.

    Returns:
        AsyncMock configured for HTTP session operations.

    """
    return AsyncMock(spec=aiohttp.ClientSession)


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Provide MagicMock for ConfigManager.

    Includes pre-configured return values for:
    - load_global_config: Returns default global configuration
    - load_app_config: Returns default app configuration
    - load_catalog: Returns default catalog data
    - list_installed_apps: Returns list of test app names

    Returns:
        MagicMock configured for ConfigManager operations.

    """
    mock = MagicMock()
    mock.load_global_config.return_value = {
        "max_concurrent_downloads": 3,
        "directory": {
            "storage": Path("/test/storage"),
            "download": Path("/test/download"),
            "backup": Path("/test/backup"),
            "icon": Path("/test/icon"),
            "cache": Path("/test/cache"),
            "settings": Path("/test/settings"),
            "logs": Path("/test/logs"),
        },
    }
    mock.load_app_config.return_value = {
        "owner": "test-owner",
        "repo": "test-repo",
        "source": "catalog",
        "appimage": {
            "name": "test-app.AppImage",
            "version": "1.0.0",
            "characteristic_suffix": ["-x86_64", "-linux"],
        },
    }
    mock.load_catalog.return_value = {
        "apps": {
            "test-app": {
                "owner": "test-owner",
                "repo": "test-repo",
            }
        }
    }
    mock.list_installed_apps.return_value = ["app1", "app2"]
    return mock


@pytest.fixture
def mock_auth_manager() -> MagicMock:
    """Provide MagicMock for GitHubAuthManager.

    Includes pre-configured return values for authentication operations.

    Returns:
        MagicMock configured for GitHubAuthManager operations.

    """
    mock = MagicMock()
    mock.get_token.return_value = "test-token"
    mock.is_authenticated.return_value = True
    mock.apply_auth.return_value = {"Authorization": "token test-token"}
    mock.get_rate_limit_status.return_value = {
        "remaining": 5000,
        "reset": None,
    }
    mock.should_wait_for_rate_limit.return_value = False
    return mock


@pytest.fixture
def mock_cache_manager() -> MagicMock:
    """Provide MagicMock for ReleaseCacheManager.

    Includes pre-configured return values for cache operations.

    Returns:
        MagicMock configured for ReleaseCacheManager operations.

    """
    mock = MagicMock()
    mock.cache_dir = Path("/test/cache/releases")
    mock.ttl_hours = 24
    return mock


@pytest.fixture
def mock_progress_reporter() -> MagicMock:
    """Provide MagicMock for ProgressReporter.

    Includes pre-configured return values for progress operations.

    Returns:
        MagicMock configured for ProgressReporter operations.

    """
    mock = MagicMock()
    mock.is_active.return_value = True
    mock.add_task.return_value = "task-id"
    return mock


# =============================================================================
# Mock Core Services
# =============================================================================


@pytest.fixture
def mock_backup_service() -> MagicMock:
    """Provide MagicMock for BackupService.

    Returns:
        MagicMock configured for BackupService operations with
        create_backup returning a Path object.

    """
    mock = MagicMock()
    mock.create_backup.return_value = Path("/test/backup/app.backup")
    return mock


@pytest.fixture
def mock_download_service() -> AsyncMock:
    """Provide AsyncMock for DownloadService.

    Returns:
        AsyncMock configured for DownloadService operations with
        download_appimage returning a Path object.

    """
    mock = AsyncMock()
    mock.download_appimage.return_value = Path("/test/download/app.AppImage")
    mock.download_file.return_value = Path("/test/download/checksum.sha256")
    return mock


@pytest.fixture
def mock_verification_service() -> MagicMock:
    """Provide MagicMock for VerificationService.

    Returns:
        MagicMock configured for VerificationService operations.

    """
    mock = MagicMock()
    mock.verify_file.return_value = MagicMock(is_verified=True)
    return mock


@pytest.fixture
def mock_post_download_processor() -> AsyncMock:
    """Provide AsyncMock for PostDownloadProcessor.

    Returns:
        AsyncMock configured for PostDownloadProcessor operations with
        process method returning operation result.

    """
    mock = AsyncMock()
    mock.process.return_value = MagicMock(success=True)
    return mock


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_app_config() -> dict[str, Any]:
    """Provide sample application configuration.

    Returns:
        Dictionary with standard app configuration structure including
        owner, repo, appimage details, and icon settings.

    """
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
def sample_catalog() -> dict[str, Any]:
    """Provide sample catalog data.

    Returns:
        Dictionary with catalog structure containing application entries.

    """
    return {
        "version": "1.0.0",
        "apps": {
            "test-app": {
                "owner": "test-owner",
                "repo": "test-repo",
                "icon": "https://example.com/icon.png",
            },
            "another-app": {
                "owner": "another-owner",
                "repo": "another-repo",
                "icon": "https://example.com/icon2.png",
            },
        },
    }


@pytest.fixture
def sample_asset() -> Asset:
    """Provide sample AppImage asset.

    Returns:
        Asset object representing an AppImage release asset with realistic
        name, URL, size, and content type.

    """
    return Asset(
        name="test-app-1.0.0-x86_64.AppImage",
        browser_download_url="https://github.com/test-owner/test-repo/releases/download/v1.0.0/test-app-1.0.0-x86_64.AppImage",
        size=100_000_000,
        digest="",
    )


@pytest.fixture
def sample_release_data(sample_asset: Asset) -> Release:
    """Provide sample Release object with test data.

    Args:
        sample_asset: The sample asset fixture for asset inclusion.

    Returns:
        Release object with realistic GitHub release data.

    """
    return Release(
        owner="test-owner",
        repo="test-repo",
        version="1.0.0",
        prerelease=False,
        assets=[sample_asset],
        original_tag_name="v1.0.0",
    )


# =============================================================================
# UpdateInfo Factory Fixtures
# =============================================================================


@pytest.fixture
def update_info_factory() -> Callable[..., UpdateInfo]:
    """Provide factory function to create UpdateInfo instances.

    This factory allows customization of UpdateInfo fields while providing
    sensible defaults for all required attributes.

    Returns:
        Factory function accepting optional keyword arguments for UpdateInfo
        fields. Returns configured UpdateInfo instance.

    Example:
        >>> update_info = update_info_factory(
        ...     app_name="custom-app",
        ...     has_update=True,
        ...     latest_version="2.0.0"
        ... )

    """

    def _create_update_info(**overrides: Any) -> UpdateInfo:  # noqa: ANN401
        """Create UpdateInfo with customizable fields."""
        defaults = {
            "app_name": "test-app",
            "current_version": "1.0.0",
            "latest_version": "1.1.0",
            "has_update": True,
            "release_url": "https://github.com/test-owner/test-repo/releases/tag/v1.1.0",
            "prerelease": False,
            "original_tag_name": "v1.1.0",
            "release_data": None,
            "app_config": None,
            "error_reason": None,
        }
        defaults.update(overrides)
        return UpdateInfo(**defaults)

    return _create_update_info


@pytest.fixture
def error_update_info(
    update_info_factory: Callable[..., UpdateInfo],
) -> UpdateInfo:
    """Provide UpdateInfo with error condition.

    Returns:
        UpdateInfo instance representing a failed update check with
        error_reason set to indicate the failure.

    """
    return update_info_factory(
        error_reason="Failed to fetch release data: Network error"
    )


@pytest.fixture
def skip_update_info(
    update_info_factory: Callable[..., UpdateInfo],
) -> UpdateInfo:
    """Provide UpdateInfo for skip scenarios (no update available).

    Returns:
        UpdateInfo instance with has_update=False, representing an
        application that is already up to date.

    """
    return update_info_factory(
        current_version="1.0.0",
        latest_version="1.0.0",
        has_update=False,
    )
