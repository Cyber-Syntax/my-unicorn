"""Pytest configuration and fixtures for core module tests.

This module provides shared test fixtures for all core module tests, including:
- Mocked external dependencies (sessions, config managers)
- Mock service implementations
- Test data factories (sample assets, releases)

Fixtures defined here are available to all tests in the core module and its
submodules without explicit imports.
"""

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from my_unicorn.core.backup import BackupService
from my_unicorn.core.github import Asset, Release
from my_unicorn.core.protocols import ProgressReporter, ProgressType

# =============================================================================
# Async Helpers
# =============================================================================


async def async_chunk_gen(
    chunks: list[bytes],
) -> AsyncGenerator[bytes, None]:
    """Async generator yielding chunks for simulating HTTP responses.

    Args:
        chunks: List of byte chunks to yield.

    Yields:
        Individual byte chunks.

    """
    for chunk in chunks:
        yield chunk


# =============================================================================
# Mock Progress Reporter
# =============================================================================


class MockProgressReporter(ProgressReporter):
    """Mock implementation of ProgressReporter for testing.

    Tracks all method calls and task state for verification in tests.
    Methods are async to match the actual ProgressReporter interface.
    """

    def __init__(self) -> None:
        """Initialize mock reporter with empty tracking collections."""
        self.tasks: dict[str, dict] = {}
        self.updates: list[tuple[str, float | None, str | None]] = []
        self.finished: list[tuple[str, bool, str | None]] = []
        self._active = True
        self._task_counter = 0

    def is_active(self) -> bool:
        """Return whether the reporter is active.

        Returns:
            True if reporter is active, False otherwise.

        """
        return self._active

    async def add_task(
        self,
        name: str,
        progress_type: ProgressType,
        total: float | None = None,
    ) -> str:
        """Add a task and return its ID.

        Args:
            name: Task name.
            progress_type: Type of progress to report.
            total: Total amount for the task (optional).

        Returns:
            Unique task ID.

        """
        self._task_counter += 1
        task_id = f"mock-task-{self._task_counter}"
        self.tasks[task_id] = {
            "name": name,
            "progress_type": progress_type,
            "total": total,
            "completed": 0,
            "description": "",
        }
        return task_id

    async def update_task(
        self,
        task_id: str,
        completed: float | None = None,
        description: str | None = None,
    ) -> None:
        """Record a task update.

        Args:
            task_id: ID of the task to update.
            completed: Completion amount (optional).
            description: Task description (optional).

        """
        self.updates.append((task_id, completed, description))
        if task_id in self.tasks:
            if completed is not None:
                self.tasks[task_id]["completed"] = completed
            if description is not None:
                self.tasks[task_id]["description"] = description

    async def finish_task(
        self,
        task_id: str,
        *,
        success: bool = True,
        description: str | None = None,
    ) -> None:
        """Record a task finish.

        Args:
            task_id: ID of the task to finish.
            success: Whether the task completed successfully.
            description: Finish description (optional).

        """
        self.finished.append((task_id, success, description))

    def get_task_info(self, task_id: str) -> dict[str, object]:
        """Get task info by ID.

        Args:
            task_id: ID of the task.

        Returns:
            Dictionary with task information, or empty dict if not found.

        """
        if task_id in self.tasks:
            return self.tasks[task_id]
        return {}


# =============================================================================
# Mock External Dependencies
# =============================================================================


@pytest_asyncio.fixture
def mock_session() -> AsyncMock:
    """Provide AsyncMock for aiohttp.ClientSession.

    Returns:
        AsyncMock configured for HTTP session operations.

    """
    return AsyncMock()


@pytest.fixture
def tmp_file(tmp_path: Path) -> Path:
    """Create a temporary file path for downloads.

    Args:
        tmp_path: pytest temporary directory fixture.

    Returns:
        Path to a temporary file suitable for download testing.

    """
    return tmp_path / "testfile.bin"


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
        "catalog_ref": "test-app",
        "state": {
            "version": "1.0.0",
            "installed_date": "2025-01-01T00:00:00Z",
            "installed_path": "/opt/appimages/test-app.AppImage",
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
        },
    }
    return mock


# =============================================================================
# Mock Core Services
# =============================================================================


@pytest.fixture
def mock_download_service() -> AsyncMock:
    """Provide AsyncMock for DownloadService.

    Includes pre-configured methods for download operations and
    progress reporting.

    Returns:
        AsyncMock configured for DownloadService operations.

    """
    mock = AsyncMock()
    mock.download_appimage = AsyncMock(
        return_value=Path("/test/download/test-app-1.0.0.AppImage")
    )
    mock.download_file = AsyncMock(
        return_value=Path("/test/download/SHA256SUMS.txt")
    )
    mock.progress_reporter = MagicMock()
    return mock


@pytest.fixture
def mock_file_operations() -> AsyncMock:
    """Provide AsyncMock for FileOperations.

    Includes pre-configured methods for file handling operations.

    Returns:
        AsyncMock configured for FileOperations operations.

    """
    mock = AsyncMock()
    mock.move_file = AsyncMock(
        return_value=Path("/opt/appimages/test-app.AppImage")
    )
    mock.copy_file = AsyncMock(
        return_value=Path("/opt/appimages/test-app.AppImage")
    )
    mock.ensure_dir_exists = AsyncMock()
    mock.delete_file = AsyncMock()
    return mock


@pytest.fixture
def mock_verification_service() -> AsyncMock:
    """Provide AsyncMock for VerificationService.

    Includes pre-configured methods for verification operations.

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
            "updated_config": {},
        }
    )
    return mock


@pytest.fixture
def mock_backup_service() -> AsyncMock:
    """Provide AsyncMock for BackupService.

    Includes pre-configured methods for backup operations.

    Returns:
        AsyncMock configured for BackupService operations.

    """
    mock = AsyncMock()
    mock.create_backup = AsyncMock(
        return_value=Path("/test/backup/test-app.backup")
    )
    mock.restore_backup = AsyncMock()
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
        name="test-app-1.0.0-x86_64.AppImage",
        size=100_000_000,
        digest=full_hash,
        browser_download_url=(
            "https://github.com/test-owner/test-repo/releases/download/"
            "v1.0.0/test-app-1.0.0-x86_64.AppImage"
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
        owner="test-owner",
        repo="test-repo",
        version="1.0.0",
        prerelease=False,
        assets=[sample_asset],
        original_tag_name="v1.0.0",
    )


@pytest.fixture
def dummy_config(tmp_path: Path) -> tuple:
    """Provide dummy config_manager and global_config for BackupService."""
    backup_dir = tmp_path / "backups"
    storage_dir = tmp_path / "Applications"
    backup_dir.mkdir()
    storage_dir.mkdir()

    global_config = {
        "directory": {"backup": backup_dir, "storage": storage_dir},
        "max_backup": 2,
    }
    config_manager = MagicMock()
    config_manager.list_installed_apps.return_value = [
        "app1",
        "app2",
        "freetube",
    ]
    return config_manager, global_config, backup_dir, storage_dir


@pytest.fixture
def backup_service(dummy_config: tuple) -> BackupService:
    """Create BackupService instance for testing."""
    config_manager, global_config, _, _ = dummy_config
    return BackupService(config_manager, global_config)


@pytest.fixture
def sample_app_config() -> dict:
    """Sample app configuration for testing (v2 format)."""
    return {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "app1",
        "state": {
            "version": "1.2.3",
            "installed_date": "2024-08-19T12:50:44.179839",
            "installed_path": "/path/to/storage/app1.AppImage",
            "verification": {
                "passed": True,
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "abc123def456",
                        "computed": "abc123def456",
                        "source": "github_api",
                    }
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "/path/to/icon.png",
            },
        },
        "overrides": {
            "metadata": {
                "name": "app1",
                "display_name": "App1",
            },
            "source": {
                "type": "github",
                "owner": "owner",
                "repo": "repo",
                "prerelease": False,
            },
            "appimage": {
                "rename": "app1",
            },
            "verification": {
                "methods": ["digest"],
            },
            "icon": {
                "method": "extraction",
            },
        },
    }


@pytest.fixture
def sample_v1_app_config() -> dict:
    """Sample app configuration for testing (v1 format - legacy)."""
    return {
        "config_version": "1.0.0",
        "appimage": {
            "version": "1.2.3",
            "name": "app1.AppImage",
            "rename": "app1",
            "installed_date": "2024-08-19T12:50:44.179839",
            "digest": "sha256:abc123def456",
        },
    }
