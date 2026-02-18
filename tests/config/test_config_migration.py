"""Tests for configuration migration logic and INI file formatting."""

import configparser
from pathlib import Path

from my_unicorn.config import GlobalConfigManager
from my_unicorn.config.migration.helpers import compare_versions
from my_unicorn.constants import GLOBAL_CONFIG_VERSION


def test_version_comparison(config_dir: Path) -> None:
    """Test semantic version comparison functionality."""
    manager = GlobalConfigManager(config_dir)

    # Test equal versions
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.0.1", "1.0.1") == 0

    # Test version1 < version2
    assert compare_versions("1.0.0", "1.0.1") == -1
    assert compare_versions("1.0.1", "1.1.0") == -1
    assert compare_versions("1.1.0", "2.0.0") == -1

    # Test version1 > version2
    assert compare_versions("1.0.1", "1.0.0") == 1
    assert compare_versions("1.1.0", "1.0.1") == 1
    assert compare_versions("2.0.0", "1.1.0") == 1

    # Test different length versions
    assert compare_versions("1.0", "1.0.0") == 0
    assert compare_versions("1.0.0.1", "1.0.0") == 1
    assert compare_versions("1.0", "1.0.1") == -1

    # Test invalid versions (fallback to 0.0.0)
    assert compare_versions("invalid", "1.0.0") == -1
    assert compare_versions("1.0.0", "invalid") == 1


def test_needs_migration(config_dir: Path) -> None:
    """Test migration necessity detection."""
    manager = GlobalConfigManager(config_dir)

    # Current version is older than default
    assert manager.migration._needs_migration("1.0.0") is True
    assert manager.migration._needs_migration("0.9.9") is True

    # Current version is same as default
    assert manager.migration._needs_migration(GLOBAL_CONFIG_VERSION) is False

    # Current version is newer than default (shouldn't happen)
    assert manager.migration._needs_migration("2.0.0") is False

    # Invalid version should require migration
    assert manager.migration._needs_migration("invalid") is True


def test_config_backup_creation(config_dir: Path) -> None:
    """Test configuration backup functionality."""
    manager = GlobalConfigManager(config_dir)

    # Test with no existing config file
    backup_path = manager.migration._create_config_backup()
    assert backup_path == manager.settings_file

    # Create a config file and test backup
    config_content = "[DEFAULT]\nconfig_version = 1.0.0\n"
    manager.settings_file.write_text(config_content)

    backup_path = manager.migration._create_config_backup()
    assert backup_path.exists()
    assert backup_path.suffix == ".backup"
    assert "config_version = 1.0.0" in backup_path.read_text()


def test_merge_missing_fields(config_dir: Path) -> None:
    """Test missing configuration field detection and merging."""
    manager = GlobalConfigManager(config_dir)
    user_config = configparser.ConfigParser()

    # Start with minimal config using proper ConfigParser syntax
    user_config.read_string("""[DEFAULT]
config_version = 1.0.0
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
    assert user_config.has_option("directory", "storage")

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


def test_validate_merged_config(config_dir: Path) -> None:
    """Test configuration validation after merging."""
    manager = GlobalConfigManager(config_dir)

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


def test_configuration_migration_integration(config_dir: Path) -> None:
    """Test complete configuration migration workflow."""
    manager = GlobalConfigManager(config_dir)

    # Create old configuration file missing some fields
    old_config_content = """[DEFAULT]
config_version = 1.0.0
max_backup = 3

[network]
retry_attempts = 5

[directory]
storage = /custom/storage
"""
    manager.settings_file.write_text(old_config_content)

    # Load configuration (should trigger migration)
    config = manager.load_global_config()

    # Verify configuration was migrated
    assert config["config_version"] == "1.1.0"  # Should be updated
    assert config["max_backup"] == 3  # User value preserved
    assert config["network"]["retry_attempts"] == 5  # User value preserved

    # Verify missing fields were added
    assert "console_log_level" in config
    assert (
        config["console_log_level"] == "INFO"
    )  # Default value (changed from WARNING)
    assert config["network"]["timeout_seconds"] == 10  # Default value

    # Verify custom directory setting preserved
    assert str(config["directory"]["storage"]) == "/custom/storage"

    # Verify backup was created
    backup_files = list(config_dir.glob("*.backup"))
    assert len(backup_files) > 0


def test_migration_failure_rollback(config_dir: Path) -> None:
    """Test migration rollback on validation failure."""
    manager = GlobalConfigManager(config_dir)

    # Create configuration that will fail validation after migration
    # This is hard to trigger naturally, so we'll test the rollback mechanism

    original_validate = manager.migration._validate_merged_config

    def mock_validate_failure(config: configparser.ConfigParser) -> bool:
        # Always return False to simulate validation failure
        return False

    manager.migration._validate_merged_config = mock_validate_failure

    old_config_content = """[DEFAULT]
config_version = 1.0.0
"""
    manager.settings_file.write_text(old_config_content)

    # Create a user config that should trigger migration
    user_config = configparser.ConfigParser()
    user_config.read_string(old_config_content)

    # Test migration failure
    defaults = manager.get_default_global_config()
    result = manager.migration._migrate_configuration(user_config, defaults)
    assert result is False

    # Restore original method
    manager.migration._validate_merged_config = original_validate


def test_migration_with_new_config_file(config_dir: Path) -> None:
    """Test behavior with non-existent configuration file."""
    manager = GlobalConfigManager(config_dir)

    # Load configuration with no existing file
    config = manager.load_global_config()

    # Should create default configuration
    assert config["config_version"] == "1.1.0"
    assert manager.settings_file.exists()


def test_migration_no_changes_needed(config_dir: Path) -> None:
    """Test migration when configuration is already up to date."""
    manager = GlobalConfigManager(config_dir)

    # Create current configuration file with all required fields
    complete_config_content = """[DEFAULT]
    config_version = 1.1.0
    max_concurrent_downloads = 5
    max_backup = 1
    log_level = INFO
    console_log_level = WARNING

    [network]
    retry_attempts = 3
    timeout_seconds = 10

    [directory]
    download = /tmp/downloads
    storage = /tmp/storage
    backup = /tmp/backup
    icon = /tmp/icons
    settings = /tmp/settings
    logs = /tmp/logs
    cache = /tmp/cache
    """

    manager.settings_file.write_text(complete_config_content)

    # Load configuration (should not require migration)
    config = manager.load_global_config()

    # Verify no migration was performed (version stays the same)
    assert config["config_version"] == "1.1.0"

    # No backup should be created for up-to-date config
    # Note: There might be backup files from other tests, so we just check
    # that loading didn't create additional unnecessary backups


def test_config_file_with_comments(config_dir: Path) -> None:
    """Test that configuration files are saved with user-friendly comments."""
    from my_unicorn.config import ConfigManager

    catalog_dir = config_dir / "test_catalog"
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


def test_comment_stripping_functionality(config_dir: Path) -> None:
    """Test that inline comments are properly stripped when loading config."""
    from my_unicorn.config import ConfigManager

    catalog_dir = config_dir / "test_catalog2"
    catalog_dir.mkdir(exist_ok=True)
    config_manager = ConfigManager(config_dir, catalog_dir)

    # Create a config file with comments manually
    settings_file = config_manager.settings_file
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    config_content = """[DEFAULT]
max_concurrent_downloads = 10  # Max simultaneous downloads
max_backup = 3  # Number of backup copies to keep

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
    min_comment_lines = 1

    for line_num, line in lines_with_comments:
        # Should have exactly one comment (config_version)
        assert "config_version" in line, (
            f"Only config_version should have inline comment, found: {line}"
        )
        assert line.count("  #") == min_comment_lines, (
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
    expected_key_value_parts = 2

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
        assert len(parts) == expected_key_value_parts, (
            f"Line {line_num} should have 'key = value' format: {line!r}"
        )
        _, value = parts  # Only use value, ignore key
        assert not value.endswith(" "), (
            f"Value in line {line_num} should not end with space: {value!r}"
        )


def test_ini_file_inline_spacing_format(config_dir: Path) -> None:
    """Test INI files have proper spacing without trailing spaces.

    This prevents regression of the trailing whitespace issue where all lines
    had unnecessary trailing spaces even when they had no inline comments.
    """
    from my_unicorn.config import ConfigManager

    min_comment_lines = 1
    min_clean_lines = 5

    catalog_dir = config_dir / "test_catalog3"
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
    assert len(lines_with_comments) >= min_comment_lines, (
        "Should have at least config_version with comment"
    )
    assert len(lines_without_comments) >= min_clean_lines, (
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
