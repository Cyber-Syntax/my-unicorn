"""Pytest configuration and fixtures for install module tests.

This module provides shared test fixtures for the install module, including
mocked external dependencies, core services, and test data factories specific
to installation workflows.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.post_download import PostDownloadResult

# =============================================================================
# Mock External Dependencies
# =============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Provide AsyncMock for aiohttp.ClientSession.

    Returns:
        AsyncMock configured for HTTP session operations.

    """
    return AsyncMock()


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Provide MagicMock for ConfigManager.

    Includes pre-configured return values for configuration operations.

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
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "qownnotes",
        "state": {
            "version": "1.0.0",
            "installed_date": "2025-01-01T00:00:00Z",
            "installed_path": "/opt/appimages/qownnotes.AppImage",
            "verification": {
                "passed": True,
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "SHA256",
                    }
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "~/.local/share/icons/qownnotes.png",
            },
        },
        "overrides": {},
    }
    mock.load_catalog.return_value = {
        "version": "1.0.0",
        "apps": {
            "qownnotes": {
                "owner": "pbek",
                "repo": "QOwnNotes",
            }
        },
    }
    return mock


@pytest.fixture
def mock_auth_manager() -> MagicMock:
    """Provide MagicMock for GitHubAuthManager.

    Returns:
        MagicMock configured for authentication operations.

    """
    mock = MagicMock()
    mock.get_token.return_value = "test-token"
    mock.is_authenticated.return_value = True
    return mock


@pytest.fixture
def mock_cache_manager() -> MagicMock:
    """Provide MagicMock for ReleaseCacheManager.

    Returns:
        MagicMock configured for cache operations.

    """
    mock = MagicMock()
    mock.cache_dir = Path("/test/cache/releases")
    mock.ttl_hours = 24
    return mock


# =============================================================================
# Mock Core Services
# =============================================================================


@pytest.fixture
def mock_download_service() -> AsyncMock:
    """Provide AsyncMock for DownloadService.

    Includes pre-configured methods for:
    - download_appimage: Returns Path to downloaded file
    - download_file: Returns Path to downloaded checksum file
    - progress_reporter: Returns a mock progress reporter

    Returns:
        AsyncMock configured for DownloadService operations.

    """
    mock = AsyncMock()
    mock.download_appimage = AsyncMock(
        return_value=Path("/test/download/qownnotes-1.0.0.AppImage")
    )
    mock.download_file = AsyncMock(
        return_value=Path("/test/download/SHA256SUMS.txt")
    )
    mock.progress_reporter = MagicMock()
    return mock


@pytest.fixture
def mock_verification_service() -> AsyncMock:
    """Provide AsyncMock for VerificationService.

    Returns:
        AsyncMock configured for verification operations.

    """
    mock = AsyncMock()
    mock.verify_file = AsyncMock(
        return_value={
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash": "abc123def456",
                    "algorithm": "SHA256",
                }
            },
            "updated_config": {},
        }
    )
    return mock


@pytest.fixture
def mock_post_download_processor() -> AsyncMock:
    """Provide AsyncMock for PostDownloadProcessor.

    Pre-configured with successful processing result.

    Returns:
        AsyncMock configured for PostDownloadProcessor operations.

    """
    mock = AsyncMock()
    mock.process = AsyncMock(
        return_value=PostDownloadResult(
            success=True,
            install_path=Path("/opt/appimages/qownnotes.AppImage"),
            verification_result={"passed": True},
            icon_result={"path": "~/.local/share/icons/qownnotes.png"},
            config_result={"saved": True},
            desktop_result={
                "path": "~/.local/share/applications/qownnotes.desktop"
            },
            error=None,
        )
    )
    return mock


@pytest.fixture
def mock_github_client() -> AsyncMock:
    """Provide AsyncMock for GitHubClient.

    Returns:
        AsyncMock configured for GitHub API operations.

    """
    mock = AsyncMock()
    mock.get_release = AsyncMock()
    mock.get_releases = AsyncMock()
    return mock


@pytest.fixture
def mock_progress_reporter() -> MagicMock:
    """Provide MagicMock for ProgressReporter.

    Returns:
        MagicMock configured for progress tracking operations.

    """
    mock = MagicMock()
    mock.is_active.return_value = True
    mock.add_task = MagicMock(return_value="task-id")
    mock.update_task = MagicMock()
    mock.finish_task = AsyncMock()
    return mock


@pytest.fixture
def mock_storage_service() -> MagicMock:
    """Provide MagicMock for FileOperations.

    Returns:
        MagicMock configured for file storage operations.

    """
    mock = MagicMock()
    install_path = Path("/opt/appimages/qownnotes.AppImage")
    mock.move_file = MagicMock(return_value=install_path)
    mock.copy_file = MagicMock(return_value=install_path)
    mock.ensure_dir_exists = MagicMock()
    return mock


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_asset() -> Asset:
    """Provide sample AppImage asset.

    Returns:
        Asset object representing a realistic AppImage release asset.

    """
    hash_value = "abcdef0123456789abcdef0123456789abcdef"
    full_hash = f"sha256:{hash_value}0123456789abcdef0123456789abcdef"
    return Asset(
        name="QOwnNotes-1.0.0-x86_64.AppImage",
        size=100_000_000,
        digest=full_hash,
        browser_download_url=(
            "https://github.com/pbek/QOwnNotes/releases/download/v1.0.0/"
            "QOwnNotes-1.0.0-x86_64.AppImage"
        ),
    )


@pytest.fixture
def sample_release(sample_asset: Asset) -> Release:
    """Provide sample GitHub Release.

    Args:
        sample_asset: Sample asset fixture for inclusion in release.

    Returns:
        Release object with realistic GitHub release data.

    """
    return Release(
        owner="pbek",
        repo="QOwnNotes",
        version="1.0.0",
        prerelease=False,
        assets=[sample_asset],
        original_tag_name="v1.0.0",
    )


@pytest.fixture
def sample_app_config() -> dict[str, Any]:
    """Provide sample v2.0.0 application configuration.

    Returns:
        Dictionary with standard app configuration structure including
        metadata, source, appimage, verification, and icon settings.

    """
    return {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "qownnotes",
        "state": {
            "version": "1.0.0",
            "installed_date": "2025-01-01T00:00:00Z",
            "installed_path": "/opt/appimages/qownnotes.AppImage",
            "verification": {
                "passed": True,
                "actual_method": "digest",
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "SHA256",
                        "expected": "sha256:abc123abc123",
                        "computed": "abc123abc123",
                    }
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "~/.local/share/icons/qownnotes.png",
            },
        },
        "overrides": {
            "metadata": {
                "name": "QOwnNotes",
                "display_name": "QOwnNotes",
            },
            "source": {
                "type": "github",
                "owner": "pbek",
                "repo": "QOwnNotes",
                "prerelease": False,
            },
            "appimage": {
                "naming": {
                    "template": "QOwnNotes-{version}-x86_64.AppImage",
                    "target_name": "qownnotes.AppImage",
                    "architectures": ["x86_64"],
                }
            },
            "verification": {
                "method": "digest",
            },
            "icon": {
                "method": "extraction",
            },
        },
    }


@pytest.fixture
def sample_catalog_entry() -> dict[str, Any]:
    """Provide sample catalog entry with GitHub configuration.

    Returns:
        Dictionary with catalog entry structure including metadata,
        source configuration, and verification settings.

    """
    return {
        "metadata": {
            "name": "QOwnNotes",
            "display_name": "QOwnNotes",
            "description": "A note taking app for the command line",
        },
        "source": {
            "type": "github",
            "owner": "pbek",
            "repo": "QOwnNotes",
            "prerelease": False,
        },
        "appimage": {
            "naming": {
                "template": "QOwnNotes-{version}-x86_64.AppImage",
                "target_name": "qownnotes.AppImage",
                "architectures": ["x86_64"],
            }
        },
        "verification": {
            "method": "digest",
        },
        "icon": {
            "method": "extraction",
        },
    }


# =============================================================================
# Result Fixtures
# =============================================================================


@pytest.fixture
def sample_verification_result() -> dict[str, Any]:
    """Provide sample verification result.

    Returns:
        Dictionary with successful verification result including
        passed status, methods, and updated config.

    """
    hash_value = "abcdef0123456789abcdef0123456789abcdef"
    full_hash = f"sha256:{hash_value}0123456789abcdef0123456789abcdef"
    return {
        "passed": True,
        "actual_method": "digest",
        "methods": {
            "digest": {
                "type": "digest",
                "status": "passed",
                "algorithm": "SHA256",
                "expected": full_hash,
                "computed": hash_value + "0123456789abcdef0123456789abcdef",
                "source": "github_api",
            }
        },
        "updated_config": {
            "verification": {
                "method": "digest",
                "passed": True,
            }
        },
    }


@pytest.fixture
def sample_post_download_result() -> PostDownloadResult:
    """Provide sample successful post-download result.

    Returns:
        PostDownloadResult with success=True and all processed results.

    """
    return PostDownloadResult(
        success=True,
        install_path=Path("/opt/appimages/qownnotes.AppImage"),
        verification_result={
            "passed": True,
            "actual_method": "digest",
            "methods": {
                "digest": {
                    "type": "digest",
                    "status": "passed",
                    "algorithm": "SHA256",
                }
            },
        },
        icon_result={
            "installed": True,
            "method": "extraction",
            "path": "~/.local/share/icons/qownnotes.png",
        },
        config_result={"success": True, "operation": "install"},
        desktop_result={
            "success": True,
            "path": "~/.local/share/applications/qownnotes.desktop",
        },
        error=None,
    )


@pytest.fixture
def sample_install_result_success() -> dict[str, Any]:
    """Provide sample successful install result.

    Returns:
        Dictionary with install success result including app name,
        version, paths, and success status.

    """
    return {
        "success": True,
        "app_name": "qownnotes",
        "version": "1.0.0",
        "source": "catalog",
        "message": "Successfully installed qownnotes v1.0.0",
        "installed_path": "/opt/appimages/qownnotes.AppImage",
        "icon": "~/.local/share/icons/qownnotes.png",
        "desktop": "~/.local/share/applications/qownnotes.desktop",
    }


@pytest.fixture
def sample_install_result_failure() -> dict[str, Any]:
    """Provide sample failed install result.

    Returns:
        Dictionary with install failure result including error message
        and failure indicator.

    """
    return {
        "success": False,
        "app_name": "qownnotes",
        "version": "1.0.0",
        "source": "catalog",
        "message": "Failed to install qownnotes v1.0.0",
        "error": "Verification failed: SHA256 checksum mismatch",
        "installed_path": None,
        "icon": None,
        "desktop": None,
    }
