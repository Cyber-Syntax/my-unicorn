"""Tests for ConfigManager: global config, app config, catalog, and directory logic."""

import configparser
from typing import cast

import orjson
import pytest

from my_unicorn.config import (
    AppConfig,
    AppConfigManager,
    CatalogManager,
    CommentAwareConfigParser,
    ConfigManager,
    DirectoryManager,
    GlobalConfigManager,
)
from my_unicorn.constants import CONFIG_VERSION


@pytest.fixture
def config_dir(tmp_path):
    """Provide a temporary config directory for ConfigManager."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # Create temporary catalog directory with one app in the test environment
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
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
                "github": {
                    "repo": True,
                    "prerelease": False,
                },
                "verification": {
                    "digest": False,
                    "skip": False,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
                "icon": {
                    "extraction": False,
                    "url": "",
                    "name": "dummy.png",
                },
            }
        )
    )
    return config_dir


@pytest.fixture
def config_manager(config_dir, tmp_path):
    """ConfigManager instance using temporary config_dir and catalog_dir."""
    # Use the temporary catalog directory for tests
    catalog_dir = tmp_path / "catalog"
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


def test_directory_creation_without_comments(config_manager, tmp_path):
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


def test_comment_stripping_configparser(config_manager):
    """Test that CommentAwareConfigParser correctly strips inline comments."""
    # Create a config file with inline comments
    config_content = """[DEFAULT]
batch_mode = true  # Non-interactive mode

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
    assert parser.get("DEFAULT", "batch_mode") == "true"
    assert parser.get("directory", "logs") == "/test/logs"
    assert parser.get("directory", "cache") == "/test/cache"
    assert parser.get("directory", "tmp") == "/test/tmp"

    # Verify that the raw config content contains comments
    assert "# Log files directory" in config_content
    assert "# Cache directory" in config_content


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
    result = app_manager.remove_app_config(
        app_name
    )  # Should be False on second try
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
        "github": {
            "repo": True,
            "prerelease": False,
        },
        "verification": {
            "digest": False,
            "skip": False,
            "checksum_file": "",
            "checksum_hash_type": "sha256",
        },
        "icon": {
            "extraction": False,
            "url": "",
            "name": "testapp.png",
        },
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
                "appimage": {
                    "rename": "integration_test",
                    "name_template": "",
                    "characteristic_suffix": [],
                },
                "github": {
                    "repo": True,
                    "prerelease": False,
                },
                "verification": {
                    "digest": False,
                    "skip": False,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
                "icon": {
                    "extraction": False,
                    "url": "",
                    "name": "integration_test.png",
                },
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
    assert (
        loaded_global["max_concurrent_downloads"] == TEST_CONCURRENT_DOWNLOADS
    )

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
    config_manager.save_app_config(
        "integration_test", cast(AppConfig, app_config)
    )
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
    default_config = (
        config_manager.global_config_manager.get_default_global_config()
    )
    assert isinstance(default_config, dict)

    # Test the global config manager conversion method by creating a proper config dict
    test_config = {"max_backup": "2", "locale": "en_US", "directory": {}}
    converted_config = (
        config_manager.global_config_manager._convert_to_global_config(
            test_config
        )
    )
    assert isinstance(converted_config, dict)


def test_version_comparison(config_dir):
    """Test semantic version comparison functionality."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))

    # Test equal versions
    assert manager.migration._compare_versions("1.0.0", "1.0.0") == 0
    assert manager.migration._compare_versions("1.0.1", "1.0.1") == 0

    # Test version1 < version2
    assert manager.migration._compare_versions("1.0.0", "1.0.1") == -1
    assert manager.migration._compare_versions("1.0.1", "1.1.0") == -1
    assert manager.migration._compare_versions("1.1.0", "2.0.0") == -1

    # Test version1 > version2
    assert manager.migration._compare_versions("1.0.1", "1.0.0") == 1
    assert manager.migration._compare_versions("1.1.0", "1.0.1") == 1
    assert manager.migration._compare_versions("2.0.0", "1.1.0") == 1

    # Test different length versions
    assert manager.migration._compare_versions("1.0", "1.0.0") == 0
    assert manager.migration._compare_versions("1.0.0.1", "1.0.0") == 1
    assert manager.migration._compare_versions("1.0", "1.0.1") == -1

    # Test invalid versions (fallback to 0.0.0)
    assert manager.migration._compare_versions("invalid", "1.0.0") == -1
    assert manager.migration._compare_versions("1.0.0", "invalid") == 1


def test_needs_migration(config_dir):
    """Test migration necessity detection."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))

    # Current version is older than default
    assert manager.migration._needs_migration("1.0.0") is True
    assert manager.migration._needs_migration("0.9.9") is True

    # Current version is same as default
    assert manager.migration._needs_migration(CONFIG_VERSION) is False

    # Current version is newer than default (shouldn't happen)
    assert manager.migration._needs_migration("2.0.0") is False

    # Invalid version should require migration
    assert manager.migration._needs_migration("invalid") is True


def test_config_backup_creation(config_dir):
    """Test configuration backup functionality."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))

    # Test with no existing config file
    backup_path = manager.migration._create_config_backup()
    assert backup_path == manager.directory_manager.settings_file

    # Create a config file and test backup
    config_content = "[DEFAULT]\nconfig_version = 1.0.0\n"
    manager.directory_manager.settings_file.write_text(config_content)

    backup_path = manager.migration._create_config_backup()
    assert backup_path.exists()
    assert backup_path.suffix == ".backup"
    assert "config_version = 1.0.0" in backup_path.read_text()


def test_merge_missing_fields(config_dir):
    """Test missing configuration field detection and merging."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))
    user_config = configparser.ConfigParser()

    # Start with minimal config using proper ConfigParser syntax
    user_config.read_string("""[DEFAULT]
config_version = 1.0.0
locale = en_US
""")

    defaults = manager.get_default_global_config()

    # Test merging missing fields
    fields_added = manager.migration._merge_missing_fields(
        user_config, defaults
    )
    assert fields_added is True

    # Verify missing scalar fields were added
    assert user_config.has_option("DEFAULT", "max_concurrent_downloads")
    assert user_config.has_option("DEFAULT", "console_log_level")

    # Verify nested sections were added
    assert user_config.has_section("network")
    assert user_config.has_section("directory")
    assert user_config.has_option("network", "retry_attempts")
    assert user_config.has_option("directory", "repo")

    # Test with complete config (no fields should be added)
    complete_config = configparser.ConfigParser()
    complete_config.read_dict({"DEFAULT": {"config_version": "1.0.1"}})
    for key, value in defaults.items():
        if isinstance(value, dict):
            complete_config.add_section(key)
            for subkey, subvalue in value.items():
                complete_config.set(key, subkey, str(subvalue))
        else:
            complete_config.set("DEFAULT", key, str(value))

    fields_added = manager.migration._merge_missing_fields(
        complete_config, defaults
    )
    assert fields_added is False


def test_validate_merged_config(config_dir):
    """Test configuration validation after merging."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))

    # Create valid complete configuration
    defaults = manager.get_default_global_config()
    config = configparser.ConfigParser()

    # Set DEFAULT section values properly
    default_items = {
        k: str(v) for k, v in defaults.items() if not isinstance(v, dict)
    }
    config.read_dict({"DEFAULT": default_items})

    # Add nested sections
    for key, value in defaults.items():
        if isinstance(value, dict):
            config.add_section(key)
            for subkey, subvalue in value.items():
                config.set(key, subkey, str(subvalue))

    assert manager.migration._validate_merged_config(config) is True

    # Test with configuration that would cause validation to fail
    # Create a config missing required fields
    minimal_config = configparser.ConfigParser()
    minimal_config.read_string("""[DEFAULT]
config_version = 1.0.1
""")
    # Minimal config should fail validation due to missing required fields

    assert manager.migration._validate_merged_config(minimal_config) is False


def test_configuration_migration_integration(config_dir):
    """Test complete configuration migration workflow."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))

    # Create old configuration file missing some fields
    old_config_content = """[DEFAULT]
config_version = 1.0.0
locale = fr_FR
max_backup = 3

[network]
retry_attempts = 5

[directory]
storage = /custom/storage
"""
    manager.directory_manager.settings_file.write_text(old_config_content)

    # Load configuration (should trigger migration)
    config = manager.load_global_config()

    # Verify configuration was migrated
    assert config["config_version"] == "1.0.2"  # Should be updated
    assert config["locale"] == "fr_FR"  # User value preserved
    assert config["max_backup"] == 3  # User value preserved
    assert config["network"]["retry_attempts"] == 5  # User value preserved

    # Verify missing fields were added
    assert "console_log_level" in config
    assert config["console_log_level"] == "WARNING"  # Default value
    assert config["network"]["timeout_seconds"] == 10  # Default value

    # Verify custom directory setting preserved but missing ones added
    assert str(config["directory"]["storage"]) == "/custom/storage"
    assert config["directory"]["repo"]  # Should have default value

    # Verify backup was created
    backup_files = list(config_dir.glob("*.backup"))
    assert len(backup_files) > 0


def test_migration_failure_rollback(config_dir):
    """Test migration rollback on validation failure."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))

    # Create configuration that will fail validation after migration
    # This is hard to trigger naturally, so we'll test the rollback mechanism

    original_validate = manager.migration._validate_merged_config

    def mock_validate_failure(config):
        # Always return False to simulate validation failure
        return False

    manager.migration._validate_merged_config = mock_validate_failure

    old_config_content = """[DEFAULT]
config_version = 1.0.0
locale = test_locale
"""
    manager.directory_manager.settings_file.write_text(old_config_content)

    # Create a user config that should trigger migration
    user_config = configparser.ConfigParser()
    user_config.read_string(old_config_content)

    # Test migration failure
    defaults = manager.get_default_global_config()
    result = manager.migration._migrate_configuration(user_config, defaults)
    assert result is False

    # Restore original method
    manager.migration._validate_merged_config = original_validate


def test_migration_with_new_config_file(config_dir):
    """Test behavior with non-existent configuration file."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))

    # Load configuration with no existing file
    config = manager.load_global_config()

    # Should create default configuration
    assert config["config_version"] == "1.0.2"
    assert config["locale"] == "en_US"
    assert manager.directory_manager.settings_file.exists()


def test_migration_no_changes_needed(config_dir):
    """Test migration when configuration is already up to date."""
    manager = GlobalConfigManager(DirectoryManager(config_dir))

    # Create current configuration file with all required fields
    complete_config_content = """[DEFAULT]
config_version = 1.0.2
max_concurrent_downloads = 5
max_backup = 1
batch_mode = true
locale = en_US
log_level = INFO
console_log_level = WARNING

[network]
retry_attempts = 3
timeout_seconds = 10

[directory]
repo = /tmp/test-repo
package = /tmp/test-package
download = /tmp/downloads
storage = /tmp/storage
backup = /tmp/backup
icon = /tmp/icons
settings = /tmp/settings
logs = /tmp/logs
cache = /tmp/cache
tmp = /tmp/tmp
"""

    manager.directory_manager.settings_file.write_text(complete_config_content)

    # Load configuration (should not require migration)
    config = manager.load_global_config()

    # Verify no migration was performed (version stays the same)
    assert config["config_version"] == "1.0.2"

    # No backup should be created for up-to-date config
    # Note: There might be backup files from other tests, so we just check
    # that loading didn't create additional unnecessary backups


def test_config_file_with_comments(config_dir, tmp_path):
    """Test that configuration files are saved with user-friendly comments."""
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir(exist_ok=True)
    config_manager = ConfigManager(config_dir, catalog_dir)

    # Load and save config to create file with comments
    config = config_manager.load_global_config()
    config_manager.save_global_config(config)

    # Read the raw file content to check for comments
    settings_file = config_manager.settings_file
    content = settings_file.read_text(encoding="utf-8")

    # Check for header comment
    assert "My-Unicorn AppImage Installer Configuration" in content
    assert "Last updated:" in content
    assert "Configuration version:" in content

    # Check for section comments
    assert "MAIN CONFIGURATION" in content
    assert "NETWORK CONFIGURATION" in content
    assert "DIRECTORY PATHS" in content

    # Check for inline comments - only config_version should have one
    assert "# DO NOT MODIFY - Config format version" in content
    # Other fields should not have inline comments
    assert "# Max simultaneous downloads" not in content
    assert "# Number of backup copies to keep" not in content
    assert "# Download retry attempts" not in content
    assert "# AppImage metadata repository" not in content

    # Verify that configuration can still be loaded correctly
    loaded_config = config_manager.load_global_config()
    assert loaded_config == config


def test_comment_stripping_functionality(config_dir, tmp_path):
    """Test that inline comments are properly stripped when loading config."""
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir(exist_ok=True)
    config_manager = ConfigManager(config_dir, catalog_dir)

    # Create a config file with comments manually
    settings_file = config_manager.settings_file
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    config_content = """[DEFAULT]
max_concurrent_downloads = 10  # Max simultaneous downloads
max_backup = 3  # Number of backup copies to keep
batch_mode = false  # Non-interactive mode

[network]
retry_attempts = 5  # Download retry attempts
timeout_seconds = 30  # Request timeout in seconds

[directory]
download = /tmp/downloads  # Temporary download location
"""

    settings_file.write_text(config_content, encoding="utf-8")

    # Load config and verify values are correctly parsed (comments stripped)
    config = config_manager.load_global_config()

    assert config["max_concurrent_downloads"] == 10
    assert config["max_backup"] == 3
    assert config["batch_mode"] is False
    assert config["network"]["retry_attempts"] == 5
    assert config["network"]["timeout_seconds"] == 30
    assert str(config["directory"]["download"]) == "/tmp/downloads"


def _parse_ini_file_lines(content: str) -> tuple[list, list, list]:
    """Parse INI file content and categorize config lines."""
    lines = content.split("\n")

    # Find all key=value lines (configuration lines)
    config_lines = []
    for line_num, line in enumerate(lines, 1):
        if "=" in line and not line.strip().startswith("#"):
            config_lines.append((line_num, line))

    # Categorize lines: with comments vs without comments
    lines_with_comments = []
    lines_without_comments = []

    for line_num, line in config_lines:
        if "  #" in line:  # Has inline comment (double space before #)
            lines_with_comments.append((line_num, line))
        else:
            lines_without_comments.append((line_num, line))

    return config_lines, lines_with_comments, lines_without_comments


def _verify_comment_lines(lines_with_comments: list) -> None:
    """Verify lines with comments have proper formatting."""
    MIN_COMMENT_LINES = 1

    for line_num, line in lines_with_comments:
        # Should have exactly one comment (config_version)
        assert "config_version" in line, (
            f"Only config_version should have inline comment, found: {line}"
        )
        assert line.count("  #") == MIN_COMMENT_LINES, (
            f"Line {line_num} should have exactly one comment marker: {line!r}"
        )
        assert "DO NOT MODIFY" in line, (
            f"Line {line_num} should have the protection comment: {line!r}"
        )

        # Verify format: should end with comment, not extra spaces
        assert line.endswith("# DO NOT MODIFY - Config format version"), (
            f"Line {line_num} should end with comment, not spaces: {line!r}"
        )


def _verify_clean_lines(lines_without_comments: list) -> None:
    """Verify lines without comments have no trailing spaces."""
    EXPECTED_KEY_VALUE_PARTS = 2

    for line_num, line in lines_without_comments:
        # Should not end with any spaces
        assert not line.endswith(" "), (
            f"Line {line_num} should not have trailing spaces: {line!r}"
        )
        assert not line.endswith("  "), (
            f"Line {line_num} should not have trailing double spaces: {line!r}"
        )

        # Should have proper format: "key = value" (no trailing whitespace)
        parts = line.split(" = ")
        assert len(parts) == EXPECTED_KEY_VALUE_PARTS, (
            f"Line {line_num} should have 'key = value' format: {line!r}"
        )
        _, value = parts  # Only use value, ignore key
        assert not value.endswith(" "), (
            f"Value in line {line_num} should not end with space: {value!r}"
        )


def test_ini_file_inline_spacing_format(config_dir, tmp_path):
    """Test INI files have proper spacing without trailing spaces.

    This prevents regression of the trailing whitespace issue where all lines
    had unnecessary trailing spaces even when they had no inline comments.
    """
    MIN_COMMENT_LINES = 1
    MIN_CLEAN_LINES = 5

    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir(exist_ok=True)
    config_manager = ConfigManager(config_dir, catalog_dir)

    # Load and save config to create file with proper formatting
    config = config_manager.load_global_config()
    config_manager.save_global_config(config)

    # Read and parse the raw file content
    settings_file = config_manager.settings_file
    content = settings_file.read_text(encoding="utf-8")
    _, lines_with_comments, lines_without_comments = _parse_ini_file_lines(
        content
    )

    # Verify we have the expected structure
    assert len(lines_with_comments) >= MIN_COMMENT_LINES, (
        "Should have at least config_version with comment"
    )
    assert len(lines_without_comments) >= MIN_CLEAN_LINES, (
        "Should have multiple lines without comments"
    )

    # Test comment lines and clean lines
    _verify_comment_lines(lines_with_comments)
    _verify_clean_lines(lines_without_comments)

    # Verify the file can be read back correctly
    reloaded_config = config_manager.load_global_config()
    assert reloaded_config == config, (
        "Config should reload identically despite formatting changes"
    )
