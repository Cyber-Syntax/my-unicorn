"""Fixtures for backup service tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.core.backup import BackupService


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
