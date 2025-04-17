#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto update command module.

This module provides a command to automatically check and update all AppImages
without requiring manual selection of each app.
"""

import logging
import os
from typing import List, Dict, Any

from src.commands.update_base import BaseUpdateCommand


class UpdateAllAutoCommand(BaseUpdateCommand):
    """Command to automatically check and update all AppImages without manual selection."""

    def execute(self):
        """
        Check all AppImage configurations and update those with new versions available.

        This method automatically scans all available AppImage configurations and
        updates any that have newer versions available.
        """
        logging.info("Starting automatic check of all AppImages")
        print("Checking all AppImages for updates...")

        # Load global configuration
        self.global_config.load_config()

        # Find all updatable apps
        updatable_apps = self._find_all_updatable_apps()

        if not updatable_apps:
            logging.info("All AppImages are up to date")
            print("All AppImages are up to date!")
            return

        # Display updatable apps to user
        self._display_update_list(updatable_apps)

        # Determine what to do based on batch mode
        if self.global_config.batch_mode:
            logging.info(
                f"Batch mode enabled - updating all {len(updatable_apps)} AppImages automatically"
            )
            print(
                f"Batch mode enabled - updating all {len(updatable_apps)} AppImages automatically"
            )
            self._update_apps(updatable_apps)
        else:
            # In interactive mode, ask which apps to update
            self._handle_interactive_update(updatable_apps)

    def _find_all_updatable_apps(self) -> List[Dict[str, Any]]:
        """
        Find all AppImages that have updates available.

        Returns:
            List[Dict[str, Any]]: List of updatable app information dictionaries
        """
        updatable_apps = []

        try:
            # Get all config files
            json_files = self._list_all_config_files()
            if not json_files:
                logging.warning("No AppImage configuration files found")
                print("No AppImage configuration files found. Use the Download option first.")
                return []

            print(f"Checking {len(json_files)} AppImage configurations...")

            # Check each app for updates
            for config_file in json_files:
                try:
                    # Create a temporary app config for checking this app
                    app_name = os.path.splitext(config_file)[0]  # Remove .json extension
                    print(f"Checking {app_name}...", end="", flush=True)

                    app_data = self._check_single_app_version(self.app_config, config_file)
                    if app_data:
                        print(f" update available: {app_data['current']} → {app_data['latest']}")
                        updatable_apps.append(app_data)
                    else:
                        print(" already up to date")

                except Exception as e:
                    error_msg = f"Error checking {config_file}: {str(e)}"
                    logging.error(error_msg)
                    print(f" error: {str(e)}")

        except Exception as e:
            error_msg = f"Error during update check: {str(e)}"
            logging.error(error_msg)
            print(error_msg)

        return updatable_apps

    def _list_all_config_files(self) -> List[str]:
        """
        Get a list of all AppImage configuration files.

        Returns:
            List[str]: List of configuration filenames
        """
        return self.app_config.list_json_files()

    def _handle_interactive_update(self, updatable_apps: List[Dict[str, Any]]) -> None:
        """
        Handle interactive mode where user selects which apps to update.

        Args:
            updatable_apps: List of updatable app information dictionaries
        """
        # Ask user which apps to update
        print("\nEnter the numbers of the AppImages you want to update (comma-separated):")
        print("For example: 1,3,4 or 'all' for all apps, or 'cancel' to exit")

        user_input = input("> ").strip().lower()

        if user_input == "cancel":
            logging.info("Update cancelled by user")
            print("Update cancelled.")
            return

        if user_input == "all":
            logging.info("User selected to update all apps")
            self._update_apps(updatable_apps)
            return

        try:
            # Parse user selection
            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]

            # Validate indices
            if any(idx < 0 or idx >= len(updatable_apps) for idx in selected_indices):
                logging.warning("Invalid app selection indices")
                print("Invalid selection. Please enter valid numbers.")
                return

            # Create list of selected apps
            selected_apps = [updatable_apps[idx] for idx in selected_indices]

            if selected_apps:
                logging.info(f"User selected {len(selected_apps)} apps to update")
                print(f"Updating {len(selected_apps)} selected AppImages...")
                self._update_apps(selected_apps)
            else:
                logging.info("No apps selected for update")
                print("No apps selected for update.")

        except ValueError:
            logging.warning("Invalid input format for app selection")
            print("Invalid input. Please enter numbers separated by commas.")

    def _update_apps(self, apps_to_update: List[Dict[str, Any]]) -> None:
        """
        Update the specified apps.

        Args:
            apps_to_update: List of app information dictionaries to update
        """
        total_apps = len(apps_to_update)
        is_batch = total_apps > 1

        success_count = 0
        failure_count = 0

        for index, app_data in enumerate(apps_to_update, 1):
            print(f"\n[{index}/{total_apps}] Processing {app_data['name']}...")
            success = self._update_single_app(app_data, is_batch=is_batch)

            if success:
                success_count += 1
            else:
                failure_count += 1

        # Print summary
        print("\n=== Update Summary ===")
        print(f"Total apps processed: {total_apps}")
        print(f"Successfully updated: {success_count}")
        if failure_count > 0:
            print(f"Failed updates: {failure_count}")
        print("Update process completed!")
