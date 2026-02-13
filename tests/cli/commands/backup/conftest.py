"""Fixtures for backup command tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.cli.commands.backup import BackupHandler
from my_unicorn.config import ConfigManager
from my_unicorn.core.backup import BackupService


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Mock configuration manager."""
    config_manager = MagicMock(spec=ConfigManager)
    config_manager.list_installed_apps.return_value = [
        "appflowy",
        "freetube",
        "obsidian",
    ]
    return config_manager


@pytest.fixture
def mock_auth_manager() -> MagicMock:
    """Mock authentication manager."""
    return MagicMock()


@pytest.fixture
def mock_update_manager() -> MagicMock:
    """Mock update manager."""
    return MagicMock()


@pytest.fixture
def temp_config(tmp_path: Path) -> tuple:
    """Create temporary configuration with backup directory."""
    backup_dir = tmp_path / "backups"
    storage_dir = tmp_path / "Applications"

    backup_dir.mkdir(parents=True)
    storage_dir.mkdir(parents=True)

    global_config = {
        "directory": {
            "backup": backup_dir,
            "storage": storage_dir,
        },
        "max_backup": 3,
    }
    return global_config, backup_dir, storage_dir


@pytest.fixture
def backup_handler(
    mock_config_manager: MagicMock,
    mock_auth_manager: MagicMock,
    mock_update_manager: MagicMock,
    temp_config: tuple,
) -> BackupHandler:
    """Create BackupHandler instance with mocked dependencies."""
    global_config, _, _ = temp_config
    handler = BackupHandler(
        mock_config_manager, mock_auth_manager, mock_update_manager
    )
    handler.global_config = global_config
    handler.backup_service = BackupService(  # type: ignore[attr-defined]
        mock_config_manager, global_config
    )
    return handler


@pytest.fixture
def sample_app_config() -> dict:
    """Sample app configuration (v2 format)."""
    return {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "appflowy",
        "state": {
            "version": "1.2.3",
            "installed_date": "2024-08-19T12:50:44.179839",
            "installed_path": "/path/to/storage/appflowy.AppImage",
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
                "name": "appflowy",
                "display_name": "AppFlowy",
            },
            "source": {
                "type": "github",
                "owner": "AppFlowy-IO",
                "repo": "AppFlowy",
                "prerelease": False,
            },
            "appimage": {
                "rename": "appflowy",
            },
            "verification": {
                "methods": ["digest"],
            },
            "icon": {
                "method": "extraction",
            },
        },
    }
