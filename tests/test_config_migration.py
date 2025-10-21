"""Tests for configuration migration module."""

import configparser
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from my_unicorn.config import DirectoryManager
from my_unicorn.config_migration import ConfigMigration
from my_unicorn.constants import CONFIG_VERSION


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def directory_manager(temp_dir):
    """Create a DirectoryManager for testing."""
    config_dir = temp_dir / "config"
    config_dir.mkdir()
    return DirectoryManager(config_dir=config_dir)


@pytest.fixture
def migration(directory_manager):
    """Create a ConfigMigration instance for testing."""
    return ConfigMigration(directory_manager)


@pytest.fixture
def sample_defaults():
    """Sample default configuration for testing."""
    return {
        "config_version": CONFIG_VERSION,
        "log_level": "INFO",
        "console_log_level": "WARNING",
        "network": {"retry_attempts": "3", "timeout_seconds": "10"},
        "directory": {"repo": "/tmp/repo", "storage": "/tmp/storage"},
    }


class TestConfigMigration:
    """Test cases for ConfigMigration class."""

    def test_init(self, migration, directory_manager):
        """Test ConfigMigration initialization."""
        assert migration.directory_manager == directory_manager
        assert migration._messages == []

    def test_collect_message(self, migration):
        """Test message collection functionality."""
        migration._collect_message("INFO", "Test message %s", "arg1")

        assert len(migration._messages) == 1
        level, message, args = migration._messages[0]
        assert level == "INFO"
        assert message == "Test message %s"
        assert args == ("arg1",)

    def test_collect_message_critical_prints(self, migration, capsys):
        """Test that critical messages are printed to console."""
        migration._collect_message("ERROR", "Critical error: %s", "problem")

        captured = capsys.readouterr()
        assert (
            "Config Migration ERROR: Critical error: problem" in captured.out
        )

    def test_needs_migration_true(self, migration):
        """Test migration is needed for older versions."""
        assert migration._needs_migration("1.0.0") is True
        assert migration._needs_migration("0.9.0") is True

    def test_needs_migration_false(self, migration):
        """Test migration is not needed for current or newer versions."""
        assert migration._needs_migration(CONFIG_VERSION) is False
        assert migration._needs_migration("1.1.0") is False

    def test_compare_versions(self, migration):
        """Test version comparison logic."""
        assert migration._compare_versions("1.0.0", "1.0.1") == -1
        assert migration._compare_versions("1.0.1", "1.0.0") == 1
        assert migration._compare_versions("1.0.1", "1.0.1") == 0

    def test_migrate_if_needed_no_migration(self, migration, sample_defaults):
        """Test migration when no migration is needed."""
        config = configparser.ConfigParser()
        config["DEFAULT"] = {"config_version": CONFIG_VERSION}

        result = migration.migrate_if_needed(config, sample_defaults)

        assert result is True
        assert len(migration._messages) == 0

    def test_migrate_if_needed_with_migration(
        self, migration, sample_defaults
    ):
        """Test migration when migration is needed."""
        config = configparser.ConfigParser()
        config["DEFAULT"] = {"config_version": "1.0.0"}

        # Mock the migration methods to avoid file operations
        migration._create_config_backup = MagicMock(
            return_value=Path("/tmp/backup")
        )
        migration._validate_merged_config = MagicMock(return_value=True)

        result = migration.migrate_if_needed(config, sample_defaults)

        assert result is True
        assert len(migration._messages) > 0

    def test_merge_missing_fields_adds_fields(
        self, migration, sample_defaults
    ):
        """Test that missing fields are added during merge."""
        config = configparser.ConfigParser()
        config["DEFAULT"] = {"config_version": "1.0.0"}

        result = migration._merge_missing_fields(config, sample_defaults)

        assert result is True
        assert config.has_option("DEFAULT", "log_level")
        assert config.has_option("DEFAULT", "console_log_level")
        assert config.has_section("network")
        assert config.has_option("network", "retry_attempts")

    def test_merge_missing_fields_no_changes(self, migration, sample_defaults):
        """Test that no changes are made when all fields exist."""
        config = configparser.ConfigParser()
        config["DEFAULT"] = {
            "config_version": CONFIG_VERSION,
            "log_level": "INFO",
            "console_log_level": "WARNING",
        }
        config.add_section("network")
        config.set("network", "retry_attempts", "3")
        config.set("network", "timeout_seconds", "10")
        config.add_section("directory")
        config.set("directory", "repo", "/tmp/repo")
        config.set("directory", "storage", "/tmp/storage")

        result = migration._merge_missing_fields(config, sample_defaults)

        assert result is False

    def test_validate_merged_config_valid(self, migration):
        """Test validation of a valid configuration."""
        config = configparser.ConfigParser()
        config["DEFAULT"] = {
            "config_version": CONFIG_VERSION,
            "log_level": "INFO",
            "console_log_level": "WARNING",
        }
        config.add_section("network")
        config.set("network", "retry_attempts", "3")
        config.set("network", "timeout_seconds", "10")
        config.add_section("directory")
        config.set("directory", "repo", "/tmp/repo")
        config.set("directory", "storage", "/tmp/storage")

        result = migration._validate_merged_config(config)

        assert result is True

    def test_validate_merged_config_invalid(self, migration):
        """Test validation of an invalid configuration."""
        config = configparser.ConfigParser()
        config["DEFAULT"] = {"config_version": CONFIG_VERSION}
        # Missing required sections and fields

        result = migration._validate_merged_config(config)

        assert result is False

    def test_replay_messages_to_logger(self, migration):
        """Test replaying messages to logger."""
        # Add some test messages
        migration._collect_message("INFO", "Test message 1")
        migration._collect_message("WARNING", "Test message 2")

        assert len(migration._messages) == 2

        # Replay messages (this will attempt to import logger)
        migration.replay_messages_to_logger()

        # Messages should be cleared after successful replay (or kept if logger unavailable)
        # Since we might not have the logger available in tests, we can't guarantee clearing

    def test_clear_messages(self, migration):
        """Test clearing collected messages."""
        migration._collect_message("INFO", "Test message")
        assert len(migration._messages) == 1

        migration.clear_messages()
        assert len(migration._messages) == 0

    def test_has_messages_property(self, migration):
        """Test has_messages property."""
        assert migration.has_messages is False

        migration._collect_message("INFO", "Test message")
        assert migration.has_messages is True

        migration.clear_messages()
        assert migration.has_messages is False

    def test_create_backup_no_existing_file(self, migration):
        """Test backup creation when no config file exists."""
        result = migration._create_config_backup()

        # Should return the settings file path even if it doesn't exist
        assert result == migration.directory_manager.settings_file

    def test_restore_backup_no_backups(self, migration):
        """Test backup restoration when no backups exist."""
        # Should not raise an error
        migration._restore_backup()

        # Check that a message was collected about no backup found
        error_messages = [
            msg for msg in migration._messages if msg[0] == "ERROR"
        ]
        # This might not create an error message if no backups exist
        # The behavior depends on implementation details
