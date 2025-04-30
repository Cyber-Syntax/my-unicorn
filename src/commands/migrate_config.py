#!/usr/bin/env python3
"""Configuration migration command module.

This module provides a command to check and migrate configuration settings
when the application is updated with new configuration options.
"""

import json
import logging
import os

from src.commands.base import Command
from src.config_migrator import ConfigMigrator


class MigrateConfigCommand(Command):
    """Command to check and migrate configuration settings.

    This command identifies missing configuration keys in both global and app-specific
    configurations, then adds those keys with appropriate default values.
    """

    def __init__(self):
        """Initialize the migration command."""
        self._logger = logging.getLogger(__name__)

    def execute(self):
        """Execute the configuration migration command.

        Checks both global and app-specific configurations for missing keys
        and updates them with default values when needed.
        """
        self._logger.info("Starting configuration migration check")
        print("\n=== Configuration Migration Check ===")

        # Display current configuration file paths
        global_config_path = os.path.expanduser("~/.config/myunicorn/settings.json")
        print(f"Global config location: {global_config_path}")

        # Check if file exists and display its content for debugging
        if os.path.isfile(global_config_path):
            try:
                with open(global_config_path, encoding="utf-8") as f:
                    current_config = json.load(f)
                print(f"Current config keys: {list(current_config.keys())}")
                self._logger.debug(f"Current config content: {current_config}")
            except Exception as e:
                self._logger.error(f"Error reading config file: {e}")
                print(f"Error reading config file: {e}")
        else:
            print("Global config file does not exist yet.")

        print("\nChecking for configuration updates...")

        # Run the migration
        results = ConfigMigrator.run_full_migration()

        # Report on global config migration
        if results["global_config"]["migrated"]:
            keys = results["global_config"]["keys_added"]
            print(f"\n✅ Global configuration updated with {len(keys)} new settings:")
            for key in keys:
                print(f"  • Added: {key}")
        else:
            print("\n✓ Global configuration is up-to-date.")

        # Report on app config migrations
        app_count = results["app_configs"]["migrated_count"]
        if app_count > 0:
            print(f"\n✅ Updated {app_count} application configuration files:")
            for app_name, keys in results["app_configs"]["details"].items():
                print(f"  • {app_name}: Added {len(keys)} settings ({', '.join(keys)})")
        else:
            print("\n✓ All application configurations are up-to-date.")

        print("\nConfiguration migration complete.")
        print("==================================")
