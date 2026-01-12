"""Configuration migration module - separate to avoid circular imports.

This module handles configuration migration independently from the main config
and logger modules to break the circular import dependency.

The migration process:
1. Collects migration messages during config loading (no logger dependency)
2. After config loading is complete, replays messages to the existing logger
3. This ensures the custom logger functionality is preserved while avoiding
   circular imports between config.py ↔ logger.py during initialization.
"""

import configparser
import shutil
from datetime import datetime
from pathlib import Path

# Import from centralized constants module
from my_unicorn.domain.constants import (
    CONFIG_BACKUP_EXTENSION,
    CONFIG_BACKUP_SUFFIX_TEMPLATE,
    CONFIG_BACKUP_TIMESTAMP_FORMAT,
    CONFIG_FALLBACK_OLD_VERSION,
    CONFIG_FALLBACK_PREVIOUS_VERSION,
    CONFIG_MIGRATION_PRINT_PREFIX,
    GLOBAL_CONFIG_VERSION,
    KEY_CONFIG_VERSION,
    KEY_REPO,
    KEY_RETRY_ATTEMPTS,
    KEY_STORAGE,
    KEY_TIMEOUT_SECONDS,
    SECTION_DEFAULT,
    SECTION_DIRECTORY,
    SECTION_NETWORK,
)
from my_unicorn.domain.version import compare_versions
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class ConfigMigration:
    """Single class to handle config migration with deferred logging."""

    def __init__(self, config_dir: Path, settings_file: Path) -> None:
        """Initialize migration handler.

        Args:
            config_dir: Configuration directory path
            settings_file: Settings file path

        """
        self.config_dir = config_dir
        self.settings_file = settings_file
        # (level, message, args)
        self._messages: list[tuple[str, str, tuple]] = []

    def _collect_message(self, level: str, message: str, *args) -> None:
        """Collect migration messages for later logging.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message format string
            *args: Arguments for message formatting

        """
        self._messages.append((level, message, args))

        # Print critical errors to console as fallback
        if level in ("ERROR", "CRITICAL"):
            formatted_msg = message % args if args else message
            logger.info(
                "%s %s: %s",
                CONFIG_MIGRATION_PRINT_PREFIX,
                level,
                formatted_msg,
            )

    def migrate_if_needed(
        self,
        user_config: configparser.ConfigParser,
        defaults: dict[str, str | dict[str, str]],
    ) -> bool:
        """Migrate configuration if needed.

        Args:
            user_config: User configuration parser
            defaults: Default configuration values

        Returns:
            True if migration was successful or not needed, False on failure

        """
        current_version = user_config.get(
            SECTION_DEFAULT,
            KEY_CONFIG_VERSION,
            fallback=CONFIG_FALLBACK_OLD_VERSION,
        )

        if not self._needs_migration(current_version):
            return True

        return self._migrate_configuration(user_config, defaults)

    def _needs_migration(self, current_version: str) -> bool:
        """Check if configuration needs migration.

        Args:
            current_version: Current config version string

        Returns:
            True if migration is needed

        """
        return compare_versions(current_version, GLOBAL_CONFIG_VERSION) < 0

    def _migrate_configuration(
        self,
        user_config: configparser.ConfigParser,
        defaults: dict[str, str | dict[str, str]],
    ) -> bool:
        """Perform the actual migration.

        Args:
            user_config: User configuration parser to migrate
            defaults: Default configuration values

        Returns:
            True if migration was successful, False otherwise

        """
        try:
            self._collect_message("INFO", "Starting configuration migration")

            # Check if any fields actually need to be added/changed
            fields_added = self._merge_missing_fields(user_config, defaults)
            current_version = user_config.get(
                SECTION_DEFAULT,
                KEY_CONFIG_VERSION,
                fallback=CONFIG_FALLBACK_PREVIOUS_VERSION,
            )
            version_needs_update = current_version != GLOBAL_CONFIG_VERSION

            # If no fields need to be added and version is current, no
            # migration needed
            if not fields_added and not version_needs_update:
                self._collect_message(
                    "INFO", "No migration needed - configuration is up to date"
                )
                return True

            # Only create backup if we're actually going to make changes
            self._create_config_backup()

            # Update config version if needed
            if version_needs_update:
                user_config.set(
                    "DEFAULT", "config_version", GLOBAL_CONFIG_VERSION
                )
                self._collect_message(
                    "INFO",
                    "Updated configuration version to %s",
                    GLOBAL_CONFIG_VERSION,
                )

            # Validate merged configuration
            if not self._validate_merged_config(user_config):
                self._collect_message(
                    "ERROR", "Migration validation failed, restoring backup"
                )
                self._restore_backup()
                return False

            # Save migrated configuration using the new comment-aware method
            # We need to import here to avoid circular imports
            from my_unicorn.config import GlobalConfigManager

            temp_manager = GlobalConfigManager(self.config_dir)
            migrated_config = temp_manager._convert_to_global_config(
                user_config
            )
            temp_manager.save_global_config(migrated_config)

            self._collect_message(
                "INFO", "Configuration migration completed successfully"
            )
            return True

        except Exception as e:
            self._collect_message(
                "ERROR", "Configuration migration failed: %s", e
            )
            return False

    def _create_config_backup(self) -> Path:
        """Create timestamped backup of configuration file.

        Returns:
            Path to backup file

        Raises:
            OSError: If backup creation fails

        """
        if not self.settings_file.exists():
            # No config to backup
            return self.settings_file

        # Prepare backup filename with timestamp
        timestamp = datetime.now().strftime(CONFIG_BACKUP_TIMESTAMP_FORMAT)
        backup_path: Path = self.settings_file.with_suffix(
            CONFIG_BACKUP_SUFFIX_TEMPLATE.format(timestamp=timestamp)
        )

        try:
            shutil.copy2(self.settings_file, backup_path)
            self._collect_message(
                "INFO", "Created configuration backup at %s", backup_path
            )
            return backup_path
        except OSError as e:
            raise OSError(f"Failed to create config backup: {e}") from e

    def _restore_backup(self) -> None:
        """Restore configuration from most recent backup."""
        try:
            # Find most recent backup
            backup_files = list(
                self.settings_file.parent.glob(
                    f"{self.settings_file.name}.*{CONFIG_BACKUP_EXTENSION}"
                )
            )
            if backup_files:
                latest_backup = max(
                    backup_files, key=lambda p: p.stat().st_mtime
                )
                shutil.copy2(latest_backup, self.settings_file)
                self._collect_message(
                    "INFO",
                    "Restored configuration from backup: %s",
                    latest_backup,
                )
        except Exception as e:
            self._collect_message("ERROR", "Failed to restore backup: %s", e)

    def _merge_missing_fields(
        self,
        user_config: configparser.ConfigParser,
        defaults: dict[str, str | dict[str, str]],
    ) -> bool:
        """Merge missing configuration fields with defaults.

        Args:
            user_config: User's configuration parser
            defaults: Default configuration values

        Returns:
            True if any fields were added, False otherwise

        """
        fields_added = False

        # Check scalar fields in DEFAULT section
        for key, value in defaults.items():
            if isinstance(value, str) and not user_config.has_option(
                "DEFAULT", key
            ):
                user_config.set("DEFAULT", key, value)
                self._collect_message(
                    "INFO",
                    "Added missing configuration field: %s = %s",
                    key,
                    value,
                )
                fields_added = True

        # Check nested sections (network, directory)
        for section_name, section_values in defaults.items():
            if isinstance(section_values, dict):
                if not user_config.has_section(section_name):
                    user_config.add_section(section_name)
                    self._collect_message(
                        "INFO",
                        "Added missing configuration section: %s",
                        section_name,
                    )

                for key, value in section_values.items():
                    if not user_config.has_option(section_name, key):
                        user_config.set(section_name, key, str(value))
                        self._collect_message(
                            "INFO",
                            "Added missing field: [%s] %s = %s",
                            section_name,
                            key,
                            value,
                        )
                        fields_added = True

        return fields_added

    def _validate_merged_config(
        self, config: configparser.ConfigParser
    ) -> bool:
        """Validate merged configuration for completeness.

        Args:
            config: Configuration parser to validate

        Returns:
            True if configuration is valid and complete

        """
        try:
            # Basic validation - check required fields exist
            required_fields = [
                (SECTION_DEFAULT, KEY_CONFIG_VERSION),
                (SECTION_DEFAULT, "log_level"),
                (SECTION_DEFAULT, "console_log_level"),
                (SECTION_NETWORK, KEY_RETRY_ATTEMPTS),
                (SECTION_NETWORK, KEY_TIMEOUT_SECONDS),
                (SECTION_DIRECTORY, KEY_REPO),
                (SECTION_DIRECTORY, KEY_STORAGE),
            ]

            for section, key in required_fields:
                if not config.has_option(section, key):
                    self._collect_message(
                        "ERROR",
                        "Missing required field: [%s] %s",
                        section,
                        key,
                    )
                    return False

            self._collect_message(
                "DEBUG", "Configuration validation successful"
            )
            return True
        except Exception as e:
            self._collect_message(
                "ERROR", "Configuration validation failed: %s", e
            )
            return False

    def replay_messages_to_logger(self) -> None:
        """Replay collected messages to existing custom logger.

        This method is called after config loading is complete and the logger
        is available. It replays all collected migration messages to maintain
        proper structured logging while avoiding circular imports during init.
        """
        if not self._messages:
            return

        try:
            # Import logger only when needed (after config is loaded)
            from my_unicorn.logger import get_logger

            logger = get_logger("my_unicorn.config_migration")

            for level, message, args in self._messages:
                log_method = getattr(logger, level.lower())
                if args:
                    log_method(message, *args)
                else:
                    log_method(message)

            self._messages.clear()
        except Exception:
            # If logger still not available, keep messages for next attempt
            # This can happen during testing or unusual init scenarios
            pass

    def clear_messages(self) -> None:
        """Clear collected messages without replaying them.

        Useful for testing or when messages should be discarded.
        """
        self._messages.clear()

    @property
    def has_messages(self) -> bool:
        """Check if there are unreplayed messages.

        Returns:
            True if there are messages waiting to be replayed

        """
        return bool(self._messages)
