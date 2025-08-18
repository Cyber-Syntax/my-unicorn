"""Tests for BackupService: backup creation, cleanup, and info."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.backup import BackupService


@pytest.fixture
def dummy_config(tmp_path):
    """Provide dummy config_manager and global_config for BackupService."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    global_config = {
        "directory": {"backup": backup_dir},
        "max_backup": 2,
    }
    config_manager = MagicMock()
    return config_manager, global_config, backup_dir


@pytest.fixture
def backup_service(dummy_config):
    config_manager, global_config, _ = dummy_config
    return BackupService(config_manager, global_config)


def test_create_backup_creates_file(backup_service, dummy_config, tmp_path):
    config_manager, global_config, backup_dir = dummy_config
    file_path = tmp_path / "app.AppImage"
    file_path.write_text("data")
    backup = backup_service.create_backup(file_path, backup_dir, version="1.2.3")
    assert backup.exists()
    assert backup.name.startswith("app-1.2.3.backup")
    assert backup.read_text() == "data"


def test_create_backup_missing_file(backup_service, dummy_config):
    _, _, backup_dir = dummy_config
    file_path = Path("nonexistent.AppImage")
    backup = backup_service.create_backup(file_path, backup_dir)
    assert backup is None


def test_cleanup_old_backups_removes_excess(backup_service, dummy_config, tmp_path):
    config_manager, global_config, backup_dir = dummy_config
    app_name = "app"
    app_config = {"appimage": {"name": "app.AppImage"}}
    config_manager.load_app_config.return_value = app_config
    # Create 4 backups with different times
    paths = []
    src_file = tmp_path / "app.AppImage"
    src_file.write_text("data")
    for i in range(4):
        p = backup_service.create_backup(src_file, backup_dir, version=f"v{i}")
        # Set mtime to simulate age
        old_time = datetime.now() - timedelta(days=i)
        p.write_text(f"data{i}")
        os_time = old_time.timestamp()
        os.utime(p, (os_time, os_time))
        paths.append(p)
    global_config["max_backup"] = 2
    backup_service.cleanup_old_backups(app_name)
    # Only 2 newest backups remain
    remaining = list(backup_dir.glob("app*.backup.AppImage"))
    assert len(remaining) == 2


def test_cleanup_old_backups_max_zero_removes_all(backup_service, dummy_config, tmp_path):
    config_manager, global_config, backup_dir = dummy_config
    app_name = "app"
    app_config = {"appimage": {"name": "app.AppImage"}}
    config_manager.load_app_config.return_value = app_config
    for i in range(3):
        backup_service.create_backup(tmp_path / "app.AppImage", backup_dir, version=f"v{i}")
    global_config["max_backup"] = 0
    backup_service.cleanup_old_backups(app_name)
    assert not list(backup_dir.glob("app*.backup.AppImage"))


def test_get_backup_info_returns_sorted_info(backup_service, dummy_config, tmp_path):
    config_manager, global_config, backup_dir = dummy_config
    app_name = "app"
    app_config = {"appimage": {"name": "app.AppImage"}}
    config_manager.load_app_config.return_value = app_config
    # Create backups with different times
    infos = []
    src_file = tmp_path / "app.AppImage"
    src_file.write_text("data")
    for i in range(3):
        p = backup_service.create_backup(src_file, backup_dir, version=f"v{i}")
        old_time = datetime.now() - timedelta(days=i)
        os_time = old_time.timestamp()
        os.utime(p, (os_time, os_time))
        infos.append((p, old_time))
    result = backup_service.get_backup_info(app_name)
    assert len(result) == 3
    # Sorted by created (newest first)
    assert result[0]["created"] > result[1]["created"] > result[2]["created"]
    assert all("name" in r and "size" in r and "path" in r for r in result)


def test_get_backup_info_missing_config(backup_service, dummy_config):
    config_manager, global_config, backup_dir = dummy_config
    app_name = "missing"
    config_manager.load_app_config.return_value = None
    result = backup_service.get_backup_info(app_name)
    assert result == []
