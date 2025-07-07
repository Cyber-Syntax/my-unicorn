#!/usr/bin/env python3
"""Configuration migration command module.

This module provides a command to check and migrate configuration settings
when the application is updated with new configuration options.
"""

import argparse
import json
import logging
import os

from my_unicorn.commands.base import Command
from my_unicorn.config_migrator import ConfigMigrator
from my_unicorn.global_config import GlobalConfigManager


class MigrateConfigCommand(Command):
    """Command to check and migrate configuration settings.

    This command identifies missing configuration keys in both global and app-specific
    configurations, then adds those keys with appropriate default values. It can also
    detect and remove unused configuration keys with user confirmation.
    """

    def __init__(self):
        """Initialize the migration command."""
        self._logger = logging.getLogger(__name__)
        self._parser = argparse.ArgumentParser(
            description="Migrate configuration files by adding missing settings and optionally removing unused settings."
        )
        self._parser.add_argument(
            "--clean",
            action="store_true",
            help="Enable removal of unused configuration settings",
        )
        self._parser.add_argument(
            "--force",
            action="store_true",
            help="Remove unused settings without user confirmation",
        )
        # Create instance of GlobalConfigManager for use in the command
        self._global_config = GlobalConfigManager()

    def execute(self, args=None):
        """Execute the configuration migration command.

        Checks both global and app-specific configurations for missing keys
        and updates them with default values when needed. Can also detect and
        remove unused keys with user confirmation.

        Args:
            args: Command line arguments (optional).

        """
        self._logger.info("Starting configuration migration check")
        print("\n=== Configuration Migration Check ===")

        # Check if called from menu (args=None) or command line
        if args is None:
            # Interactive mode - called from menu
            print("\nDo you want to check for and remove unused configuration variables?")
            user_choice = input("This will help clean up old settings (yes/no): ").strip().lower()
            delete_unused = user_choice in ("yes", "y")
            require_confirmation = True  # Always require confirmation in interactive mode
        else:
            # Command line mode
            parsed_args = self._parser.parse_args(args)
            delete_unused = parsed_args.clean
            require_confirmation = not parsed_args.force

        if delete_unused:
            if require_confirmation:
                print(
                    "Unused configuration variables will be identified and removed with your confirmation."
                )
            else:
                print(
                    "Unused configuration variables will be automatically removed (--force mode)."
                )

        # Display current configuration file paths
        global_config_path = os.path.expanduser("~/.config/myunicorn/settings.json")
        print(f"Global config location: {global_config_path}")

        # Check if file exists and display its content for debugging
        if os.path.isfile(global_config_path):
            try:
                with open(global_config_path, encoding="utf-8") as f:
                    current_config = json.load(f)
                print(f"Current config keys: {list(current_config.keys())}")
                self._logger.debug("Current config content: %s", current_config)
            except Exception as e:
                self._logger.error("Error reading config file: %s", e)
                print(f"Error reading config file: {e}")
        else:
            print("Global config file does not exist yet.")

        print("\nChecking for configuration updates...")

        # Run the migration
        results = ConfigMigrator.run_full_migration(
            delete_unused=delete_unused, require_confirmation=require_confirmation
        )

        # Reload the global configuration after migration
        self._global_config.reload()

        # Report on global config migration
        global_migrated = results["global_config"]["migrated"]
        global_added = results["global_config"]["keys_added"]
        global_deleted = results["global_config"]["keys_deleted"]

        if global_added or global_deleted:
            print("\n✅ Global configuration updated:")

            if global_added:
                print(f"  • Added {len(global_added)} new settings:")
                for key in global_added:
                    print(f"    - Added: {key}")

            if global_deleted:
                print(f"  • Removed {len(global_deleted)} unused settings:")
                for key in global_deleted:
                    print(f"    - Removed: {key}")
        else:
            print("\n✓ Global configuration is up-to-date.")

        # Report on app config migrations
        app_count = results["app_configs"]["migrated_count"]
        app_deleted_count = results["app_configs"]["updated_count"]

        if app_count > 0 or app_deleted_count > 0:
            print("\n✅ Application configuration updates:")

            # Report added keys
            if app_count > 0:
                print(f"  • Updated {app_count} application configuration files with new settings:")
                for app_name, keys in results["app_configs"]["details"].items():
                    print(f"    - {app_name}: Added {len(keys)} settings ({', '.join(keys)})")

            # Report deleted keys
            if results["app_configs"]["deleted_details"]:
                deleted_apps = results["app_configs"]["deleted_details"]
                print(
                    f"  • Removed unused settings from {len(deleted_apps)} application configurations:"
                )
                for app_name, keys in deleted_apps.items():
                    print(f"    - {app_name}: Removed {len(keys)} settings ({', '.join(keys)})")
        else:
            print("\n✓ All application configurations are up-to-date.")

        print("\nConfiguration migration complete.")
        print("==================================")
