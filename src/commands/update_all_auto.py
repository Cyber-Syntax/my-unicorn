#!/usr/bin/env python3
"""Auto update command module.

This module provides a command to automatically check and update all AppImages
without requiring manual selection of each app. Supports both synchronous and
asynchronous updates for improved performance.
"""

import asyncio
import logging
import os
from typing import Any  # Retained for compatibility with Any type

from src.auth_manager import GitHubAuthManager
from src.commands.update_base import BaseUpdateCommand


class UpdateAllAutoCommand(BaseUpdateCommand):
    """Command to automatically check and update all AppImages without manual selection."""

    def __init__(self):
        """Initialize with base configuration and async-specific settings."""
        super().__init__()

        # Note: max_concurrent_updates is already initialized in the BaseUpdateCommand constructor
        # and the global_config is already loaded in __post_init__

    def execute(self):
        """Check all AppImage configurations and update those with new versions available.

        This method automatically scans all available AppImage configurations and
        updates any that have newer versions available. By default, it uses the
        synchronous update method, but if async_mode is enabled, it will use
        the more efficient concurrent update approach.
        """
        logging.info("Starting automatic check of all AppImages")
        print("Checking all AppImages for updates...")

        try:
            # Use async mode by default - it's more efficient
            use_async = True

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
                print("⚠️  Not enough API requests available to check all apps!")
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
                if use_async:
                    self._update_apps_async_wrapper(updatable_apps)
                else:
                    self._update_apps(updatable_apps)
            else:
                # In interactive mode, ask which apps to update
                self._handle_interactive_update(updatable_apps, use_async)

        except KeyboardInterrupt:
            logging.info("Operation cancelled by user (Ctrl+C)")
            print("\nOperation cancelled by user (Ctrl+C)")
            return

    def _find_all_updatable_apps(self) -> list[dict[str, Any]]:
        """Find all AppImages that have updates available.

        Returns:
            list[tuple[str, Any]]: list of updatable app information dictionaries

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
                    error_msg = f"Error checking {config_file}: {e!s}"
                    logging.error(error_msg)
                    print(f"{app_name}: error: {e!s}")
                except KeyboardInterrupt:
                    logging.info("Update check cancelled by user (Ctrl+C)")
                    print("\nUpdate check cancelled by user (Ctrl+C)")
                    return updatable_apps

        except Exception as e:
            error_msg = f"Error during update check: {e!s}"
            logging.error(error_msg)
            print(error_msg)

        return updatable_apps

    def _list_all_config_files(self) -> list[str]:
        """Get a list of all AppImage configuration files.

        Returns:
            list[str]: list of configuration filenames

        """
        return self.app_config.list_json_files()

    def _handle_interactive_update(
        self, updatable_apps: list[dict[str, Any]], use_async: bool = False
    ) -> None:
        """Handle interactive mode where user selects which apps to update.

        Args:
            updatable_apps: list of updatable app information dictionaries
            use_async: Whether to use async update mode

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
                if use_async:
                    self._update_apps_async_wrapper(updatable_apps)
                else:
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
                    if use_async:
                        self._update_apps_async_wrapper(selected_apps)
                    else:
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

    def _update_apps_async_wrapper(self, apps_to_update: list[dict[str, Any]]) -> None:
        """Wrapper to call the async update method from a synchronous context.

        Args:
            apps_to_update: list of app information dictionaries to update

        """
        try:
            # Create a new event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            print(
                f"\nStarting asynchronous update of {len(apps_to_update)} AppImages (max {self.max_concurrent_updates} concurrent)..."
            )
            logging.info(
                f"Starting asynchronous update of {len(apps_to_update)} AppImages with concurrency limit {self.max_concurrent_updates}"
            )

            # Run the async function using the base class method
            success_count, failure_count, results = loop.run_until_complete(
                self._update_apps_async(apps_to_update)
            )

            # Display results
            self._display_async_results(success_count, failure_count, results, len(apps_to_update))

        except KeyboardInterrupt:
            logging.info("Update process cancelled by user (Ctrl+C)")
            print("\nUpdate process cancelled by user (Ctrl+C)")
        except Exception as e:
            logging.error(f"Error in async update process: {e!s}", exc_info=True)
            print(f"\nError in update process: {e!s}")

    def _display_async_results(
        self,
        success_count: int,
        failure_count: int,
        results: dict[str, dict[str, Any]],
        total_apps: int,
    ) -> None:
        """Display the results of async update operation.

        Args:
            success_count: Number of successful updates
            failure_count: Number of failed updates
            results: Dictionary mapping app names to their result data
            total_apps: Total number of apps processed

        """
        print("\n=== Update Summary ===")
        print(f"Total apps processed: {success_count + failure_count}/{total_apps}")
        print(f"Successfully updated: {success_count}")

        if failure_count > 0:
            print(f"Failed updates: {failure_count}")

            # list failed updates
            for app_name, result in results.items():
                if result.get("status") != "success":
                    message = result.get("message", "Unknown error")
                    print(f"  - {app_name}: {message}")

        print("\nUpdate process completed!")

        # Prompt to remove downloaded files for failed updates in batch
        if failure_count > 0:
            failed_apps = [name for name, res in results.items() if res.get("status") != "success"]

            from src.utils.cleanup_utils import cleanup_batch_failed_updates

            try:
                # Use the unified batch cleanup function
                cleanup_batch_failed_updates(
                    failed_apps=failed_apps, results=results, ask_confirmation=True, verbose=True
                )
            except KeyboardInterrupt:
                print("\nCleanup cancelled.")

        # Display updated rate limit information after updates
        self._display_rate_limit_info()

    def _update_apps(self, apps_to_update: list[dict[str, Any]]) -> None:
        """Update multiple apps synchronously.

        Args:
            apps_to_update: list of app information dictionaries to update

        """
        success_count = 0
        failure_count = 0

        for idx, app_data in enumerate(apps_to_update, 1):
            print(f"\n[{idx}/{len(apps_to_update)}] Updating {app_data['name']}...")
            result = self._update_single_app(app_data, is_batch=True)

            if result:
                success_count += 1
                logging.info(f"Successfully updated {app_data['name']}")
            else:
                failure_count += 1
                logging.error(f"Failed to update {app_data['name']}")

        print("\n=== Update Summary ===")
        print(f"Total apps processed: {success_count + failure_count}/{len(apps_to_update)}")
        print(f"Successfully updated: {success_count}")

        if failure_count > 0:
            print(f"Failed updates: {failure_count}")

        print("\nUpdate process completed!")

        # Display updated rate limit information after updates
        self._display_rate_limit_info()

    def _display_update_list(self, updatable_apps: list[dict[str, Any]]) -> None:
        """Display a list of updatable apps with standard print statements.

        Args:
            updatable_apps: list of updatable app information dictionaries

        """
        print(f"\nFound {len(updatable_apps)} apps to update:")
        print("-" * 60)
        print("# | App                  | Current      | Latest")
        print("-" * 60)

        for idx, app in enumerate(updatable_apps, 1):
            print(f"{idx:<2}| {app['name']:<20} | {app['current']:<12} | {app['latest']}")

        print("-" * 60)

    def _display_rate_limit_info(self) -> None:
        """Display GitHub API rate limit information after updates using standard print statements."""
        try:
            # Use the cached rate limit info to avoid unnecessary API calls
            remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

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

        except Exception as e:
            # Silently handle any errors to avoid breaking update completion
            logging.debug(f"Error displaying rate limit info: {e}")
