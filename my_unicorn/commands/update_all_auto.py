#!/usr/bin/env python3
"""Auto update command module.

This module provides a command to automatically check and update all AppImages
without requiring manual selection of each app. Supports both synchronous and
asynchronous updates for improved performance.
"""

import logging
from typing import Any

from my_unicorn.commands.update_base import BaseUpdateCommand

logger = logging.getLogger(__name__)


class AutoUpdateCommand(BaseUpdateCommand):
    """Command to automatically check and update all AppImages without manual selection."""

    def execute(self):
        """Check all AppImage configurations and update those with new versions available.

        This method automatically scans all available AppImage configurations and
        updates any that have newer versions available.
        """
        logger.info("Starting automatic check of all AppImages")
        print("Checking all AppImages for updates...")

        try:
            updatable_apps = self.find_updatable_apps()

            if not updatable_apps:
                logger.info("All AppImages are up to date")
                print("All AppImages are up to date!")
                return

            self.check_rate_limits(updatable_apps)

            self._display_update_list(updatable_apps)

            # Determine what to do based on batch mode
            if self.global_config.batch_mode:
                logger.info(
                    "Batch mode enabled - updating all %d AppImages automatically",
                    len(updatable_apps),
                )
                print(
                    f"Batch mode enabled - updating all {len(updatable_apps)} "
                    f"AppImages automatically"
                )
                self.update_apps_async_wrapper(updatable_apps)
            else:
                # ask which apps to update
                self._handle_interactive_update(updatable_apps)

        except KeyboardInterrupt:
            logger.info("Operation cancelled by user (Ctrl+C)")
            print("\nOperation cancelled by user (Ctrl+C)")
            return

    def _handle_interactive_update(self, updatable_apps: list[dict[str, Any]]) -> None:
        """Handle interactive mode where user selects which apps to update.

        Args:
            updatable_apps: list of updatable app information dictionaries

        """
        print("\nEnter the numbers of the AppImages you want to update (comma-separated):")
        print("For example: 1,3,4 or 'all' for all apps, or 'cancel' to exit")

        try:
            user_input = input("> ").strip().lower()

            if user_input == "cancel":
                logger.info("Update cancelled by user")
                print("Update cancelled.")
                return

            if user_input == "all":
                logger.info("User selected to update all apps")
                self.update_apps_async_wrapper(updatable_apps)

                try:
                    # Parse user selection
                    selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]

                    # Validate indices
                    if any(idx < 0 or idx >= len(updatable_apps) for idx in selected_indices):
                        logger.warning("Invalid app selection indices")
                        print("Invalid selection. Please enter valid numbers.")
                        return

                    # Create list of selected apps
                    selected_apps = [updatable_apps[idx] for idx in selected_indices]

                    if selected_apps:
                        logger.info("User selected %d apps to update", len(selected_apps))
                        self.update_apps_async_wrapper(selected_apps)
                    else:
                        logger.info("No apps selected for update")
                        print("No apps selected for update.")

                except ValueError:
                    logger.warning("Invalid input format for app selection")
                    print("Invalid input. Please enter numbers separated by commas.")
        except KeyboardInterrupt:
            logger.info("Selection cancelled by user (Ctrl+C)")
            print("\nSelection cancelled by user (Ctrl+C)")
            return

    def _display_update_list(self, updatable_apps: list[dict[str, Any]]) -> None:
        """Display list of apps to update."""
        print(f"\nFound {len(updatable_apps)} apps to update:")
        for idx, app in enumerate(updatable_apps, start=1):
            self._logger.info(
                "%d. %s (%s → %s)", idx, app["name"], app["current"], app["latest"]
            )
            update_msg = f"{idx}. {app['name']} ({app['current']} → {app['latest']})"
            print(update_msg)
