#!/usr/bin/env python3
"""Configuration migration module for detecting and updating config files."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from my_unicorn.app_config import AppConfigManager
from my_unicorn.global_config import GlobalConfigManager

logger = logging.getLogger(__name__)


class ConfigMigrator:
    """Manages detection and migration of configuration settings."""

    @staticmethod
    def check_and_migrate_global_config(
        delete_unused: bool = False, require_confirmation: bool = True
    ) -> tuple[bool, list[str], list[str]]:
        """Check global configuration for missing or unused keys and migrate if needed.

        Args:
            delete_unused: Whether to delete unused configuration keys.
            require_confirmation: Whether to require user confirmation before deleting.

        Returns:
            tuple[bool, list[str], list[str]]: (True if migration occurred,
                                               list of migrated keys,
                                               list of deleted keys)

        """
        logger.info("Checking global configuration for updates")

        # Get default values from a fresh instance
        default_config = GlobalConfigManager()
        default_dict = default_config.to_dict()

        # Path to user's config file
        config_file = Path(os.path.expanduser("~/.config/myunicorn/settings.json"))
        logger.debug("Global config file path: %s", config_file)

        # Debug output for default configuration
        logger.debug("Default config keys: %s", list(default_dict.keys()))

        try:
            if config_file.is_file():
                # Read the existing config file directly to detect changes without modifying it yet
                with open(config_file, encoding="utf-8") as f:
                    file_content = f.read()

                # Parse the JSON content
                user_config_dict = json.loads(file_content)
                logger.debug("User config keys: %s", list(user_config_dict.keys()))

                # Find missing keys (in default but not in user config)
                missing_keys = [key for key in default_dict if key not in user_config_dict]
                logger.info("Missing keys check result: %s", missing_keys)

                # Find unused keys (in user config but not in default)
                unused_keys = [key for key in user_config_dict if key not in default_dict]
                logger.info("Unused keys check result: %s", unused_keys)

                has_changes = False
                deleted_keys = []

                # Handle unused keys if deletion is requested
                if delete_unused and unused_keys:
                    logger.info("Found %d unused keys: %s", len(unused_keys), unused_keys)

                    # Get confirmation if required
                    confirmed = not require_confirmation
                    if require_confirmation:
                        print(
                            "\nDetected unused configuration keys that are no longer needed:"
                        )
                        for key in unused_keys:
                            print(f"  • {key}: {user_config_dict[key]}")

                        confirmation = (
                            input("\nDo you want to remove these unused keys? (yes/no): ")
                            .strip()
                            .lower()
                        )
                        confirmed = confirmation == "yes"

                    # Delete keys if confirmed - leverage GlobalConfigManager
                    if confirmed:
                        # Create an instance that will load the current configuration
                        config_manager = GlobalConfigManager()

                        # Get current, valid configuration as a dictionary
                        current_config = config_manager.to_dict()

                        # Create a new configuration dictionary with only valid keys
                        cleaned_config = {}
                        for key, value in user_config_dict.items():
                            if key in current_config:
                                cleaned_config[key] = value

                        # Add any missing default keys
                        for key in missing_keys:
                            cleaned_config[key] = default_dict[key]

                        # Write back the clean configuration with only valid keys
                        with open(config_file, "w", encoding="utf-8") as f:
                            json.dump(cleaned_config, f, indent=4)

                        # Record which keys were deleted
                        deleted_keys = unused_keys
                        logger.info(
                            "Removed %d unused keys from global config", len(deleted_keys)
                        )
                        has_changes = True
                    else:
                        logger.info("Skipped deleting unused keys (not confirmed)")

                # Early return if no changes needed
                if not missing_keys and not has_changes:
                    logger.info("Global configuration is up-to-date")
                    return False, [], []

                # Add missing keys with default values if not already handled above
                if missing_keys and not has_changes:
                    # Create a new configuration dictionary with existing and new keys
                    updated_config = user_config_dict.copy()
                    for key in missing_keys:
                        updated_config[key] = default_dict[key]
                        logger.info(
                            "Added missing key '%s' with default value: %s",
                            key,
                            default_dict[key],
                        )

                    # Write back the updated configuration
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(updated_config, f, indent=4)

                    has_changes = True

                if has_changes:
                    logger.info(
                        "Successfully migrated global config with %d new keys, "
                        "removed %d unused keys",
                        len(missing_keys),
                        len(deleted_keys),
                    )
                return has_changes, missing_keys, deleted_keys
            else:
                # Config file doesn't exist, create a new one using GlobalConfigManager
                logger.info("Config file not found at %s, creating new", config_file)
                new_config = GlobalConfigManager()
                new_config.save_config()
                logger.info("Created new global configuration with default values")
                return True, list(default_dict.keys()), []

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in config file: %s", e)
            return False, [], []
        except Exception as e:
            logger.error("Error during global config migration: %s", e, exc_info=True)
            return False, [], []

    @staticmethod
    def _get_confirmation_for_app(
        app_name: str, unused_keys: list[str], app_dict: dict[str, Any]
    ) -> bool:
        """Get user confirmation for deleting unused keys for a specific app.

        Args:
            app_name: The name of the application.
            unused_keys: The list of unused keys to potentially delete.
            app_dict: The application's configuration dictionary.

        Returns:
            bool: True if user confirms deletion, False otherwise.

        """
        print(f"\nDetected unused configuration keys for app '{app_name}':")
        for key in unused_keys:
            print(f"  • {key}: {app_dict[key]}")

        confirmation = (
            input(f"\nDo you want to remove these unused keys for '{app_name}'? (yes/no): ")
            .strip()
            .lower()
        )
        return confirmation == "yes"

    @staticmethod
    def check_and_migrate_app_configs(
        delete_unused: bool = False, require_confirmation: bool = True
    ) -> tuple[int, dict[str, list[str]], dict[str, list[str]]]:
        """Check all app configuration files for missing or unused keys and migrate if needed.

        Args:
            delete_unused: Whether to delete unused configuration keys.
            require_confirmation: Whether to require user confirmation before deleting.

        Returns:
            tuple[int, tuple[str, list[str]], tuple[str, list[str]]]:
                (Migrated config count,
                dict of app name -> migrated keys,
                dict of app name -> deleted keys)

        """
        # Create app config manager to list files and get default values
        app_config = AppConfigManager()
        app_config_folder = app_config.config_folder
        logger.info("Checking app configs in: %s", app_config_folder)

        migrated_configs = {}
        deleted_configs = {}

        try:
            # list all JSON files in the app config directory
            json_files = app_config.list_json_files()
            logger.debug("Found %d app config files: %s", len(json_files), json_files)

            if not json_files:
                logger.info("No app configuration files found")
                return 0, {}, {}

            # Get default template for app configs
            default_app_config = AppConfigManager()
            default_dict = default_app_config.to_dict()
            logger.debug("Default app config keys: %s", list(default_dict.keys()))

            # Check each app config file
            for json_file in json_files:
                app_name = os.path.splitext(json_file)[0]
                config_path = Path(os.path.join(app_config_folder, json_file))
                logger.debug("Processing app config: %s at %s", app_name, config_path)

                try:
                    # Read the app config file
                    with open(config_path, encoding="utf-8") as f:
                        file_content = f.read()

                    # Parse JSON content
                    user_app_dict = json.loads(file_content)
                    logger.debug(
                        "App '%s' config keys: %s", app_name, list(user_app_dict.keys())
                    )

                    # Special handling for app_rename being null
                    if (
                        "app_rename" in user_app_dict
                        and user_app_dict["app_rename"] is None
                        and "repo" in user_app_dict
                        and user_app_dict["repo"]
                    ):
                        logger.info(
                            "Fixing null app_rename for app '%s' using repo value", app_name
                        )
                        user_app_dict["app_rename"] = user_app_dict["repo"]
                        has_changes = True  # Mark that this config needs to be saved
                    else:
                        has_changes = False

                    # Find missing keys
                    missing_keys = [key for key in default_dict if key not in user_app_dict]
                    logger.debug("App '%s' missing keys: %s", app_name, missing_keys)

                    # Find unused keys
                    unused_keys = [key for key in user_app_dict if key not in default_dict]
                    logger.debug("App '%s' unused keys: %s", app_name, unused_keys)

                    app_deleted_keys = []

                    # Handle unused keys if deletion is requested
                    if delete_unused and unused_keys:
                        logger.info(
                            "Found %d unused keys for app '%s': %s",
                            len(unused_keys),
                            app_name,
                            unused_keys,
                        )

                        # Get confirmation if required
                        confirmed = not require_confirmation
                        if require_confirmation and unused_keys:
                            confirmed = ConfigMigrator._get_confirmation_for_app(
                                app_name, unused_keys, user_app_dict
                            )

                        # Delete keys if confirmed
                        if confirmed:
                            for key in unused_keys:
                                del user_app_dict[key]
                                app_deleted_keys.append(key)
                                logger.info(
                                    "Deleted unused key '%s' from app '%s'", key, app_name
                                )
                            has_changes = True
                            deleted_configs[app_name] = app_deleted_keys
                            logger.info(
                                "Removed %d unused keys from app '%s'",
                                len(app_deleted_keys),
                                app_name,
                            )
                        else:
                            logger.info(
                                "Skipped deleting unused keys for app '%s' (not confirmed)",
                                app_name,
                            )

                    # Early return if no changes needed
                    if not missing_keys and not has_changes:
                        logger.info("App config '%s' is up-to-date", app_name)
                        continue

                    # Add missing keys with default values
                    for key in missing_keys:
                        user_app_dict[key] = default_dict[key]
                        logger.info("Added missing key '%s' to app '%s'", key, app_name)
                        has_changes = True

                    # Write updated config back to file if there were changes
                    if has_changes:
                        with open(config_path, "w", encoding="utf-8") as f:
                            json.dump(user_app_dict, f, indent=4)

                    if missing_keys:
                        migrated_configs[app_name] = missing_keys
                        logger.info(
                            "Migrated app '%s' with %d new keys", app_name, len(missing_keys)
                        )

                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON in app config '%s': %s", app_name, e)
                except Exception as e:
                    logger.error(
                        "Error processing app config '%s': %s", app_name, e, exc_info=True
                    )

            return len(migrated_configs), migrated_configs, deleted_configs

        except Exception as e:
            logger.error("Error during app config migration: %s", e, exc_info=True)
            return 0, {}, {}

    @staticmethod
    def run_full_migration(
        delete_unused: bool = False, require_confirmation: bool = True
    ) -> dict[str, Any]:
        """Run a complete migration of global and app configurations.

        Args:
            delete_unused: Whether to delete unused configuration keys.
            require_confirmation: Whether to require user confirmation before deleting.

        Returns:
            tuple[str, Any]: Migration results summary

        """
        results = {
            "global_config": {"migrated": False, "keys_added": [], "keys_deleted": []},
            "app_configs": {
                "migrated_count": 0,
                "updated_count": 0,
                "details": {},
                "deleted_details": {},
            },
        }

        # Migrate global configuration
        global_migrated, global_keys, global_deleted = (
            ConfigMigrator.check_and_migrate_global_config(delete_unused, require_confirmation)
        )
        results["global_config"]["migrated"] = global_migrated
        results["global_config"]["keys_added"] = global_keys
        results["global_config"]["keys_deleted"] = global_deleted

        # Migrate app configurations
        app_count, app_details, app_deleted = ConfigMigrator.check_and_migrate_app_configs(
            delete_unused, require_confirmation
        )
        results["app_configs"]["migrated_count"] = app_count
        results["app_configs"]["details"] = app_details
        results["app_configs"]["deleted_details"] = app_deleted
        results["app_configs"]["updated_count"] = len(app_deleted)

        return results
