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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from my_unicorn.config import DirectoryManager

# Import from centralized constants module
from my_unicorn.constants import CONFIG_VERSION


class ConfigMigration:
    """Single class to handle config migration with deferred logging."""

    def __init__(self, directory_manager: "DirectoryManager") -> None:
        """Initialize migration handler.

        Args:
            directory_manager: Directory manager for path operations

        """
        self.directory_manager = directory_manager
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
            print(f"Config Migration {level}: {formatted_msg}")

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
            "DEFAULT", "config_version", fallback="0.0.0"
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
        return self._compare_versions(current_version, CONFIG_VERSION) < 0

    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare two semantic version strings.

        Args:
            version1: First version string (e.g., "1.0.0")
            version2: Second version string (e.g., "1.0.1")

        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2

        """

        def parse_version(version: str) -> list[int]:
            """Parse version string into list of integers."""
            try:
                return [int(x) for x in version.split(".")]
            except ValueError:
                # Fallback for invalid versions
                return [0, 0, 0]

        v1_parts = parse_version(version1)
        v2_parts = parse_version(version2)

        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        for v1, v2 in zip(v1_parts, v2_parts, strict=True):
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
        return 0

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
                "DEFAULT", "config_version", fallback="1.0.0"
            )
            version_needs_update = current_version != CONFIG_VERSION

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
                user_config.set("DEFAULT", "config_version", CONFIG_VERSION)
                self._collect_message(
                    "INFO",
                    "Updated configuration version to %s",
                    CONFIG_VERSION,
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

            temp_manager = GlobalConfigManager(self.directory_manager)
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
        if not self.directory_manager.settings_file.exists():
            # No config to backup
            return self.directory_manager.settings_file

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.directory_manager.settings_file.with_suffix(
            f".{timestamp}.backup"
        )

        try:
            shutil.copy2(self.directory_manager.settings_file, backup_path)
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
                self.directory_manager.settings_file.parent.glob(
                    f"{self.directory_manager.settings_file.name}.*.backup"
                )
            )
            if backup_files:
                latest_backup = max(
                    backup_files, key=lambda p: p.stat().st_mtime
                )
                shutil.copy2(
                    latest_backup, self.directory_manager.settings_file
                )
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
                ("DEFAULT", "config_version"),
                ("DEFAULT", "log_level"),
                ("DEFAULT", "console_log_level"),
                ("network", "retry_attempts"),
                ("network", "timeout_seconds"),
                ("directory", "repo"),
                ("directory", "storage"),
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
            # This can happen during testing or unusual initialization scenarios
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
