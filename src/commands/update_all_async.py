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
from typing import Any

from src.auth_manager import GitHubAuthManager
from src.commands.update_base import BaseUpdateCommand
from src.utils import ui_utils


class UpdateAsyncCommand(BaseUpdateCommand):
    """Command to update multiple AppImages concurrently using async I/O.

    This class extends the BaseUpdateCommand to provide asynchronous update
    capabilities, allowing multiple AppImages to be updated in parallel for
    improved performance.

    Attributes:
        _logger (logging.Logger): Logger instance for this class

    """

    def __init__(self) -> None:
        """Initialize with base configuration and async-specific settings."""
        super().__init__()
        # Logger for this class
        self._logger = logging.getLogger(__name__)

        # The max_concurrent_updates value is initialized from the global config
        # that was already loaded in BaseUpdateCommand.__post_init__()

    def execute(self) -> None:
        """Main update execution flow with asynchronous processing.

        This method orchestrates the async update process:
        1. Loads configuration and checks for available AppImages
        2. Verifies GitHub API rate limits before proceeding
        3. Finds updatable apps through user selection
        4. Manages concurrent update operations
        5. Displays progress and results
        """
        try:
            # Get available configuration files
            available_files = self.app_config.list_json_files()

            if not available_files:
                logging.warning("No AppImage configuration files found")
                print("No AppImage configuration files found. Use the Download option first.")
                return

            # Check current rate limits before any API operations
            raw_remaining, raw_limit, reset_time, is_authenticated = (
                GitHubAuthManager.get_rate_limit_info()
            )
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
                return

            # Show a warning if rate limits are low but don't prevent user from proceeding
            if remaining < 10:  # Now an int comparison
                print("\n--- GitHub API Rate Limit Warning ---")
                print(f"⚠️ Low API requests remaining: {remaining}/{limit}")
                if reset_time:
                    print(f"Limits reset at: {reset_time}")

                if not is_authenticated:
                    print(
                        "\n🔑 Consider adding a GitHub token using option 7 in the main menu to increase rate limits (5000/hour)."
                    )

                print(
                    "\nYou can still proceed, but you may not be able to update all selected apps."
                )
                print("Consider selecting fewer apps or only the most important ones.\n")

                # Give user a chance to abort
                try:
                    if input("Do you want to continue anyway? [y/N]: ").strip().lower() != "y":
                        print("Operation cancelled.")
                        return
                except KeyboardInterrupt:
                    print("\nOperation cancelled.")
                    return

            # 1. Find updatable apps via user selection
            updatable = self._find_updatable_apps()
            if not updatable:
                logging.info("No AppImages selected for update or all are up to date")
                return

            # 2. Get user confirmation
            if not self._confirm_updates(updatable):
                logging.info("Update cancelled by user")
                print("Update cancelled")
                return

            # 3. Check if we have enough rate limits for the selected apps
            can_proceed, filtered_apps, status_message = self._check_rate_limits(updatable)

            if not can_proceed:
                # Display rate limit status
                print("\n--- GitHub API Rate Limit Check ---")
                print(status_message)

                if not filtered_apps:
                    logging.warning("Update aborted: Insufficient API rate limits")
                    print("Update process aborted due to rate limit constraints.")
                    return

                # Ask user if they want to proceed with partial updates
                try:
                    continue_partial = (
                        input(
                            f"\nProceed with partial update ({len(filtered_apps)}/{len(updatable)} apps)? [y/N]: "
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

                # User confirmed - proceed with partial update
                updatable = filtered_apps
                print(f"\nProceeding with update of {len(updatable)} apps within rate limits.")

            # 4. Perform async updates
            self._perform_async_updates(updatable)

        except KeyboardInterrupt:
            logging.info("Operation cancelled by user (Ctrl+C)")
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
            List[Dict[str, Any]]: A list of updatable application information dictionaries

        """
        updatable_apps = []

        # Let user select which config files to check
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

    def _confirm_updates(self, updatable: list[dict[str, Any]]) -> bool:
        """Handle user confirmation based on batch mode.

        Args:
            updatable: List of updatable app information dictionaries

        Returns:
            bool: True if updates are confirmed, False otherwise

        """
        if self.global_config.batch_mode:
            self._logger.info("Batch mode: Auto-confirming updates")
            print("Batch mode: Auto-confirming updates")
            return True

        # Display list of apps to update
        print(f"\nFound {len(updatable)} apps to update:")
        print("-" * 60)
        print("# | App                  | Current      | Latest")
        print("-" * 60)

        for idx, app in enumerate(updatable, 1):
            print(f"{idx:<2}| {app['name']:<20} | {app['current']:<12} | {app['latest']}")

        print("-" * 60)

        try:
            return input("\nProceed with updates? [y/N]: ").strip().lower() == "y"
        except KeyboardInterrupt:
            self._logger.info("Confirmation cancelled by user (Ctrl+C)")
            print("\nConfirmation cancelled by user (Ctrl+C)")
            return False

    def _check_rate_limits(
        self, apps: list[dict[str, Any]]
    ) -> tuple[bool, list[dict[str, Any]], str]:
        """Check if we have enough API rate limits for the selected apps.

        This method:
        1. Gets current GitHub API rate limits
        2. Estimates required requests per app (2-3 typically)
        3. Determines if there are enough rate limits for all selected apps
        4. If not, filters to apps that can be processed within limits

        Args:
            apps: List of app information dictionaries

        Returns:
            Tuple containing:
            - bool: True if we can proceed with all apps, False if partial/no update needed
            - List[Dict[str, Any]]: Filtered list of apps that can be processed
            - str: Status message explaining the rate limit situation

        """
        # Get current rate limit info
        raw_remaining, raw_limit, reset_time, is_authenticated = (
            GitHubAuthManager.get_rate_limit_info()
        )
        try:
            remaining = int(raw_remaining)
            limit = int(raw_limit)
        except (ValueError, TypeError):
            self._logger.error(
                "Could not parse rate limit values: remaining=%s, limit=%s",
                raw_remaining,
                raw_limit,
            )
            return False, [], "Error: Could not determine API rate limits."

        # For each app, we need approximately:
        # - 1 API call to fetch releases
        # - 1 API call to get version info
        # - Potentially 1 more if we need additional info (uncommon)
        # Using 3 as a conservative estimate to be safe
        requests_per_app = 3

        # Calculate total required requests
        required_requests = len(apps) * requests_per_app

        # Check if we have enough remaining
        if remaining >= required_requests:
            # We have enough rate limits for all apps
            return (
                True,
                apps,
                f"Sufficient API rate limits: {remaining} remaining, {required_requests} required",
            )

        # Not enough for all apps - calculate how many we can process
        processable_apps_count = remaining // requests_per_app
        filtered_apps = []

        if processable_apps_count > 0:
            # Take only as many apps as we can process with available rate limits
            filtered_apps = apps[:processable_apps_count]
            status = (
                f"⚠️ Insufficient API rate limits for all apps.\n"
                f"Rate limits: {remaining}/{limit} remaining\n"
                f"Total required: {required_requests} ({requests_per_app} per app × {len(apps)} apps)\n"
                f"Can process: {processable_apps_count}/{len(apps)} apps with current rate limits"
            )

            if reset_time:
                status += f"\nLimits reset at: {reset_time}"

            if not is_authenticated:
                status += (
                    "\n\n🔑 Adding a GitHub token would increase your rate limit to 5000/hour."
                )
        else:
            # Can't process any apps with current rate limits
            status = (
                f"❌ Insufficient API rate limits.\n"
                f"Rate limits: {remaining}/{limit} remaining\n"
                f"Required: {required_requests} ({requests_per_app} per app × {len(apps)} apps)\n"
                f"Cannot process any apps with current rate limits."
            )

            if reset_time:
                status += f"\nLimits reset at: {reset_time}"

            if not is_authenticated:
                status += (
                    "\n\n🔑 Adding a GitHub token would increase your rate limit to 5000/hour."
                )

        return False, filtered_apps, status

    def _perform_async_updates(self, apps_to_update: list[dict[str, Any]]) -> None:
        """Perform async updates using the base class functionality.

        This method sets up the event loop and calls the base class async update
        method, then displays the results in a format suitable for this command.

        Args:
            apps_to_update: List of app information dictionaries to update

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

            # Set the main event loop in ui_utils
            ui_utils.set_main_event_loop(loop)

            print("Asynchronous update started")

            # Use the base class async update method
            success_count, failure_count, results = loop.run_until_complete(
                super()._update_apps_async(apps_to_update)
            )

            # Show completion message
            print("\n=== Update Summary ===")
            print(f"Total apps processed: {success_count + failure_count}/{len(apps_to_update)}")
            print(f"Successfully updated: {success_count}")

            if failure_count > 0:
                print(f"Failed updates: {failure_count}")

                # List failed updates
                failed_apps = []
                for app_name, result in results.items():
                    if result.get("status") != "success":
                        message = result.get("message", "Unknown error")
                        print(f"  - {app_name}: {message}")
                        failed_apps.append(app_name)

            print("\nUpdate process completed!")

            # Batch prompt to remove downloaded files for failed updates
            if failure_count > 0 and failed_apps:
                from src.utils.cleanup_utils import cleanup_batch_failed_updates

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
            self._display_rate_limit_info()

        except KeyboardInterrupt:
            print("\nUpdate process cancelled by user (Ctrl+C)")
        except Exception as e:
            print(f"\nError in update process: {e!s}")

    def _display_rate_limit_info(self) -> None:
        """Display GitHub API rate limit information after updates using standard print statements."""
        try:
            # Use the cached rate limit info to avoid unnecessary API calls
            raw_remaining, raw_limit, reset_time, is_authenticated = (
                GitHubAuthManager.get_rate_limit_info()
            )
            try:
                remaining = int(raw_remaining)
                limit = int(raw_limit)
            except (ValueError, TypeError):
                return

            print("\n--- GitHub API Rate Limits ---")
            print(
                f"Remaining requests: {remaining}/{limit} ({'authenticated' if is_authenticated else 'unauthenticated'})"
            )

            if reset_time:
                print(f"Resets at: {reset_time}")

            if remaining < (100 if is_authenticated else 20):
                if remaining < 100 and is_authenticated:
                    print("⚠️ Running low on API requests!")
                elif remaining < 20 and not is_authenticated:
                    print("⚠️ Low on unauthenticated requests!")
                    print("Tip: Add a GitHub token to increase rate limits (5000/hour).")

            print("Note: Rate limit information is an estimate based on usage since last refresh.")

        except Exception:
            # Silently handle any errors to avoid breaking update completion
            pass
