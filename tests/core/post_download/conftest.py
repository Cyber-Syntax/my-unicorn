"""Pytest fixtures for post_download module tests.

Provides shared test fixtures for post_download module, including mocked
external dependencies, core services, and test data factories specific to
post-download processing workflows.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.github import Asset, Release
from my_unicorn.core.post_download import (
    OperationType,
    PostDownloadContext,
    PostDownloadProcessor,
    PostDownloadResult,
)

# =============================================================================
# Module-Specific Service Mocks
# =============================================================================


@pytest.fixture
def mock_download_service_post() -> AsyncMock:
    """Provide AsyncMock for DownloadService (post_download context).

    Returns:
        AsyncMock configured for DownloadService operations.

    """
    mock = AsyncMock()
    mock.download_file = AsyncMock(
        return_value=Path("/test/download/SHA256SUMS.txt")
    )
    mock.progress_reporter = MagicMock()
    return mock


@pytest.fixture
def mock_storage_service_post() -> MagicMock:
    """Provide MagicMock for FileOperations (storage/file operations).

    Returns:
        MagicMock configured for FileOperations operations.

    """
    mock = MagicMock()
    mock.make_executable = MagicMock()
    mock.move_to_install_dir = MagicMock(
        return_value=Path("/opt/appimages/test-app.AppImage")
    )
    mock.ensure_dir_exists = MagicMock()
    mock.delete_file = MagicMock()
    return mock


@pytest.fixture
def mock_config_manager_post() -> MagicMock:
    """Provide MagicMock for ConfigManager (post_download context).

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
        "catalog_ref": "test-app",
        "state": {
            "version": "1.0.0",
            "installed_date": "2025-01-01T00:00:00Z",
            "installed_path": "/opt/appimages/test-app.AppImage",
        },
    }
    return mock


@pytest.fixture
def mock_verification_service_post() -> AsyncMock:
    """Provide AsyncMock for VerificationService (post_download context).

    Returns:
        AsyncMock configured for VerificationService operations.

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
        }
    )
    return mock


@pytest.fixture
def mock_backup_service_post() -> MagicMock:
    """Provide MagicMock for BackupService (post_download context).

    Returns:
        MagicMock configured for BackupService operations.

    """
    mock = MagicMock()
    mock.create_backup = MagicMock(
        return_value=Path("/test/backup/test-app.backup")
    )
    mock.cleanup_old_backups = MagicMock()
    return mock


@pytest.fixture
def mock_progress_reporter_post() -> MagicMock:
    """Provide MagicMock for ProgressReporter (post_download context).

    Returns:
        MagicMock configured for ProgressReporter operations.

    """
    mock = MagicMock()
    mock.is_active = MagicMock(return_value=True)
    return mock


# =============================================================================
# Processor Fixture
# =============================================================================


@pytest.fixture
def processor_instance(  # noqa: PLR0913
    mock_download_service_post: AsyncMock,
    mock_storage_service_post: MagicMock,
    mock_config_manager_post: MagicMock,
    mock_verification_service_post: AsyncMock,
    mock_backup_service_post: MagicMock,
    mock_progress_reporter_post: MagicMock,
) -> PostDownloadProcessor:
    """Provide PostDownloadProcessor with all mock dependencies.

    Args:
        mock_download_service_post: Mocked download service.
        mock_storage_service_post: Mocked file operations service.
        mock_config_manager_post: Mocked configuration manager.
        mock_verification_service_post: Mocked verification service.
        mock_backup_service_post: Mocked backup service.
        mock_progress_reporter_post: Mocked progress reporter.

    Returns:
        PostDownloadProcessor instance with all dependencies injected.

    """
    return PostDownloadProcessor(
        download_service=mock_download_service_post,
        storage_service=mock_storage_service_post,
        config_manager=mock_config_manager_post,
        verification_service=mock_verification_service_post,
        backup_service=mock_backup_service_post,
        progress_reporter=mock_progress_reporter_post,
    )


# =============================================================================
# Context and Result Fixtures
# =============================================================================


@pytest.fixture
def sample_asset_post() -> Asset:
    """Provide sample AppImage asset for post_download tests.

    Returns:
        Asset object representing a realistic AppImage release asset.

    """
    hash_value = "abcdef0123456789abcdef0123456789abcdef"
    full_hash = f"sha256:{hash_value}0123456789abcdef0123456789abcdef"
    return Asset(
        name="test-app-1.0.0-x86_64.AppImage",
        size=100_000_000,
        digest=full_hash,
        browser_download_url=(
            "https://github.com/test-owner/test-repo/releases/download/"
            "v1.0.0/test-app-1.0.0-x86_64.AppImage"
        ),
    )


@pytest.fixture
def sample_release_post(sample_asset_post: Asset) -> Release:
    """Provide sample GitHub Release for post_download tests.

    Args:
        sample_asset_post: Sample asset fixture for inclusion in release.

    Returns:
        Release object with realistic GitHub release data.

    """
    return Release(
        owner="test-owner",
        repo="test-repo",
        version="1.0.0",
        prerelease=False,
        assets=[sample_asset_post],
        original_tag_name="v1.0.0",
    )


@pytest.fixture
def install_context(
    tmp_path: Path, sample_asset_post: Asset, sample_release_post: Release
) -> PostDownloadContext:
    """Provide PostDownloadContext for INSTALL operation.

    Args:
        tmp_path: Temporary directory from pytest.
        sample_asset_post: Sample asset for context.
        sample_release_post: Sample release for context.

    Returns:
        PostDownloadContext configured for INSTALL operation.

    """
    return PostDownloadContext(
        app_name="test-app",
        downloaded_path=tmp_path / "test-app-1.0.0-x86_64.AppImage",
        asset=sample_asset_post,
        release=sample_release_post,
        app_config={
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "test-app",
            "state": {
                "version": "1.0.0",
                "installed_date": "2025-01-01T00:00:00Z",
            },
        },
        catalog_entry={"name": "test-app", "owner": "test-owner"},
        operation_type=OperationType.INSTALL,
        owner="test-owner",
        repo="test-repo",
        verify_downloads=True,
        source="catalog",
    )


@pytest.fixture
def update_context(
    tmp_path: Path, sample_asset_post: Asset, sample_release_post: Release
) -> PostDownloadContext:
    """Provide PostDownloadContext for UPDATE operation.

    Args:
        tmp_path: Temporary directory from pytest.
        sample_asset_post: Sample asset for context.
        sample_release_post: Sample release for context.

    Returns:
        PostDownloadContext configured for UPDATE operation.

    """
    return PostDownloadContext(
        app_name="test-app",
        downloaded_path=tmp_path / "test-app-2.0.0-x86_64.AppImage",
        asset=sample_asset_post,
        release=sample_release_post,
        app_config={
            "config_version": "2.0.0",
            "source": "catalog",
            "catalog_ref": "test-app",
            "state": {
                "version": "2.0.0",
                "installed_date": "2025-02-01T00:00:00Z",
            },
        },
        catalog_entry={"name": "test-app", "owner": "test-owner"},
        operation_type=OperationType.UPDATE,
        owner="test-owner",
        repo="test-repo",
        verify_downloads=True,
        source="catalog",
    )


@pytest.fixture
def sample_post_download_result() -> PostDownloadResult:
    """Provide sample PostDownloadResult instance.

    Returns:
        PostDownloadResult configured as a successful installation result.

    """
    return PostDownloadResult(
        success=True,
        install_path=Path("/opt/appimages/test-app.AppImage"),
        verification_result={
            "passed": True,
            "methods": {
                "digest": {
                    "passed": True,
                    "hash": "abc123def456",
                    "algorithm": "SHA256",
                }
            },
        },
        icon_result={
            "success": True,
            "path": "/opt/icons/test-app.png",
            "source": "extracted",
        },
        config_result={"success": True, "operation": "install"},
        desktop_result={"success": True, "path": "/home/user/.local/share/"},
    )
