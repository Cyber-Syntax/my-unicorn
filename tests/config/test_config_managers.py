"""Tests for ConfigManager facade and specialized manager classes."""

import configparser
from pathlib import Path

import orjson
import pytest

from my_unicorn.config import (
    AppConfigManager,
    CatalogLoader,
    CommentAwareConfigParser,
    ConfigManager,
    GlobalConfigManager,
)


def test_load_and_save_global_config(config_manager: ConfigManager) -> None:
    """Test loading and saving global config."""
    config = config_manager.load_global_config()
    assert isinstance(config, dict)
    test_max_backup = 7
    config["max_backup"] = test_max_backup
    config_manager.save_global_config(config)
    loaded = config_manager.load_global_config()
    assert loaded["max_backup"] == test_max_backup


def test_load_app_config_and_migration(config_manager: ConfigManager) -> None:
    """Test saving and loading app config with v2.0.0 format."""
    app_name = "testapp"
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "testapp",
        "state": {
            "version": "1.0.0",
            "installed_date": "2025-01-01T00:00:00",
            "installed_path": "/path/to/app.AppImage",
            "verification": {
                "passed": True,
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                    }
                ],
            },
            "icon": {"installed": False, "method": "extraction", "path": ""},
        },
    }
    config_manager.save_app_config(app_name, app_config)
    loaded = config_manager.load_app_config(app_name)

    # Should load v2.0.0 config successfully
    assert loaded["config_version"] == "2.0.0"
    assert "state" in loaded
    assert loaded["state"]["verification"]["passed"] is True


def test_remove_app_config(config_manager: ConfigManager) -> None:
    """Test removing app config file."""
    app_name = "toremove"
    app_config = {
        "config_version": "1.0.0",
        "source": "catalog",
        "appimage": {
            "version": "1.0",
            "name": "toremove.AppImage",
            "rename": "toremove",
            "name_template": "",
            "characteristic_suffix": [],
            "installed_date": "2024-01-01T12:00:00",
            "digest": "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
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


def test_list_installed_apps(config_manager: ConfigManager) -> None:
    """Test listing installed apps."""
    app_names = ["app1", "app2"]
    for name in app_names:
        config_manager.save_app_config(
            name,
            {
                "config_version": "1.0.0",
                "source": "catalog",
                "appimage": {
                    "version": "1.0",
                    "name": f"{name}.AppImage",
                    "rename": name,
                    "name_template": "",
                    "characteristic_suffix": [],
                    "installed_date": "2024-01-01T12:00:00",
                    "digest": (
                        "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
                    ),
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


def test_list_catalog_apps(config_manager: ConfigManager) -> None:
    """Test listing catalog apps."""
    catalog_apps = config_manager.list_catalog_apps()
    assert "dummyapp" in catalog_apps


def test_load_catalog_entry(config_manager: ConfigManager) -> None:
    """Test loading catalog entry."""
    entry = config_manager.load_catalog("dummyapp")
    assert entry is not None
    assert entry["source"]["owner"] == "dummy"
    assert entry["source"]["repo"] == "dummyrepo"


def test_ensure_directories_from_config(
    config_manager: ConfigManager, tmp_path: Path
) -> None:
    """Test ensure_directories_from_config creates directories."""
    dirs = {
        "download": tmp_path / "download",
        "storage": tmp_path / "storage",
        "backup": tmp_path / "backup",
        "icon": tmp_path / "icon",
        "settings": tmp_path / "settings",
        "logs": tmp_path / "logs",
        "cache": tmp_path / "cache",
    }
    config = {
        "config_version": "1.1.0",
        "max_concurrent_downloads": 5,
        "max_backup": 1,
        "log_level": "INFO",
        "console_log_level": "INFO",
        "network": {"retry_attempts": 3, "timeout_seconds": 10},
        "directory": dirs,
    }
    config_manager.ensure_directories_from_config(config)
    for d in dirs.values():
        assert d.exists()


def test_directory_creation_without_comments(
    config_manager: ConfigManager, tmp_path: Path
) -> None:
    """Test that directories are created without inline comments in names.

    This test prevents regression of the bug where directories were created
    with comment text in their names (e.g., 'logs  # Log files directory').
    """
    # Load config (this will create and save a default config with comments)
    config_manager.load_global_config()

    # Verify the config file was saved correctly
    config_content = config_manager.settings_file.read_text()
    assert "logs = " in config_content
    assert "cache = " in config_content
    # Only config_version should have inline comment
    assert "# DO NOT MODIFY - Config format version" in config_content

    # Reload config to simulate the full save/load cycle
    config_reloaded = config_manager.load_global_config()

    # Verify that directory paths are clean (no comments)
    for key, path in config_reloaded["directory"].items():
        path_str = str(path)
        assert "  #" not in path_str, (
            f"Directory path '{key}' contains comment: {path_str}"
        )
        assert "# " not in path_str, (
            f"Directory path '{key}' contains comment: {path_str}"
        )

    # Create directories using the config
    config_manager.ensure_directories_from_config(config_reloaded)

    # Verify that actual directories created do not have comments in names
    config_dir = config_manager.config_dir
    if config_dir.exists():
        for item in config_dir.iterdir():
            if item.is_dir():
                dir_name = item.name
                assert "  #" not in dir_name, (
                    f"Directory created with comment in name: '{dir_name}'"
                )
                assert "# " not in dir_name, (
                    f"Directory created with comment in name: '{dir_name}'"
                )

    # Test with specific directory paths that should be created
    test_dirs = ["logs", "cache", "tmp"]
    for dir_name in test_dirs:
        expected_path = config_dir / dir_name
        if expected_path.exists():
            expected_name = expected_path.name
            assert expected_name == dir_name, (
                f"Expected '{dir_name}', got '{expected_name}'"
            )
            # Ensure no directory with comments exists
            comment_variations = [
                f"{dir_name}  # Log files directory",
                f"{dir_name}  # Cache directory",
                f"{dir_name}  # Temporary files directory",
            ]
            for bad_name in comment_variations:
                bad_path = config_dir / bad_name
                assert not bad_path.exists(), (
                    f"Found directory with comment in name: '{bad_name}'"
                )


def test_comment_stripping_configparser(config_manager: ConfigManager) -> None:
    """Test that CommentAwareConfigParser correctly strips inline comments."""
    # Create a config file with inline comments
    config_content = """[DEFAULT]

[directory]
logs = /test/logs  # Log files directory
cache = /test/cache  # Cache directory
tmp = /test/tmp  # Temporary files directory
"""

    # Write the config content to a temporary file
    test_config_file = config_manager.config_dir / "test_config.conf"
    test_config_file.write_text(config_content)

    # Load with CommentAwareConfigParser
    parser = CommentAwareConfigParser()
    parser.read(test_config_file)

    # Verify that comments are stripped from values
    assert parser.get("directory", "logs") == "/test/logs"
    assert parser.get("directory", "cache") == "/test/cache"
    assert parser.get("directory", "tmp") == "/test/tmp"

    # Verify that the raw config content contains comments
    assert "# Log files directory" in config_content
    assert "# Cache directory" in config_content


def test_global_config_manager(config_dir: Path) -> None:
    """Test GlobalConfigManager functionality."""
    global_manager = GlobalConfigManager(config_dir)

    # Test loading default config
    config = global_manager.load_global_config()
    assert isinstance(config, dict)
    assert "config_version" in config
    assert "max_concurrent_downloads" in config

    # Test saving and loading
    test_max_downloads = 8
    config["max_concurrent_downloads"] = test_max_downloads
    global_manager.save_global_config(config)
    loaded = global_manager.load_global_config()
    assert loaded["max_concurrent_downloads"] == test_max_downloads

    # Test get default global config
    default = global_manager.get_default_global_config()
    assert isinstance(default, dict)

    # Test convert to global config (with compatible input type)
    raw_config = configparser.ConfigParser()
    raw_config.add_section("settings")
    raw_config.set("settings", "max_backup", "3")
    converted = global_manager._convert_to_global_config(raw_config)
    assert "directory" in converted
    assert "network" in converted


def test_app_config_manager(config_dir: Path) -> None:
    """Test AppConfigManager functionality."""
    apps_dir = config_dir / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    app_manager = AppConfigManager(apps_dir)

    # Test saving and loading app config
    app_name = "testapp"
    test_version = "2.0.0"
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "testapp",
        "state": {
            "version": test_version,
            "installed_date": "2024-01-01T12:00:00",
            "installed_path": "",
            "verification": {
                "passed": True,
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
                        "computed": "abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
                        "source": "github_api",
                    }
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "",
            },
        },
    }

    app_manager.save_app_config(app_name, app_config)
    loaded = app_manager.load_app_config(app_name)
    assert loaded is not None
    # V2.0.0 format with state
    assert loaded["config_version"] == "2.0.0"
    assert loaded["state"]["version"] == test_version

    # Test listing apps
    installed = app_manager.list_installed_apps()
    assert app_name in installed

    # Test removing app config
    result = app_manager.remove_app_config(app_name)
    assert result is True
    result = app_manager.remove_app_config(
        app_name
    )  # Should be False on second try
    assert result is False

    # Test non-existent app
    nonexistent = app_manager.load_app_config("nonexistent")
    assert nonexistent is None


def test_catalog_manager(config_dir: Path) -> None:
    """Test CatalogLoader functionality."""
    # Create catalog directory with test data
    catalog_dir = config_dir / "catalog"
    catalog_dir.mkdir()

    test_app_data = {
        "config_version": "2.0.0",
        "metadata": {
            "name": "testapp",
            "display_name": "Test App",
            "description": "",
        },
        "source": {
            "type": "github",
            "owner": "testowner",
            "repo": "testapp",
            "prerelease": False,
        },
        "appimage": {
            "naming": {
                "template": "",
                "target_name": "testapp",
                "architectures": ["amd64"],
            }
        },
        "verification": {"method": "digest"},
        "icon": {"method": "extraction", "filename": "testapp.png"},
    }

    test_catalog_file = catalog_dir / "testapp.json"
    test_catalog_file.write_bytes(orjson.dumps(test_app_data))

    # Create CatalogLoader with catalog_dir
    catalog_loader = CatalogLoader(catalog_dir)

    # Test listing catalog apps
    catalog_apps = catalog_loader.list_apps()
    assert "testapp" in catalog_apps

    # Test loading catalog entry
    entry = catalog_loader.load("testapp")
    assert entry is not None
    assert entry["source"]["owner"] == "testowner"
    assert entry["source"]["repo"] == "testapp"

    # Test non-existent catalog entry
    with pytest.raises(FileNotFoundError):
        catalog_loader.load("nonexistent")


def test_config_manager_facade_integration(config_dir: Path) -> None:
    """Test that ConfigManager facade properly integrates all managers."""
    catalog_dir = config_dir / "catalog"
    catalog_dir.mkdir()

    # Create test catalog entry
    test_catalog_file = catalog_dir / "integration_test.json"
    test_catalog_file.write_bytes(
        orjson.dumps(
            {
                "config_version": "2.0.0",
                "metadata": {
                    "name": "integration_test",
                    "display_name": "Integration Test",
                    "description": "",
                },
                "source": {
                    "type": "github",
                    "owner": "integration",
                    "repo": "test",
                    "prerelease": False,
                },
                "appimage": {
                    "naming": {
                        "template": "",
                        "target_name": "integration_test",
                        "architectures": ["amd64", "x86_64"],
                    }
                },
                "verification": {"method": "digest"},
                "icon": {
                    "method": "extraction",
                    "filename": "integration_test.png",
                },
            }
        )
    )

    config_manager = ConfigManager(config_dir, catalog_dir)

    # Test that all manager functionality is accessible through facade
    test_concurrent_downloads = 6

    # Global config operations
    global_config = config_manager.load_global_config()
    global_config["max_concurrent_downloads"] = test_concurrent_downloads
    config_manager.save_global_config(global_config)
    loaded_global = config_manager.load_global_config()
    assert (
        loaded_global["max_concurrent_downloads"] == test_concurrent_downloads
    )

    # App config operations
    app_config = {
        "config_version": "2.0.0",
        "source": "catalog",
        "catalog_ref": "integration_test",
        "state": {
            "version": "1.0.0",
            "installed_date": "2024-01-01T12:00:00",
            "installed_path": "",
            "verification": {
                "passed": True,
                "methods": [
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": "abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
                        "computed": "abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
                        "source": "github_api",
                    }
                ],
            },
            "icon": {
                "installed": True,
                "method": "extraction",
                "path": "",
            },
        },
    }
    config_manager.save_app_config("integration_test", app_config)
    loaded_app = config_manager.load_app_config("integration_test")
    assert loaded_app is not None
    # After migration to v2.0.0, structure changes
    assert loaded_app["config_version"] == "2.0.0"
    assert loaded_app["state"]["version"] == "1.0.0"

    # Catalog operations
    catalog_apps = config_manager.list_catalog_apps()
    assert "integration_test" in catalog_apps

    catalog_entry = config_manager.load_catalog("integration_test")
    assert catalog_entry is not None
    assert catalog_entry["source"]["repo"] == "test"

    # Directory operations
    assert config_manager.apps_dir.exists()
    assert config_manager.global_config_manager.settings_file.exists()

    # Test direct access to manager classes
    default_config = (
        config_manager.global_config_manager.get_default_global_config()
    )
    assert isinstance(default_config, dict)

    # Test the global config manager conversion method by creating a proper config dict
    test_config = {"max_backup": "2", "directory": {}}
    converted_config = (
        config_manager.global_config_manager._convert_to_global_config(
            test_config
        )
    )
    assert isinstance(converted_config, dict)
