#!/usr/bin/env python3
"""Asynchronous update command module for concurrent AppImage updates.

This module provides a command to update multiple AppImages concurrently
using asynchronous I/O operations. It leverages Python's asyncio library
to perform parallel updates, significantly improving performance when
updating multiple apps simultaneously.

Key features:
- Concurrent updates with configurable parallelism
- Simple progress tracking during updates
- GitHub API rate limit awareness
- Graceful cancellation handling
- Update summaries
"""

import logging
from pathlib import Path
from typing import Any, override

from my_unicorn.commands.update_base import BaseUpdateCommand


class SelectiveUpdateCommand(BaseUpdateCommand):
    """Command to update multiple AppImages concurrently using async I/O.

    This class extends the BaseUpdateCommand to provide asynchronous update
    capabilities, allowing multiple AppImages to be updated in parallel for
    improved performance.

    Attributes:
        _logger (self._logger.Logger): Logger instance for this class

    """

    def __init__(self, app_names: list[str] | None = None) -> None:
        """Initialize with base configuration and async-specific settings.

        Args:
            app_names: Optional list of app names to update. If provided, these will be used
                      instead of interactive selection.

        """
        super().__init__()
        # Logger for this class
        self._logger = logging.getLogger(__name__)

        # Store predefined app names for CLI usage
        self._predefined_app_names = app_names

        # The max_concurrent_updates value is initialized from the global config
        # that was already loaded in BaseUpdateCommand.__post_init__()

    @override
    def execute(self) -> None:
        """Execute the update process with selective asynchronous updates.

        This method checks all selected AppImages for updates and updates them asynchronously.
        """
        try:
            # Use predefined app names if provided, otherwise use interactive selection
            if self._predefined_app_names:
                selected_files = self._select_files_by_names(self._predefined_app_names)
            else:
                selected_files = self.app_config.select_files()

            # 1. Find updatable_apps apps via user selection
            updatable_apps = self.find_updatable_apps(selected_files)
            if not updatable_apps:
                self._logger.info("No AppImages selected for update or all are up to date")
                return

            # 2. Get user confirmation
            if not self._confirm_updates(updatable_apps):
                self._logger.info("Update cancelled by user")
                print("Update cancelled")
                return

            # 3. Check if we have enough rate limits for the selected apps
            self.check_rate_limits(updatable_apps)

            # 4. Perform async updates
            self.update_apps_async_wrapper(updatable_apps)

        except KeyboardInterrupt:
            self._logger.info("Operation cancelled by user (Ctrl+C)")
            print("\nOperation cancelled by user (Ctrl+C)")
            return
        except Exception as e:
            self._logger.error("Unexpected error in async update: %s", str(e), exc_info=True)
            print(f"\nUnexpected error: {e!s}")
            return

    def _select_files_by_names(self, app_names: list[str]) -> list[str]:
        """Select configuration files based on provided app names.

        Args:
            app_names: List of app names to select

        Returns:
            list[str]: List of JSON configuration file names that match the app names

        """
        available_files = self.app_config.list_json_files()
        if not available_files:
            print("No configuration files found.")
            return []

        # Create a mapping of lowercase app names to actual file names for case-insensitive matching
        available_apps_map = {Path(f).stem.lower(): f for f in available_files}

        selected_files = []
        missing_apps = []

        for app_name in app_names:
            # Look for matching JSON file (case-insensitive)
            app_name_lower = app_name.strip().lower()
            if app_name_lower in available_apps_map:
                selected_files.append(available_apps_map[app_name_lower])
            else:
                missing_apps.append(app_name)

        if missing_apps:
            print(f"Warning: The following apps were not found: {', '.join(missing_apps)}")
            print("Available apps:", ", ".join([Path(f).stem for f in available_files]))

        if selected_files:
            print(f"Selected apps: {', '.join([Path(f).stem for f in selected_files])}")

        return selected_files

    def _confirm_updates(self, updatable_apps: list[dict[str, Any]]) -> bool:
        """Handle user confirmation based on batch mode.

        Args:
            updatable_apps: list of updatable_apps app information dictionaries

        Returns:
            bool: True if updates are confirmed, False otherwise

        """
        if self.global_config.batch_mode:
            self._logger.info("Batch mode: Auto-confirming updates")
            print("Batch mode: Auto-confirming updates")
            return True

        # Display list of apps to update
        print(f"\nFound {len(updatable_apps)} apps to update:")
        print("-" * 60)
        print("# | App                  | Current      | Latest")
        print("-" * 60)

        for idx, app in enumerate(updatable_apps, 1):
            print(f"{idx:<2}| {app['name']:<20} | {app['current']:<12} | {app['latest']}")

        print("-" * 60)

        try:
            return input("\nProceed with updates? [y/N]: ").strip().lower() == "y"
        except KeyboardInterrupt:
            self._logger.info("Confirmation cancelled by user (Ctrl+C)")
            print("\nConfirmation cancelled by user (Ctrl+C)")
            return False
