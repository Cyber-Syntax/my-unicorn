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

import asyncio
import logging
from pathlib import Path
from typing import Any

from my_unicorn.auth_manager import GitHubAuthManager
from my_unicorn.commands.update_base import BaseUpdateCommand
from my_unicorn.download import DownloadManager
from my_unicorn.utils import ui_utils


class UpdateAsyncCommand(BaseUpdateCommand):
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

    def execute(self) -> None:
        """Main update execution flow with asynchronous processing.

        This method orchestrates the async update process:
        1. Loads configuration and checks for available AppImages
        2. Verifies GitHub API rate limits before proceeding
        3. Finds updatable_apps apps through user selection
        4. Manages concurrent update operations
        5. Displays progress and results
        """
        try:
            # 1. Find updatable_apps apps via user selection
            updatable_apps = self._find_updatable_apps()
            if not updatable_apps:
                self._logger.info("No AppImages selected for update or all are up to date")
                return

            # 2. Get user confirmation
            if not self._confirm_updates(updatable_apps):
                self._logger.info("Update cancelled by user")
                print("Update cancelled")
                return

            # 3. Check if we have enough rate limits for the selected apps
            can_proceed, filtered_apps, status_message = self.check_rate_limits(updatable_apps)

            if not can_proceed:
                # Display rate limit status
                print("\n--- GitHub API Rate Limit Check ---")
                print(status_message)

                if not filtered_apps:
                    self._logger.warning("Update aborted: Insufficient API rate limits")
                    print("Update process aborted due to rate limit constraints.")
                    return

                # Ask user if they want to proceed with partial updates
                try:
                    continue_partial = (
                        input(
                            f"\nProceed with partial update ({len(filtered_apps)}/{len(updatable_apps)} apps)? [y/N]: "
                        )
                        .strip()
                        .lower()
                        == "y"
                    )

                    if not continue_partial:
                        self._logger.info("User declined partial update")
                        print("Update cancelled.")
                        return
                except KeyboardInterrupt:
                    self._logger.info("Rate limit confirmation cancelled by user (Ctrl+C)")
                    print("\nUpdate cancelled by user (Ctrl+C)")
                    return

                # User confirmed - proceed with partial update
                updatable_apps = filtered_apps
                print(f"\nProceeding with update of {len(updatable_apps)} apps within rate limits.")

            # 4. Perform async updates
            self._perform_async_updates(updatable_apps)

        except KeyboardInterrupt:
            self._logger.info("Operation cancelled by user (Ctrl+C)")
            print("\nOperation cancelled by user (Ctrl+C)")
            return
        except Exception as e:
            self._logger.error("Unexpected error in async update: %s", str(e), exc_info=True)
            print(f"\nUnexpected error: {e!s}")
            return

    def _find_updatable_apps(self) -> list[dict[str, Any]]:
        """Find applications that can be updated through user selection.

        This method handles rate limits during the scanning process by:
        1. Checking available rate limits before API calls
        2. Providing feedback about which apps could be checked
        3. Allowing users to make informed decisions about which apps to update

        Returns:
            list[tuple[str, Any]]: A list of updatable_apps application information dictionaries

        """
        updatable_apps = []

        # Use predefined app names if provided, otherwise use interactive selection
        if self._predefined_app_names:
            selected_files = self._select_files_by_names(self._predefined_app_names)
        else:
            selected_files = self.app_config.select_files()

        if not selected_files:
            print("No configuration files selected or available.")
            return updatable_apps

        # Check current rate limits before making API calls
        raw_remaining, raw_limit, reset_time, is_authenticated = (
            GitHubAuthManager.get_rate_limit_info()
        )

        # Parse rate limit values
        try:
            remaining = int(raw_remaining)
            limit = int(raw_limit)
        except (ValueError, TypeError):
            self._logger.error(
                "Could not parse rate limit values: remaining=%s, limit=%s",
                raw_remaining,
                raw_limit,
            )
            print("Error: Could not determine API rate limits. Cannot proceed.")
            return []

        # If we have fewer requests than selected files, warn the user
        if remaining < len(selected_files):  # Now an int comparison
            print("\n--- GitHub API Rate Limit Warning ---")
            print("⚠️ Not enough API requests to check all selected apps.")
            print(f"Rate limit status: {remaining}/{limit} requests remaining")
            if reset_time:
                print(f"Limits reset at: {reset_time}")

            print(f"Selected apps: {len(selected_files)}")
            print(f"Available requests: {remaining}")

            if not is_authenticated:
                print(
                    "\n🔑 Consider adding a GitHub token using option 7 in the main menu to increase rate limits."
                )

            print("\nSome API requests will fail. Consider:")
            print("1. Selecting fewer apps")
            print("2. Adding a GitHub token")
            print("3. Waiting until rate limits reset")

            # Handle the case where we have 0 remaining requests
            if remaining == 0:
                print("\n❌ ERROR: No API requests available.")
                print("Please wait until rate limits reset or add a GitHub token.")
                self._logger.error("Update aborted: No API requests available (0 remaining)")
                return []

            # Ask user what to do
            try:
                choice = input(
                    "\nHow do you want to proceed?\n"
                    "1. Continue with all selected apps (some may fail)\n"
                    "2. Limit to available API requests\n"
                    "3. Cancel operation\n"
                    "Enter choice [1-3]: "
                ).strip()

                if choice == "2":
                    # Limit selection to available requests
                    limited_files = selected_files[:remaining]
                    # If this results in 0 files, abort with a clear message
                    if not limited_files:
                        print("\n❌ ERROR: Cannot proceed with 0 apps.")
                        print("Please wait until rate limits reset or add a GitHub token.")
                        self._logger.error("Update aborted: Rate limits allow 0 apps")
                        return []

                    selected_files = limited_files
                    print(
                        f"\nLimited selection to {len(selected_files)} apps based on available API requests."
                    )
                elif choice == "3":
                    print("Operation cancelled.")
                    return []
                else:
                    # Default to continuing with all selected (some will fail)
                    print("\nProceeding with all selected apps. Some API requests may fail.")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return []

        # Check each selected file for updates with progress indication
        print(f"\nChecking {len(selected_files)} selected apps for updates...")
        print("-" * 60)

        failed_checks = 0
        checked_count = 0

        for idx, config_file in enumerate(selected_files, 1):
            app_name = config_file.split(".")[0]  # Extract name without extension
            status_msg = f"Checking {app_name} ({idx}/{len(selected_files)})..."
            print(f"{status_msg}", end="\r")

            try:
                app_data = self._check_single_app_version(self.app_config, config_file)
                checked_count += 1

                if app_data:
                    if "error" in app_data:
                        print(f"{app_name}: Error: {app_data['error']}" + " " * 20)
                        failed_checks += 1
                    else:
                        print(
                            f"{app_name}: Update available: {app_data['current']} → {app_data['latest']}"
                            + " " * 20
                        )
                        updatable_apps.append(app_data)
                else:
                    print(f"{app_name}: Already up to date" + " " * 20)
            except Exception as e:
                print(f"{app_name}: Failed: {e!s}" + " " * 20)
                failed_checks += 1
                # If we hit rate limits, provide clear feedback
                if "rate limit exceeded" in str(e).lower():
                    print("\n⚠️ GitHub API rate limit exceeded. Cannot check remaining apps.")
                    print("Consider adding a GitHub token or waiting until rate limits reset.")
                    break

        # Summary of check results
        if not selected_files:
            print("\nNo apps were checked due to rate limit constraints.")
        else:
            print("\n--- Check Summary ---")
            print(f"✓ Updates available: {len(updatable_apps)}")
            print(f"✗ Checks failed: {failed_checks}")
            print(f"Total checked: {checked_count}/{len(selected_files)}")

        return updatable_apps

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

    def _perform_async_updates(self, apps_to_update: list[dict[str, Any]]) -> None:
        """Perform async updates using the base class functionality.

        This method sets up the event loop and calls the base class async update
        method, then displays the results in a format suitable for this command.

        Args:
            apps_to_update: list of app information dictionaries to update

        """
        try:
            print(
                f"\nUpdating {len(apps_to_update)} AppImages concurrently (max {self.max_concurrent_updates} at once)..."
            )

            # Get or create the event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # set the main event loop in ui_utils
            ui_utils.set_main_event_loop(loop)

            print("Asynchronous update started")

            # Initialize progress manager for all downloads
            DownloadManager.get_or_create_progress(len(apps_to_update))

            # Use the base class async update method
            success_count, failure_count, results = loop.run_until_complete(
                super()._update_apps_async(apps_to_update)
            )

            # Clean up progress manager after all downloads complete
            DownloadManager.stop_progress()

            # Show completion message
            print("\n=== Update Summary ===")
            print(
                f"Total apps processed: {success_count + failure_count}/{len(apps_to_update)}"
            )
            print(f"Successfully updated: {success_count}")

            # Show detailed messages for successful updates
            if success_count > 0:
                print("\nSuccessful updates:")
                for app_name, result in results.items():
                    if result.get("status") == "success":
                        # Show download message
                        download_msg = result.get("download_message", "")
                        if download_msg:
                            print(f"  {download_msg}")

                        # Show verification message
                        verification_msg = result.get("verification_message", "")
                        if verification_msg:
                            print(f"  {verification_msg}")

                        # Show success message
                        success_msg = result.get("success_message", "")
                        if success_msg:
                            print(f"  {success_msg}")
                        elif result.get("message"):
                            print(f"  ✓ {app_name} - {result.get('message')}")

            if failure_count > 0:
                print(f"\nFailed updates: {failure_count}")

                # list failed updates
                failed_apps = []
                for app_name, result in results.items():
                    if result.get("status") != "success":
                        message = result.get("message", "Unknown error")
                        elapsed = result.get("elapsed", 0)
                        print(f"  ✗ {app_name}: {message} ({elapsed:.1f}s)")
                        failed_apps.append(app_name)

            print("\nUpdate process completed!")

            # Batch prompt to remove downloaded files for failed updates
            if failure_count > 0 and failed_apps:
                from my_unicorn.utils.cleanup_utils import cleanup_batch_failed_updates

                try:
                    # Use the unified batch cleanup function
                    cleanup_batch_failed_updates(
                        failed_apps=failed_apps,
                        results=results,
                        ask_confirmation=True,
                        verbose=True,
                    )
                except KeyboardInterrupt:
                    print("\nCleanup cancelled.")

            # Display updated rate limit information after updates
            self.display_rate_limit_info()

        except KeyboardInterrupt:
            print("\nUpdate process cancelled by user (Ctrl+C)")
        except Exception as e:
            print(f"\nError in update process: {e!s}")
