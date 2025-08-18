"""Tests for ConfigManager: global config, app config, catalog, and directory logic."""

from pathlib import Path

import orjson
import pytest

from my_unicorn.config import ConfigManager


@pytest.fixture
def config_dir(tmp_path):
    """Provide a temporary config directory for ConfigManager."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # Create dummy catalog directory with one app
    catalog_dir = Path(__file__).parent.parent / "my_unicorn" / "catalog"
    catalog_dir.mkdir(exist_ok=True)
    dummy_catalog = catalog_dir / "dummyapp.json"
    dummy_catalog.write_bytes(
        orjson.dumps(
            {
                "owner": "dummy",
                "repo": "dummyrepo",
                "appimage": {
                    "rename": "dummy",
                    "name_template": "",
                    "characteristic_suffix": [],
                },
                "verification": {
                    "digest": False,
                    "skip": False,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
                "icon": None,
            }
        )
    )
    return config_dir


@pytest.fixture
def config_manager(config_dir):
    """ConfigManager instance using temporary config_dir."""
    manager = ConfigManager(config_dir)
    # Set catalog_dir to our dummy catalog
    manager.catalog_dir = Path(__file__).parent.parent / "my_unicorn" / "catalog"
    return manager


def test_load_and_save_global_config(config_manager):
    """Test loading and saving global config."""
    config = config_manager.load_global_config()
    assert isinstance(config, dict)
    config["max_backup"] = 7
    config_manager.save_global_config(config)
    loaded = config_manager.load_global_config()
    assert loaded["max_backup"] == 7


def test_load_app_config_and_migration(config_manager):
    """Test saving, loading, and migrating app config."""
    app_name = "testapp"
    app_config = {
        "config_version": "1.0.0",
        "appimage": {
            "version": "1.2.3",
            "name": "test.AppImage",
            "rename": "test",
            "name_template": "",
            "characteristic_suffix": [],
            "installed_date": "2024-01-01",
            "digest": "abc123",
            "hash": "should_migrate",
        },
        "owner": "owner",
        "repo": "repo",
        "github": {"repo": True, "prerelease": False},
        "verification": {
            "digest": True,
            "skip": False,
            "checksum_file": "",
            "checksum_hash_type": "sha256",
        },
        "icon": {"url": "", "name": "icon.png", "installed": True},
    }
    config_manager.save_app_config(app_name, app_config)
    loaded = config_manager.load_app_config(app_name)
    assert loaded["appimage"]["digest"] == "should_migrate"
    assert "hash" not in loaded["appimage"]


def test_remove_app_config(config_manager):
    """Test removing app config file."""
    app_name = "toremove"
    app_config = {
        "config_version": "1.0.0",
        "appimage": {
            "version": "1.0",
            "name": "toremove.AppImage",
            "rename": "toremove",
            "name_template": "",
            "characteristic_suffix": [],
            "installed_date": "2024-01-01",
            "digest": "abc",
        },
        "owner": "owner",
        "repo": "repo",
        "github": {"repo": True, "prerelease": False},
        "verification": {
            "digest": True,
            "skip": False,
            "checksum_file": "",
            "checksum_hash_type": "sha256",
        },
        "icon": {"url": "", "name": "icon.png", "installed": True},
    }
    config_manager.save_app_config(app_name, app_config)
    assert (config_manager.apps_dir / f"{app_name}.json").exists()
    assert config_manager.remove_app_config(app_name) is True
    assert not (config_manager.apps_dir / f"{app_name}.json").exists()
    assert config_manager.remove_app_config(app_name) is False


def test_list_installed_apps(config_manager):
    """Test listing installed apps."""
    app_names = ["app1", "app2"]
    for name in app_names:
        config_manager.save_app_config(
            name,
            {
                "config_version": "1.0.0",
                "appimage": {
                    "version": "1.0",
                    "name": f"{name}.AppImage",
                    "rename": name,
                    "name_template": "",
                    "characteristic_suffix": [],
                    "installed_date": "2024-01-01",
                    "digest": "abc",
                },
                "owner": "owner",
                "repo": "repo",
                "github": {"repo": True, "prerelease": False},
                "verification": {
                    "digest": True,
                    "skip": False,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
                "icon": {"url": "", "name": "icon.png", "installed": True},
            },
        )
    installed = config_manager.list_installed_apps()
    assert set(installed) == set(app_names)


def test_list_catalog_apps(config_manager):
    """Test listing catalog apps."""
    catalog_apps = config_manager.list_catalog_apps()
    assert "dummyapp" in catalog_apps


def test_load_catalog_entry(config_manager):
    """Test loading catalog entry."""
    entry = config_manager.load_catalog_entry("dummyapp")
    assert entry is not None
    assert entry["owner"] == "dummy"
    assert entry["repo"] == "dummyrepo"


def test_ensure_directories_from_config(config_manager, tmp_path):
    """Test ensure_directories_from_config creates directories."""
    dirs = {
        "repo": tmp_path / "repo",
        "package": tmp_path / "package",
        "download": tmp_path / "download",
        "storage": tmp_path / "storage",
        "backup": tmp_path / "backup",
        "icon": tmp_path / "icon",
        "settings": tmp_path / "settings",
        "logs": tmp_path / "logs",
        "cache": tmp_path / "cache",
        "tmp": tmp_path / "tmp",
    }
    config = {
        "config_version": "1.0.0",
        "max_concurrent_downloads": 5,
        "max_backup": 1,
        "batch_mode": True,
        "locale": "en_US",
        "log_level": "INFO",
        "network": {"retry_attempts": 3, "timeout_seconds": 10},
        "directory": dirs,
    }
    config_manager.ensure_directories_from_config(config)
    for d in dirs.values():
        assert d.exists()
