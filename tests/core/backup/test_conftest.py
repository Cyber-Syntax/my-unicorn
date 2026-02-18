"""Verification tests for conftest fixtures in tests/core/backup/."""

from pathlib import Path
from unittest.mock import MagicMock

from my_unicorn.core.backup import BackupService


def test_dummy_config_fixture(dummy_config: tuple) -> None:
    """Verify dummy_config fixture returns proper tuple structure."""
    assert isinstance(dummy_config, tuple)
    assert len(dummy_config) == 4

    config_manager, global_config, backup_dir, storage_dir = dummy_config

    assert isinstance(config_manager, MagicMock)
    assert isinstance(global_config, dict)
    assert "directory" in global_config
    assert "max_backup" in global_config
    assert isinstance(backup_dir, Path)
    assert isinstance(storage_dir, Path)


def test_backup_service_fixture(backup_service: BackupService) -> None:
    """Verify backup_service fixture creates BackupService instance."""
    assert isinstance(backup_service, BackupService)


def test_sample_app_config_fixture(sample_app_config: dict) -> None:
    """Verify sample_app_config has required keys for v2 config."""
    assert "config_version" in sample_app_config
    assert sample_app_config["config_version"] == "2.0.0"
    assert "source" in sample_app_config
    assert "catalog_ref" in sample_app_config
    assert "state" in sample_app_config
    assert "overrides" in sample_app_config


def test_sample_v1_app_config_fixture(sample_v1_app_config: dict) -> None:
    """Verify sample_v1_app_config has required keys for v1 config."""
    assert "config_version" in sample_v1_app_config
    assert sample_v1_app_config["config_version"] == "1.0.0"
    assert "appimage" in sample_v1_app_config
    assert "version" in sample_v1_app_config["appimage"]
    assert "name" in sample_v1_app_config["appimage"]
