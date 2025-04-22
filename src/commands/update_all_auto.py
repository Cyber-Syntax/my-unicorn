#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto update command module.

This module provides a command to automatically check and update all AppImages
without requiring manual selection of each app.
"""

import logging
import os
import sys
from typing import List, Dict, Any

from src.commands.update_base import BaseUpdateCommand
from src.auth_manager import GitHubAuthManager


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

        try:
            # Load global configuration
            self.global_config.load_config()

            # Check rate limits before proceeding with any API operations
            # Get current rate limit information
            remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

            # Calculate minimum requests needed (at least one per app config)
            json_files = self._list_all_config_files()
            if not json_files:
                logging.warning("No AppImage configuration files found")
                print("No AppImage configuration files found. Use the Download option first.")
                return

            # Each app will need at least one request
            min_requests_needed = len(json_files)

            # Check if we have enough requests to at least check all apps
            if remaining < min_requests_needed:
                logging.error(
                    f"Insufficient API requests to check all apps: {remaining}/{min_requests_needed} available"
                )
                print("\n--- GitHub API Rate Limit Warning ---")
                print(f"⚠️  Not enough API requests available to check all apps!")
                print(
                    f"Rate limit status: {remaining}/{limit} requests remaining{' (authenticated)' if is_authenticated else ' (unauthenticated)'}"
                )

                if reset_time:
                    print(f"Limits reset at: {reset_time}")

                print(f"Minimum requests required: {min_requests_needed} (one per app config)")

                if not is_authenticated:
                    print(
                        "\n🔑 Please add a GitHub token using option 6 in the main menu to increase rate limits (5000/hour)."
                    )

                print("\nPlease try again later when more API requests are available.")
                return

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
        except KeyboardInterrupt:
            logging.info("Operation cancelled by user (Ctrl+C)")
            print("\nOperation cancelled by user (Ctrl+C)")
            return

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

                    # Directly check version without redirecting output
                    app_data = self._check_single_app_version(self.app_config, config_file)

                    if app_data:
                        print(
                            f"{app_name}: update available: {app_data['current']} → {app_data['latest']}"
                        )
                        updatable_apps.append(app_data)
                    else:
                        print(f"{app_name}: already up to date")

                except Exception as e:
                    error_msg = f"Error checking {config_file}: {str(e)}"
                    logging.error(error_msg)
                    print(f"{app_name}: error: {str(e)}")
                except KeyboardInterrupt:
                    logging.info("Update check cancelled by user (Ctrl+C)")
                    print("\nUpdate check cancelled by user (Ctrl+C)")
                    return updatable_apps

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

        try:
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
                    self._update_apps(selected_apps)
                else:
                    logging.info("No apps selected for update")
                    print("No apps selected for update.")

            except ValueError:
                logging.warning("Invalid input format for app selection")
                print("Invalid input. Please enter numbers separated by commas.")
        except KeyboardInterrupt:
            logging.info("Selection cancelled by user (Ctrl+C)")
            print("\nSelection cancelled by user (Ctrl+C)")
            return

    def _update_apps(self, apps_to_update: List[Dict[str, Any]]) -> None:
        """
        Update the specified apps with rate limit awareness.

        Args:
            apps_to_update: List of app information dictionaries to update
        """
        logging.info(f"Checking rate limits before updating {len(apps_to_update)} AppImages")

        # Check if we have enough API requests available
        can_proceed, filtered_apps, status_message = self._check_rate_limits(apps_to_update)

        # Display rate limit status
        print("\n--- GitHub API Rate Limit Check ---")
        print(status_message)

        if not can_proceed:
            if not filtered_apps:
                logging.warning("Update aborted: Insufficient API rate limits")
                print("Update process aborted due to rate limit constraints.")
                return

            # Ask user if they want to proceed with partial updates
            if not self.global_config.batch_mode:
                try:
                    continue_partial = (
                        input(
                            f"\nProceed with partial update ({len(filtered_apps)}/{len(apps_to_update)} apps)? [y/N]: "
                        )
                        .strip()
                        .lower()
                        == "y"
                    )

                    if not continue_partial:
                        logging.info("User declined partial update")
                        print("Update cancelled.")
                        return
                except KeyboardInterrupt:
                    logging.info("Rate limit confirmation cancelled by user (Ctrl+C)")
                    print("\nUpdate cancelled by user (Ctrl+C)")
                    return

            # Batch mode or user confirmed - proceed with partial update
            apps_to_update = filtered_apps
            print(f"\nProceeding with update of {len(apps_to_update)} apps within rate limits.")

        # Continue with the regular update process
        logging.info(f"Beginning update of {len(apps_to_update)} AppImages")
        total_apps = len(apps_to_update)
        success_count = 0
        failure_count = 0

        try:
            # Process each app one by one
            for index, app_data in enumerate(apps_to_update, 1):
                try:
                    success = self._update_single_app(app_data, is_batch=(len(apps_to_update) > 1))
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except KeyboardInterrupt:
                    logging.info(f"Update of {app_data['name']} cancelled by user (Ctrl+C)")
                    print(f"\nUpdate of {app_data['name']} cancelled by user (Ctrl+C)")
                    failure_count += 1
                    # Ask if user wants to continue with remaining apps
                    if index < total_apps and total_apps > 1:
                        try:
                            continue_update = (
                                input("\nContinue with remaining updates? (y/N): ").strip().lower()
                                == "y"
                            )
                            if not continue_update:
                                logging.info("Remaining updates cancelled by user")
                                print("Remaining updates cancelled.")
                                break
                        except KeyboardInterrupt:
                            logging.info("All updates cancelled by user (Ctrl+C)")
                            print("\nAll updates cancelled by user (Ctrl+C)")
                            break

            # Show completion message
            print("\n=== Update Summary ===")
            print(f"Total apps processed: {success_count + failure_count}/{total_apps}")
            print(f"Successfully updated: {success_count}")
            if failure_count > 0:
                print(f"Failed/cancelled updates: {failure_count}")
            print("Update process completed!")

            # Display updated rate limit information after updates
            self._display_rate_limit_info()
        except KeyboardInterrupt:
            logging.info("Update process cancelled by user (Ctrl+C)")
            print("\nUpdate process cancelled by user (Ctrl+C)")
            if success_count > 0 or failure_count > 0:
                print("\n=== Partial Update Summary ===")
                print(f"Total apps processed: {success_count + failure_count}/{total_apps}")
                print(f"Successfully updated: {success_count}")
                if failure_count > 0:
                    print(f"Failed/cancelled updates: {failure_count}")
            print("Update process interrupted!")
