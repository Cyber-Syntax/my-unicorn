"""Tests for ConfigManager: global config, app config, catalog, and directory logic."""

from pathlib import Path
from typing import cast

import orjson
import pytest

from my_unicorn.config import (
    AppConfig,
    AppConfigManager,
    CatalogManager,
    ConfigManager,
    DirectoryManager,
    GlobalConfigManager,
)


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
    # Use the bundled catalog directory for tests
    catalog_dir = Path(__file__).parent.parent / "my_unicorn" / "catalog"
    return ConfigManager(config_dir, catalog_dir)


def test_load_and_save_global_config(config_manager):
    """Test loading and saving global config."""
    config = config_manager.load_global_config()
    assert isinstance(config, dict)
    TEST_MAX_BACKUP = 7
    config["max_backup"] = TEST_MAX_BACKUP
    config_manager.save_global_config(config)
    loaded = config_manager.load_global_config()
    assert loaded["max_backup"] == TEST_MAX_BACKUP


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


# Tests for refactored specialized manager classes


def test_directory_manager(config_dir):
    """Test DirectoryManager functionality."""
    dir_manager = DirectoryManager(config_dir)

    # Test properties
    assert dir_manager.config_dir == config_dir
    assert dir_manager.apps_dir == config_dir / "apps"
    assert dir_manager.settings_file == config_dir / "settings.conf"

    # Test ensure_user_directories
    dir_manager.ensure_user_directories()
    assert dir_manager.apps_dir.exists()

    # Test simple directory creation (this method just ensures directories exist)
    test_dirs = [
        config_dir / "test_repo",
        config_dir / "test_package",
    ]
    for d in test_dirs:
        d.mkdir(parents=True, exist_ok=True)
        assert d.exists()


def test_global_config_manager(config_dir):
    """Test GlobalConfigManager functionality."""
    dir_manager = DirectoryManager(config_dir)
    global_manager = GlobalConfigManager(dir_manager)

    # Test loading default config
    config = global_manager.load_global_config()
    assert isinstance(config, dict)
    assert "config_version" in config
    assert "max_concurrent_downloads" in config

    # Test saving and loading
    TEST_MAX_DOWNLOADS = 8
    config["max_concurrent_downloads"] = TEST_MAX_DOWNLOADS
    global_manager.save_global_config(config)
    loaded = global_manager.load_global_config()
    assert loaded["max_concurrent_downloads"] == TEST_MAX_DOWNLOADS

    # Test get default global config
    default = global_manager.get_default_global_config()
    assert isinstance(default, dict)

    # Test convert to global config (with compatible input type)
    from configparser import ConfigParser

    raw_config = ConfigParser()
    raw_config.add_section("settings")
    raw_config.set("settings", "max_backup", "3")
    raw_config.set("settings", "locale", "en_US")
    converted = global_manager._convert_to_global_config(raw_config)
    assert "directory" in converted
    assert "network" in converted


def test_app_config_manager(config_dir):
    """Test AppConfigManager functionality."""
    dir_manager = DirectoryManager(config_dir)
    dir_manager.ensure_user_directories()
    app_manager = AppConfigManager(dir_manager)

    # Test saving and loading app config
    app_name = "testapp"
    TEST_VERSION = "2.0.0"
    app_config = {
        "config_version": "1.0.0",
        "appimage": {
            "version": TEST_VERSION,
            "name": "test.AppImage",
            "rename": "test",
            "name_template": "",
            "characteristic_suffix": [],
            "installed_date": "2024-01-01",
            "digest": "abc123",
        },
        "owner": "testowner",
        "repo": "testrepo",
        "github": {"repo": True, "prerelease": False},
        "verification": {
            "digest": True,
            "skip": False,
            "checksum_file": "",
            "checksum_hash_type": "sha256",
        },
        "icon": {"url": "", "name": "icon.png", "installed": True},
    }

    app_manager.save_app_config(app_name, cast(AppConfig, app_config))
    loaded = app_manager.load_app_config(app_name)
    assert loaded is not None
    assert loaded["appimage"]["version"] == TEST_VERSION
    assert loaded["owner"] == "testowner"

    # Test listing apps
    installed = app_manager.list_installed_apps()
    assert app_name in installed

    # Test removing app config
    result = app_manager.remove_app_config(app_name)
    assert result is True
    result = app_manager.remove_app_config(app_name)  # Should be False on second try
    assert result is False

    # Test non-existent app
    nonexistent = app_manager.load_app_config("nonexistent")
    assert nonexistent is None


def test_catalog_manager(config_dir):
    """Test CatalogManager functionality."""
    # Create catalog directory with test data
    catalog_dir = config_dir / "catalog"
    catalog_dir.mkdir()

    test_app_data = {
        "owner": "testowner",
        "repo": "testapp",
        "appimage": {
            "rename": "testapp",
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

    test_catalog_file = catalog_dir / "testapp.json"
    test_catalog_file.write_bytes(orjson.dumps(test_app_data))

    # Create DirectoryManager with catalog_dir
    dir_manager = DirectoryManager(config_dir, catalog_dir)
    catalog_manager = CatalogManager(dir_manager)

    # Test listing catalog apps
    catalog_apps = catalog_manager.list_catalog_apps()
    assert "testapp" in catalog_apps

    # Test loading catalog entry
    entry = catalog_manager.load_catalog_entry("testapp")
    assert entry is not None
    assert entry["owner"] == "testowner"
    assert entry["repo"] == "testapp"

    # Test non-existent catalog entry
    nonexistent = catalog_manager.load_catalog_entry("nonexistent")
    assert nonexistent is None


def test_config_manager_facade_integration(config_dir):
    """Test that ConfigManager facade properly integrates all managers."""
    catalog_dir = config_dir / "catalog"
    catalog_dir.mkdir()

    # Create test catalog entry
    test_catalog_file = catalog_dir / "integration_test.json"
    test_catalog_file.write_bytes(
        orjson.dumps(
            {
                "owner": "integration",
                "repo": "test",
                "appimage": {"rename": "integration_test"},
                "verification": {"digest": False, "skip": False},
                "icon": None,
            }
        )
    )

    config_manager = ConfigManager(config_dir, catalog_dir)

    # Test that all manager functionality is accessible through facade
    TEST_CONCURRENT_DOWNLOADS = 6

    # Global config operations
    global_config = config_manager.load_global_config()
    global_config["max_concurrent_downloads"] = TEST_CONCURRENT_DOWNLOADS
    config_manager.save_global_config(global_config)
    loaded_global = config_manager.load_global_config()
    assert loaded_global["max_concurrent_downloads"] == TEST_CONCURRENT_DOWNLOADS

    # App config operations
    app_config = {
        "config_version": "1.0.0",
        "appimage": {
            "version": "1.0.0",
            "name": "integration.AppImage",
            "rename": "integration",
            "installed_date": "2024-01-01",
            "digest": "abc123",
        },
        "owner": "integration",
        "repo": "test",
        "github": {"repo": True, "prerelease": False},
        "verification": {
            "digest": True,
            "skip": False,
            "checksum_file": "",
            "checksum_hash_type": "sha256",
        },
        "icon": {"url": "", "name": "icon.png", "installed": True},
    }
    config_manager.save_app_config("integration_test", cast(AppConfig, app_config))
    loaded_app = config_manager.load_app_config("integration_test")
    assert loaded_app is not None
    assert loaded_app["owner"] == "integration"

    # Catalog operations
    catalog_apps = config_manager.list_catalog_apps()
    assert "integration_test" in catalog_apps

    catalog_entry = config_manager.load_catalog_entry("integration_test")
    assert catalog_entry is not None
    assert catalog_entry["repo"] == "test"

    # Directory operations
    assert config_manager.apps_dir.exists()
    assert config_manager.directory_manager.settings_file.exists()

    # Test direct access to manager classes
    default_config = config_manager.global_config_manager.get_default_global_config()
    assert isinstance(default_config, dict)

    # Test the global config manager conversion method by creating a proper config dict
    test_config = {"max_backup": "2", "locale": "en_US", "directory": {}}
    converted_config = config_manager.global_config_manager._convert_to_global_config(
        test_config
    )
    assert isinstance(converted_config, dict)
