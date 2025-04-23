#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Asynchronous update command module for concurrent AppImage updates.

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
import os
import time
import sys
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
from contextlib import contextmanager

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from rich.console import Console
from rich.text import Text
from rich.table import Table

from src.commands.update_base import BaseUpdateCommand
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler
from src.auth_manager import GitHubAuthManager


class UpdateAsyncCommand(BaseUpdateCommand):
    """
    Command to update multiple AppImages concurrently using async I/O.

    This class extends the BaseUpdateCommand to provide asynchronous update
    capabilities, allowing multiple AppImages to be updated in parallel for
    improved performance.

    Attributes:
        _logger (logging.Logger): Logger instance for this class
        console (Console): Rich console for output
    """

    def __init__(self) -> None:
        """Initialize with base configuration and async-specific settings."""
        super().__init__()
        # Logger for this class
        self._logger = logging.getLogger(__name__)
        # Rich console for output
        self.console = Console()

        # The max_concurrent_updates value is initialized from the global config
        # that was already loaded in BaseUpdateCommand.__post_init__()

    def execute(self) -> None:
        """
        Main update execution flow with asynchronous processing.

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
                self.console.print(
                    "[bold red]No AppImage configuration files found.[/] Use the Download option first."
                )
                return

            # Check current rate limits before any API operations
            remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

            # Show a warning if rate limits are low but don't prevent user from proceeding
            if remaining < 10:  # Low threshold for warning
                self.console.print("\n[bold yellow]--- GitHub API Rate Limit Warning ---[/]")
                self.console.print(
                    f"[bold yellow]⚠️  Low API requests remaining:[/] {remaining}/{limit}"
                )
                if reset_time:
                    self.console.print(f"Limits reset at: {reset_time}")

                if not is_authenticated:
                    self.console.print(
                        "\n[bold blue]🔑[/] Consider adding a GitHub token using option 7 in the main menu to increase rate limits (5000/hour)."
                    )

                self.console.print(
                    "\nYou can still proceed, but you may not be able to update all selected apps."
                )
                self.console.print(
                    "Consider selecting fewer apps or only the most important ones.\n"
                )

                # Give user a chance to abort
                try:
                    if input("Do you want to continue anyway? [y/N]: ").strip().lower() != "y":
                        self.console.print("[yellow]Operation cancelled.[/]")
                        return
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Operation cancelled.[/]")
                    return

            # 1. Find updatable apps via user selection
            updatable = self._find_updatable_apps()
            if not updatable:
                logging.info("No AppImages selected for update or all are up to date")
                return

            # 2. Get user confirmation
            if not self._confirm_updates(updatable):
                logging.info("Update cancelled by user")
                self.console.print("[yellow]Update cancelled[/]")
                return

            # 3. Check if we have enough rate limits for the selected apps
            can_proceed, filtered_apps, status_message = self._check_rate_limits(updatable)

            if not can_proceed:
                # Display rate limit status
                self.console.print("\n[bold yellow]--- GitHub API Rate Limit Check ---[/]")
                self.console.print(status_message)

                if not filtered_apps:
                    logging.warning("Update aborted: Insufficient API rate limits")
                    self.console.print(
                        "[bold red]Update process aborted due to rate limit constraints.[/]"
                    )
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
                        self.console.print("[yellow]Update cancelled.[/]")
                        return
                except KeyboardInterrupt:
                    logging.info("Rate limit confirmation cancelled by user (Ctrl+C)")
                    self.console.print("\n[yellow]Update cancelled by user (Ctrl+C)[/]")
                    return

                # User confirmed - proceed with partial update
                updatable = filtered_apps
                self.console.print(
                    f"\n[green]Proceeding with update of {len(updatable)} apps within rate limits.[/]"
                )

            # 4. Perform async updates
            self._update_apps_async(updatable)

        except KeyboardInterrupt:
            logging.info("Operation cancelled by user (Ctrl+C)")
            self.console.print("\n[yellow]Operation cancelled by user (Ctrl+C)[/]")
            return
        except Exception as e:
            logging.error(f"Unexpected error in async update: {str(e)}", exc_info=True)
            self.console.print(f"\n[bold red]Unexpected error:[/] {str(e)}")
            return

    def _find_updatable_apps(self) -> List[Dict[str, Any]]:
        """
        Find applications that can be updated through user selection.

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
            self.console.print("[yellow]No configuration files selected or available.[/]")
            return updatable_apps

        # Check current rate limits before making API calls
        remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

        # If we have fewer requests than selected files, warn the user
        if remaining < len(selected_files):
            self.console.print("\n[bold yellow]--- GitHub API Rate Limit Warning ---[/]")
            self.console.print(
                f"[bold yellow]⚠️  Not enough API requests to check all selected apps.[/]"
            )
            self.console.print(f"Rate limit status: {remaining}/{limit} requests remaining")
            if reset_time:
                self.console.print(f"Limits reset at: {reset_time}")

            self.console.print(f"Selected apps: {len(selected_files)}")
            self.console.print(f"Available requests: {remaining}")

            if not is_authenticated:
                self.console.print(
                    "\n[bold blue]🔑[/] Consider adding a GitHub token using option 7 in the main menu to increase rate limits."
                )

            self.console.print("\n[yellow]Some API requests will fail. Consider:[/]")
            self.console.print("1. Selecting fewer apps")
            self.console.print("2. Adding a GitHub token")
            self.console.print("3. Waiting until rate limits reset")

            # Handle the case where we have 0 remaining requests
            if remaining == 0:
                self.console.print("\n[bold red]❌ ERROR:[/] No API requests available.")
                self.console.print("Please wait until rate limits reset or add a GitHub token.")
                logging.error("Update aborted: No API requests available (0 remaining)")
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
                        self.console.print("\n[bold red]❌ ERROR:[/] Cannot proceed with 0 apps.")
                        self.console.print(
                            "Please wait until rate limits reset or add a GitHub token."
                        )
                        logging.error("Update aborted: Rate limits allow 0 apps")
                        return []

                    selected_files = limited_files
                    self.console.print(
                        f"\n[green]Limited selection to {len(selected_files)} apps based on available API requests.[/]"
                    )
                elif choice == "3":
                    self.console.print("[yellow]Operation cancelled.[/]")
                    return []
                else:
                    # Default to continuing with all selected (some will fail)
                    self.console.print(
                        "\n[yellow]Proceeding with all selected apps. Some API requests may fail.[/]"
                    )
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Operation cancelled.[/]")
                return []

        # Check each selected file for updates with progress indication
        self.console.print(
            f"\n[bold]Checking {len(selected_files)} selected apps for updates...[/]"
        )

        # Create a simple progress display for the check phase
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}[/]"),
            BarColumn(),
            TextColumn("[bold]{task.fields[status]}[/]"),
            console=self.console,
        ) as progress:
            check_task = progress.add_task(
                "[yellow]Checking apps...[/]", total=len(selected_files), status=""
            )
            failed_checks = 0

            for idx, config_file in enumerate(selected_files, 1):
                app_name = config_file.split(".")[0]  # Extract name without extension
                progress.update(
                    check_task,
                    description=f"[blue]Checking {app_name} ({idx}/{len(selected_files)})[/]",
                    advance=0,
                )

                try:
                    app_data = self._check_single_app_version(self.app_config, config_file)
                    if app_data:
                        if "error" in app_data:
                            progress.update(
                                check_task, status=f"[red]Error: {app_data['error']}[/]", advance=1
                            )
                            failed_checks += 1
                        else:
                            progress.update(
                                check_task,
                                status=f"[green]Update available: {app_data['current']} → {app_data['latest']}[/]",
                                advance=1,
                            )
                            updatable_apps.append(app_data)
                    else:
                        progress.update(check_task, status="[cyan]Already up to date[/]", advance=1)
                except Exception as e:
                    progress.update(check_task, status=f"[red]Failed: {str(e)}[/]", advance=1)
                    failed_checks += 1
                    # If we hit rate limits, provide clear feedback
                    if "rate limit exceeded" in str(e).lower():
                        self.console.print(
                            "\n[bold yellow]⚠️ GitHub API rate limit exceeded. Cannot check remaining apps.[/]"
                        )
                        self.console.print(
                            "Consider adding a GitHub token or waiting until rate limits reset."
                        )
                        break

        # Summary of check results
        if not selected_files:
            self.console.print("\n[yellow]No apps were checked due to rate limit constraints.[/]")
        else:
            self.console.print(
                f"\n[bold]Check completed:[/] [green]{len(updatable_apps)}[/] updates available, [red]{failed_checks}[/] checks failed"
            )

        return updatable_apps

    def _confirm_updates(self, updatable: List[Dict[str, Any]]) -> bool:
        """
        Handle user confirmation based on batch mode.

        Args:
            updatable: List of updatable app information dictionaries

        Returns:
            bool: True if updates are confirmed, False otherwise
        """
        if self.global_config.batch_mode:
            logging.info("Batch mode: Auto-confirming updates")
            self.console.print("[yellow]Batch mode: Auto-confirming updates[/]")
            return True

        # Display list of apps to update using Rich
        table = Table(title=f"Found {len(updatable)} apps to update")
        table.add_column("#", style="dim")
        table.add_column("App", style="cyan")
        table.add_column("Current", style="yellow")
        table.add_column("Latest", style="green")

        for idx, app in enumerate(updatable, 1):
            table.add_row(str(idx), app["name"], app["current"], app["latest"])

        self.console.print(table)

        try:
            return input("\nProceed with updates? [y/N]: ").strip().lower() == "y"
        except KeyboardInterrupt:
            logging.info("Confirmation cancelled by user (Ctrl+C)")
            self.console.print("\n[yellow]Confirmation cancelled by user (Ctrl+C)[/]")
            return False

    def _check_rate_limits(
        self, apps: List[Dict[str, Any]]
    ) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Check if we have enough API rate limits for the selected apps.

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
        remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

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
                f"[yellow]⚠️  Insufficient API rate limits for all apps.[/]\n"
                f"Rate limits: {remaining}/{limit} remaining\n"
                f"Total required: {required_requests} ({requests_per_app} per app × {len(apps)} apps)\n"
                f"Can process: {processable_apps_count}/{len(apps)} apps with current rate limits"
            )

            if reset_time:
                status += f"\nLimits reset at: {reset_time}"

            if not is_authenticated:
                status += "\n\n[blue]🔑[/] Adding a GitHub token would increase your rate limit to 5000/hour."
        else:
            # Can't process any apps with current rate limits
            status = (
                f"[bold red]❌ Insufficient API rate limits.[/]\n"
                f"Rate limits: {remaining}/{limit} remaining\n"
                f"Required: {required_requests} ({requests_per_app} per app × {len(apps)} apps)\n"
                f"Cannot process any apps with current rate limits."
            )

            if reset_time:
                status += f"\nLimits reset at: {reset_time}"

            if not is_authenticated:
                status += "\n\n[blue]🔑[/] Adding a GitHub token would increase your rate limit to 5000/hour."

        return False, filtered_apps, status

    def _update_apps_async(self, apps_to_update: List[Dict[str, Any]]) -> None:
        """
        Update multiple apps concurrently using asyncio.

        This method is the core of the async update functionality. It:
        1. Sets up tracking for in-progress and completed updates
        2. Creates an event loop and semaphore for concurrency control
        3. Launches asyncio tasks for each app update
        4. Provides real-time progress updates
        5. Handles results and generates a summary

        Args:
            apps_to_update: List of app information dictionaries to update
        """
        # Set up progress tracking
        total_apps = len(apps_to_update)
        success_count = 0
        failure_count = 0
        # Track apps currently being processed and completed apps
        in_progress: Set[str] = set()
        completed: Set[str] = set()
        # Store results for summary display
        results: Dict[str, Dict[str, Any]] = {}

        try:
            logging.info(f"Beginning asynchronous update of {total_apps} AppImages")
            self.console.print(
                f"\n[bold]Updating {total_apps} AppImages concurrently[/] (max {self.max_concurrent_updates} at once)..."
            )

            # Create a semaphore to limit concurrent operations
            self.semaphore = asyncio.Semaphore(self.max_concurrent_updates)

            # Get or create the event loop
            try:
                # Try to get the existing event loop
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # If no event loop exists in current thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Define the async update wrapper
            async def update_app_async(
                app_data: Dict[str, Any], idx: int
            ) -> Tuple[bool, Dict[str, Any]]:
                """
                Asynchronous wrapper for single app update.

                Args:
                    app_data: Dictionary with app information
                    idx: Index of app being processed (1-based)

                Returns:
                    Tuple containing success flag and result information
                """
                app_name = app_data["name"]

                # Acquire semaphore to limit concurrency
                async with self.semaphore:
                    # Track the app as in progress
                    in_progress.add(app_name)
                    start_time = time.time()

                    # Print status
                    self.console.print(
                        f"[{idx}/{total_apps}] [cyan]Starting update for {app_name}...[/]"
                    )

                    try:
                        # Call the existing update logic in a thread executor to make it non-blocking
                        # Pass app index and total apps count to the update method
                        result = await loop.run_in_executor(
                            None,
                            lambda: self._update_single_app_async(
                                app_data, is_batch=True, app_index=idx, total_apps=total_apps
                            ),
                        )

                        # Calculate elapsed time
                        elapsed_time = time.time() - start_time

                        if result:
                            self.console.print(
                                f"[{idx}/{total_apps}] [green]✓ Successfully updated {app_name}[/] ({elapsed_time:.1f}s)"
                            )
                            return (
                                True,
                                {
                                    "status": "success",
                                    "message": f"Updated {app_name} to {app_data['latest']}",
                                    "elapsed": elapsed_time,
                                },
                            )
                        else:
                            self.console.print(
                                f"[{idx}/{total_apps}] [red]✗ Failed to update {app_name}[/] ({elapsed_time:.1f}s)"
                            )
                            return (
                                False,
                                {
                                    "status": "failed",
                                    "message": "Update failed",
                                    "elapsed": elapsed_time,
                                },
                            )
                    except Exception as e:
                        error_message = str(e)
                        logging.error(f"Error updating {app_name}: {error_message}", exc_info=True)
                        elapsed_time = time.time() - start_time

                        self.console.print(
                            f"[{idx}/{total_apps}] [red]✗ Error updating {app_name}: {error_message}[/] ({elapsed_time:.1f}s)"
                        )
                        return (
                            False,
                            {"status": "error", "message": error_message, "elapsed": elapsed_time},
                        )
                    finally:
                        # Track completion
                        if app_name in in_progress:
                            in_progress.remove(app_name)
                        completed.add(app_name)

            # Create task list
            tasks = []

            # Add all update tasks
            for idx, app_data in enumerate(apps_to_update, 1):
                tasks.append(update_app_async(app_data, idx))

            # Run all tasks and wait for completion
            self.console.print("[bold]Asynchronous update started[/]")
            update_results = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

            # Process results
            for i, result in enumerate(update_results):
                app_name = apps_to_update[i]["name"]

                if isinstance(result, tuple) and len(result) == 2:
                    success, result_data = result
                    results[app_name] = result_data

                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                else:
                    # Handle exceptions that escaped the task
                    failure_count += 1
                    error_msg = str(result) if isinstance(result, Exception) else "Unknown error"
                    logging.error(f"Update of {app_name} failed with exception: {error_msg}")
                    results[app_name] = {"status": "exception", "message": error_msg, "elapsed": 0}

            # Show completion message with Rich
            self.console.print("\n=== Update Summary ===")
            self.console.print(
                f"Total apps processed: {success_count + failure_count}/{total_apps}"
            )
            self.console.print(f"[green]Successfully updated: {success_count}[/]")

            if failure_count > 0:
                self.console.print(f"[red]Failed updates: {failure_count}[/]")

                # List failed updates
                for app_name, result in results.items():
                    if result.get("status") != "success":
                        self.console.print(
                            f"  - [red]{app_name}:[/] {result.get('message', 'Unknown error')}"
                        )

            self.console.print("\n[bold green]Update process completed![/]")

            # Display updated rate limit information after updates
            self._display_rate_limit_info_rich()

        except KeyboardInterrupt:
            logging.info("Async update process cancelled by user (Ctrl+C)")
            self.console.print("\n[bold yellow]Update process cancelled by user (Ctrl+C)[/]")

            # Show partial results
            if success_count > 0 or failure_count > 0 or in_progress:
                self.console.print("\n=== Partial Update Summary ===")
                self.console.print(f"Total apps: {total_apps}")
                self.console.print(f"[green]Successfully updated: {success_count}[/]")
                self.console.print(f"[red]Failed updates: {failure_count}[/]")

                if in_progress:
                    self.console.print(f"[yellow]In progress when cancelled: {len(in_progress)}[/]")
                    self.console.print(
                        f"[yellow]Apps in progress: {', '.join(sorted(in_progress))}[/]"
                    )

                self.console.print("\n[bold yellow]Update process interrupted![/]")

        except Exception as e:
            logging.error(f"Error in async update process: {str(e)}", exc_info=True)
            self.console.print(f"\n[bold red]Error in update process:[/] {str(e)}")

    def _update_single_app_async(
        self,
        app_data: Dict[str, Any],
        is_batch: bool = False,
        app_index: int = 0,
        total_apps: int = 0,
    ) -> bool:
        """
        Update a single AppImage with specialized handling for async context.

        This method is designed to work within the async update system but
        runs synchronously within its own thread to avoid blocking the event loop.
        It handles the complete update process for a single app, including:
        1. Loading the app configuration
        2. Fetching release information from GitHub
        3. Downloading and verifying the AppImage
        4. Handling file operations and updating configuration

        Args:
            app_data: Dictionary with app information
            is_batch: Whether this update is part of a batch operation
            app_index: Index of this app in the update list (1-based)
            total_apps: Total number of apps being updated

        Returns:
            bool: True if update was successful, False otherwise
        """
        app_name = app_data["name"]
        app_config = AppConfigManager()
        global_config = GlobalConfigManager()

        logging.info(f"Starting async update for {app_name}")

        try:
            # 1. Load config for this app
            app_config.load_appimage_config(app_data["config_file"])

            # 2. Initialize GitHub API for this app
            github_api = GitHubAPI(
                owner=app_config.owner,
                repo=app_config.repo,
                sha_name=app_config.sha_name,
                hash_type=app_config.hash_type,
                arch_keyword=app_config.arch_keyword,
            )

            # 3. Perform update with one attempt (async mode always uses a single attempt)
            try:
                # Get release data (with thread-safe rate limit handling)
                success, response = github_api.get_response()
                if not success:
                    error_msg = f"Error fetching data from GitHub API: {response}"
                    logging.error(error_msg)
                    return False

                # Verify appimage_name was properly set during release processing
                if not github_api.appimage_name or not github_api.appimage_url:
                    error_msg = (
                        f"AppImage information not found for {app_name}. Check repository content."
                    )
                    logging.error(error_msg)
                    return False

                # Download AppImage - now with app index info
                logging.info(f"Downloading {github_api.appimage_name} for {app_name}")
                download_manager = DownloadManager(
                    github_api, app_index=app_index, total_apps=total_apps
                )
                download_manager.download()

                # Get the actual download path
                download_path = os.path.join("downloads", github_api.appimage_name)

                # If the file doesn't exist at the download path, log an error and return
                if not os.path.exists(download_path):
                    error_msg = f"Downloaded file not found at {download_path}"
                    logging.error(error_msg)
                    return False

                # Move the file to the current directory for verification and processing
                # This fixes the issue where downloaded files are stored in downloads/ but
                # expected to be in the root directory
                target_path = os.path.join(os.getcwd(), github_api.appimage_name)
                try:
                    # If the file already exists at the target, remove it first
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    # Copy the file from downloads to current directory
                    import shutil

                    shutil.copy2(download_path, target_path)
                    # Update file permissions to make it executable
                    os.chmod(target_path, os.stat(target_path).st_mode | 0o111)
                    logging.info(f"Moved downloaded file from {download_path} to {target_path}")
                except Exception as e:
                    error_msg = f"Error moving downloaded file: {str(e)}"
                    logging.error(error_msg)
                    return False

                # Verify the download
                if not self._verify_appimage(github_api, cleanup_on_failure=True):
                    verification_failed_msg = f"Verification failed for {app_name}."
                    logging.warning(verification_failed_msg)
                    return False

                # Handle file operations
                file_handler = self._create_file_handler(github_api, app_config, global_config)

                # Try to download icon
                from src.icon_manager import IconManager

                icon_manager = IconManager()
                icon_manager.ensure_app_icon(github_api.owner, github_api.repo)

                # Perform file operations and update config
                if file_handler.handle_appimage_operations(github_api=github_api):
                    try:
                        app_config.update_version(
                            new_version=github_api.version,
                            new_appimage_name=github_api.appimage_name,
                        )
                        success_msg = (
                            f"Successfully updated {app_name} to version {github_api.version}"
                        )
                        logging.info(success_msg)

                        # Clean up the downloaded file in downloads/ directory
                        try:
                            if os.path.exists(download_path):
                                os.remove(download_path)
                                logging.info(f"Cleaned up temporary download: {download_path}")
                        except Exception as e:
                            logging.warning(f"Could not clean up temporary download: {str(e)}")

                        return True
                    except Exception as e:
                        error_msg = f"Failed to update version in config file: {str(e)}"
                        logging.error(error_msg, exc_info=True)
                        return False
                else:
                    error_msg = f"Failed to update AppImage for {app_name}"
                    logging.error(error_msg)
                    return False

            except Exception as e:
                error_msg = f"Error updating {app_name}: {str(e)}"
                logging.error(error_msg, exc_info=True)
                return False

        except Exception as e:
            # Catch any unexpected exceptions to ensure we continue to the next app
            error_msg = f"Unexpected error updating {app_name}: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return False

    def _display_rate_limit_info_rich(self) -> None:
        """
        Display GitHub API rate limit information after updates using Rich formatting.
        """
        try:
            # Use the cached rate limit info to avoid unnecessary API calls
            remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

            self.console.print("\n--- GitHub API Rate Limits ---")
            self.console.print(
                f"Remaining requests: [bold]{remaining}/{limit}[/] ({'authenticated' if is_authenticated else 'unauthenticated'})"
            )

            if reset_time:
                self.console.print(f"Resets at: {reset_time}")

            if remaining < (100 if is_authenticated else 20):
                if remaining < 100 and is_authenticated:
                    self.console.print("[bold yellow]⚠️ Running low on API requests![/]")
                elif remaining < 20 and not is_authenticated:
                    self.console.print("[bold yellow]⚠️ Low on unauthenticated requests![/]")
                    self.console.print(
                        "[blue]Tip: Add a GitHub token to increase rate limits (5000/hour).[/]"
                    )

            self.console.print(
                "[dim]Note: Rate limit information is an estimate based on usage since last refresh.[/]"
            )

        except Exception as e:
            # Silently handle any errors to avoid breaking update completion
            logging.debug(f"Error displaying rate limit info: {e}")
