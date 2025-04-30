#!/usr/bin/env python3
"""Configuration migration module for detecting and updating config files."""

import json
import logging
import os
from typing import Any, Dict, List, Tuple

from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager

logger = logging.getLogger(__name__)


class ConfigMigrator:
    """Manages detection and migration of configuration settings."""

    @staticmethod
    def check_and_migrate_global_config() -> Tuple[bool, List[str]]:
        """Check global configuration for missing keys and migrate if needed.

        Returns:
            Tuple[bool, List[str]]: (True if migration occurred, list of migrated keys)
        """
        logger.info("Checking global configuration for updates")

        # Get default values from a fresh instance
        default_config = GlobalConfigManager()
        default_dict = default_config.to_dict()

        # Path to user's config file
        config_file = os.path.expanduser("~/.config/myunicorn/settings.json")
        logger.debug(f"Global config file path: {config_file}")

        # Debug output for default configuration
        logger.debug(f"Default config keys: {list(default_dict.keys())}")

        try:
            if os.path.isfile(config_file):
                # Read the existing config file directly
                with open(config_file, encoding="utf-8") as f:
                    file_content = f.read()

                # Debug output for raw file content
                logger.debug(f"Raw config file content: {file_content}")

                # Parse the JSON content
                user_config_dict = json.loads(file_content)
                logger.debug(f"User config keys: {list(user_config_dict.keys())}")

                # Find missing keys (in default but not in user config)
                missing_keys = [key for key in default_dict if key not in user_config_dict]
                logger.info(f"Missing keys check result: {missing_keys}")

                if not missing_keys:
                    logger.info("Global configuration is up-to-date")
                    return False, []

                logger.info(f"Found {len(missing_keys)} missing keys: {missing_keys}")

                # Add missing keys with default values
                for key in missing_keys:
                    user_config_dict[key] = default_dict[key]
                    logger.info(
                        f"Added missing key '{key}' with default value: {default_dict[key]}"
                    )

                # Write updated config back to file
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(user_config_dict, f, indent=4)

                logger.info(
                    f"Successfully migrated global config with {len(missing_keys)} new keys"
                )
                return True, missing_keys
            else:
                # Config file doesn't exist, create a new one
                logger.info(f"Config file not found at {config_file}, creating new")
                os.makedirs(os.path.dirname(config_file), exist_ok=True)
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(default_dict, f, indent=4)

                logger.info("Created new global configuration with default values")
                return True, list(default_dict.keys())

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return False, []
        except Exception as e:
            logger.error(f"Error during global config migration: {e!s}", exc_info=True)
            return False, []

    @staticmethod
    def check_and_migrate_app_configs() -> Tuple[int, Dict[str, List[str]]]:
        """Check all app configuration files for missing keys and migrate if needed.

        Returns:
            Tuple[int, Dict[str, List[str]]]: (Migrated config count, dict of app name -> migrated keys)
        """
        # Create app config manager to list files and get default values
        app_config = AppConfigManager()
        app_config_folder = app_config.config_folder
        logger.info(f"Checking app configs in: {app_config_folder}")

        migrated_configs = {}

        try:
            # List all JSON files in the app config directory
            json_files = app_config.list_json_files()
            logger.debug(f"Found {len(json_files)} app config files: {json_files}")

            if not json_files:
                logger.info("No app configuration files found")
                return 0, {}

            # Get default template for app configs
            default_app_config = AppConfigManager()
            default_dict = default_app_config.to_dict()
            logger.debug(f"Default app config keys: {list(default_dict.keys())}")

            # Check each app config file
            for json_file in json_files:
                app_name = os.path.splitext(json_file)[0]
                config_path = os.path.join(app_config_folder, json_file)
                logger.debug(f"Processing app config: {app_name} at {config_path}")

                try:
                    # Read the app config file
                    with open(config_path, encoding="utf-8") as f:
                        file_content = f.read()

                    # Parse JSON content
                    user_app_dict = json.loads(file_content)
                    logger.debug(f"App '{app_name}' config keys: {list(user_app_dict.keys())}")

                    # Find missing keys
                    missing_keys = [key for key in default_dict if key not in user_app_dict]
                    logger.debug(f"App '{app_name}' missing keys: {missing_keys}")

                    if not missing_keys:
                        logger.info(f"App config '{app_name}' is up-to-date")
                        continue

                    # Add missing keys with default values
                    for key in missing_keys:
                        user_app_dict[key] = default_dict[key]
                        logger.info(f"Added missing key '{key}' to app '{app_name}'")

                    # Write updated config back to file
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(user_app_dict, f, indent=4)

                    migrated_configs[app_name] = missing_keys
                    logger.info(f"Migrated app '{app_name}' with {len(missing_keys)} new keys")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in app config '{app_name}': {e}")
                except Exception as e:
                    logger.error(f"Error processing app config '{app_name}': {e!s}", exc_info=True)

            return len(migrated_configs), migrated_configs

        except Exception as e:
            logger.error(f"Error during app config migration: {e!s}", exc_info=True)
            return 0, {}

    @staticmethod
    def run_full_migration() -> Dict[str, Any]:
        """Run a complete migration of global and app configurations.

        Returns:
            Dict[str, Any]: Migration results summary
        """
        results = {
            "global_config": {"migrated": False, "keys_added": []},
            "app_configs": {"migrated_count": 0, "details": {}},
        }

        # Migrate global configuration
        global_migrated, global_keys = ConfigMigrator.check_and_migrate_global_config()
        results["global_config"]["migrated"] = global_migrated
        results["global_config"]["keys_added"] = global_keys

        # Migrate app configurations
        app_count, app_details = ConfigMigrator.check_and_migrate_app_configs()
        results["app_configs"]["migrated_count"] = app_count
        results["app_configs"]["details"] = app_details

        return results
