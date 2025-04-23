#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto update command module.

This module provides a command to automatically check and update all AppImages
without requiring manual selection of each app. Supports both synchronous and
asynchronous updates for improved performance.
"""

import logging
import os
import sys
import asyncio
from typing import List, Dict, Any, Optional, Tuple

from rich.console import Console
from rich.table import Table

from src.commands.update_base import BaseUpdateCommand
from src.auth_manager import GitHubAuthManager


class UpdateAllAutoCommand(BaseUpdateCommand):
    """Command to automatically check and update all AppImages without manual selection."""

    def __init__(self):
        """Initialize with base configuration and async-specific settings."""
        super().__init__()
        self.console = Console()

        # Note: max_concurrent_updates is already initialized in the BaseUpdateCommand constructor
        # and the global_config is already loaded in __post_init__

    def execute(self):
        """
        Check all AppImage configurations and update those with new versions available.

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

    def _handle_interactive_update(
        self, updatable_apps: List[Dict[str, Any]], use_async: bool = False
    ) -> None:
        """
        Handle interactive mode where user selects which apps to update.

        Args:
            updatable_apps: List of updatable app information dictionaries
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

    def _update_apps_async_wrapper(self, apps_to_update: List[Dict[str, Any]]) -> None:
        """
        Wrapper to call the async update method from a synchronous context.

        Args:
            apps_to_update: List of app information dictionaries to update
        """
        try:
            # Create a new event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Create a semaphore to limit concurrency - use max_concurrent_updates from base class
            self.semaphore = asyncio.Semaphore(self.max_concurrent_updates)

            print(
                f"\nStarting asynchronous update of {len(apps_to_update)} AppImages (max {self.max_concurrent_updates} concurrent)..."
            )

            # Run the async update method
            success_count, failure_count, results = loop.run_until_complete(
                self._update_apps_async(apps_to_update)
            )

            # Show completion message with Rich
            table = Table(title="Update Results")
            table.add_column("App", style="cyan")
            table.add_column("Result", style="bold")
            table.add_column("Details", style="dim")
            table.add_column("Time", style="blue")

            for result in results:
                app_name = result["app"]["name"]
                result_data = result["result"]
                status = result_data["status"]

                if status == "success":
                    result_style = "green"
                    result_text = "✓ Success"
                elif status == "failed":
                    result_style = "red"
                    result_text = "✗ Failed"
                else:
                    result_style = "yellow"
                    result_text = "! Error"

                table.add_row(
                    app_name,
                    f"[{result_style}]{result_text}[/{result_style}]",
                    result_data.get("message", ""),
                    f"{result_data.get('elapsed', 0):.1f}s",
                )

            self.console.print(table)

            # Show summary
            self.console.print("\n=== Update Summary ===")
            self.console.print(
                f"Total apps processed: {success_count + failure_count}/{len(apps_to_update)}"
            )
            self.console.print(f"[green]Successfully updated: {success_count}[/]")
            if failure_count > 0:
                self.console.print(f"[red]Failed updates: {failure_count}[/]")
            self.console.print("[bold green]Update process completed![/]")

            # Display updated rate limit information after updates
            self._display_rate_limit_info()

        except KeyboardInterrupt:
            logging.info("Update process cancelled by user (Ctrl+C)")
            self.console.print("\n[bold yellow]Update process cancelled by user (Ctrl+C)[/]")
        except Exception as e:
            logging.error(f"Error in async update process: {str(e)}", exc_info=True)
            self.console.print(f"\n[bold red]Error in update process:[/] {str(e)}")
