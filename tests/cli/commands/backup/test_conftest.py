"""Verification tests for conftest fixtures in tests/cli/commands/backup/."""

from pathlib import Path
from unittest.mock import MagicMock

from my_unicorn.cli.commands.backup import BackupHandler


def test_mock_config_manager_fixture(mock_config_manager: MagicMock) -> None:
    """Verify mock_config_manager is a MagicMock with ConfigManager spec."""
    assert isinstance(mock_config_manager, MagicMock)
    assert hasattr(mock_config_manager, "list_installed_apps")


def test_mock_auth_manager_fixture(mock_auth_manager: MagicMock) -> None:
    """Verify mock_auth_manager is a MagicMock."""
    assert isinstance(mock_auth_manager, MagicMock)


def test_mock_update_manager_fixture(mock_update_manager: MagicMock) -> None:
    """Verify mock_update_manager is a MagicMock."""
    assert isinstance(mock_update_manager, MagicMock)


def test_temp_config_fixture(temp_config: tuple) -> None:
    """Verify temp_config fixture returns proper tuple structure."""
    assert isinstance(temp_config, tuple)
    assert len(temp_config) == 3

    global_config, backup_dir, storage_dir = temp_config

    assert isinstance(global_config, dict)
    assert "directory" in global_config
    assert "max_backup" in global_config
    assert isinstance(backup_dir, Path)
    assert isinstance(storage_dir, Path)
    assert backup_dir.exists()
    assert storage_dir.exists()


def test_backup_handler_fixture(backup_handler: BackupHandler) -> None:
    """Verify backup_handler fixture creates BackupHandler instance."""
    assert isinstance(backup_handler, BackupHandler)
    assert hasattr(backup_handler, "global_config")
    assert hasattr(backup_handler, "backup_service")


def test_sample_app_config_fixture(sample_app_config: dict) -> None:
    """Verify sample_app_config has required keys."""
    assert "config_version" in sample_app_config
    assert sample_app_config["config_version"] == "2.0.0"
    assert "source" in sample_app_config
    assert "catalog_ref" in sample_app_config
    assert "state" in sample_app_config
    assert "overrides" in sample_app_config
