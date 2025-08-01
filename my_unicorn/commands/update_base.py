#!/usr/bin/env python3
"""Base update command module.

This module provides a base class for AppImage update commands with common
functionality for version checking and update operations, including both
synchronous and asynchronous update capabilities.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from my_unicorn.api.github_api import GitHubAPI
from my_unicorn.app_config import AppConfigManager
from my_unicorn.auth_manager import GitHubAuthManager
from my_unicorn.catalog import load_app_definition
from my_unicorn.commands.base import Command
from my_unicorn.download import DownloadManager
from my_unicorn.file_handler import FileHandler
from my_unicorn.global_config import GlobalConfigManager
from my_unicorn.utils import ui_utils
from my_unicorn.verify import VerificationManager


class BaseUpdateCommand(Command):
    """Base class for AppImage update commands.

    This class provides common functionality for checking and updating AppImages,
    to be inherited by specific update command implementations. Supports both
    synchronous and asynchronous update operations.
    """

    def __init__(self):
        """Initialize base update command with necessary configuration managers."""
        super().__init__()
        self.global_config = GlobalConfigManager()
        self.app_config = AppConfigManager()
        self._logger = logging.getLogger(__name__)

        self.max_concurrent_updates = self.global_config.max_concurrent_updates
        self._logger.debug(
            "set max_concurrent_updates to %s from global config", self.max_concurrent_updates
        )

        # Initialize semaphore in __init__
        if self.max_concurrent_updates <= 0:
            self._logger.warning(
                "Invalid max_concurrent_updates value: %s from global config. Defaulting to 1 for semaphore.",
                self.max_concurrent_updates,
            )
            # Ensure max_concurrent_updates is a positive int for Semaphore
            semaphore_value = 1
        else:
            semaphore_value = self.max_concurrent_updates

        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(semaphore_value)
        self._logger.debug("Semaphore initialized with value: %s", semaphore_value)

    def execute(self):
        """Abstract execute method to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement execute()")

    async def _update_apps_async(
        self, apps_to_update: list[dict[str, Any]]
    ) -> tuple[int, int, dict[str, dict[str, Any]]]:
        """Update multiple apps concurrently using asyncio.

        This method provides the core async update functionality that can be used
        by any subclass. It handles concurrency control, progress tracking, and
        error handling consistently across all async update operations.

        Args:
            apps_to_update: list of app information dictionaries to update

        Returns:
            tuple containing:
            - int: Number of successfully updated apps
            - int: Number of failed updates
            - dict[str, dict[str, Any]]: Dictionary mapping app names to their results
                Each result dict includes:
                - status: "success", "failed", "exception", or "error"
                - message: Success/error message
                - elapsed: Time taken for the operation
                - download_message: Message about download/existing file (for summary)
                - verification_message: Message about verification (for summary)

        """
        total_apps = len(apps_to_update)
        success_count = 0
        failure_count = 0
        results = {}

        try:
            self._logger.info("Beginning asynchronous update of %s AppImages", total_apps)

            # Create tasks for all apps
            tasks = []
            for idx, app_data in enumerate(apps_to_update, 1):
                task = self._update_single_app_async(app_data, idx, total_apps)
                tasks.append(task)

            # Run all tasks concurrently
            update_results = await asyncio.gather(*tasks, return_exceptions=True)
            self._logger.info("Processing completed. Generating update summary...")

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
                elif isinstance(result, Exception):
                    # Handle exceptions that escaped the task
                    failure_count += 1
                    error_msg = "Update of %s failed with exception: %s", app_name, result
                    self._logger.error(error_msg)
                    results[app_name] = {
                        "status": "exception",
                        "message": error_msg,
                        "elapsed": 0,
                    }
                else:
                    # Handle unexpected result format
                    failure_count += 1
                    self._logger.error("Unexpected result format for %s: %s", app_name, result)
                    results[app_name] = {
                        "status": "error",
                        "message": "Unexpected result format",
                        "elapsed": 0,
                    }

        except Exception as e:
            self._logger.error("Error in async update process: %s", e, exc_info=True)

        return success_count, failure_count, results

    async def _update_single_app_async(
        self, app_data: dict[str, Any], app_index: int, total_apps: int
    ) -> tuple[bool, dict[str, Any]]:
        """Update a single app asynchronously with concurrency control.

        This method handles the async wrapper around the core update logic,
        providing consistent behavior for all async update operations.

        Args:
            app_data: Dictionary with app information
            app_index: Index of app being processed (1-based)
            total_apps: Total number of apps being updated

        Returns:
            tuple containing:
            - bool: True if update was successful, False otherwise
            - tuple[str, Any]: Result information including status, message, and elapsed time

        """
        app_name = app_data["name"]

        # Acquire semaphore to limit concurrency
        async with self.semaphore:
            start_time = time.time()

            try:
                self._logger.info(
                    "[%s/%s] Starting update for %s", app_index, total_apps, app_name
                )

                # Create separate config managers for this app to avoid conflicts
                app_config = AppConfigManager()
                global_config = GlobalConfigManager()
                global_config.load_config()

                # Call the existing update logic in a thread executor to make it non-blocking
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._perform_app_update_core(
                        app_data=app_data,
                        app_config=app_config,
                        global_config=global_config,
                        is_async=True,
                        is_batch=True,
                        app_index=app_index,
                        total_apps=total_apps,
                    ),
                )

                # Calculate elapsed time
                elapsed_time = time.time() - start_time

                if result[0]:  # result is (success, result_data)
                    self._logger.info(
                        "[%s/%s] ✓ Successfully updated %s (%.1fs)",
                        app_index,
                        total_apps,
                        app_name,
                        elapsed_time,
                    )
                    result_appimage_name = (
                        result[1].get("appimage_name") if result[1] else None
                    )
                    result_checksum_file_name = (
                        result[1].get("checksum_file_name") if result[1] else None
                    )
                    return True, {
                        "status": "success",
                        "message": f"Updated to {app_data['latest']}",
                        "elapsed": elapsed_time,
                        "appimage_name": result_appimage_name,
                        "checksum_file_name": result_checksum_file_name,
                    }
                else:
                    self._logger.warning(
                        "[%s/%s] ✗ Failed to update %s (%.1fs)",
                        app_index,
                        total_apps,
                        app_name,
                        elapsed_time,
                    )
                    result_appimage_name = (
                        result[1].get("appimage_name") if result[1] else None
                    )
                    result_checksum_file_name = (
                        result[1].get("checksum_file_name") if result[1] else None
                    )
                    return False, {
                        "status": "failed",
                        "message": result[1].get("error", "Update failed")
                        if result[1]
                        else "Update failed",
                        "elapsed": elapsed_time,
                        "appimage_name": result_appimage_name,
                        "checksum_file_name": result_checksum_file_name,
                    }

            except Exception as e:
                error_message = str(e)
                elapsed_time = time.time() - start_time
                self._logger.error(
                    "Error updating %s: %s", app_name, error_message, exc_info=True
                )

                return False, {
                    "status": "error",
                    "message": error_message,
                    "elapsed": elapsed_time,
                }

    def _perform_app_update_core(
        self,
        app_data: dict[str, Any],
        app_config: AppConfigManager,
        global_config: GlobalConfigManager,
        is_async: bool = False,
        is_batch: bool = False,
        app_index: int = 0,
        total_apps: int = 0,
    ) -> tuple[bool, dict[str, Any] | None]:  # pylint: disable=method-hidden
        """Core method to update a single AppImage with consistent error handling.

        This contains the shared update logic used by both async and sync update
        processes. It handles loading configs, downloading, verification, and file
        operations.

        Args:
            app_data: Dictionary with app information
            app_config: App configuration manager
            global_config: Global configuration manager
            is_async: Whether this is running in an async context
            is_batch: Whether this update is part of a batch operation
            app_index: Index of this app in the update list (1-based)
            total_apps: Total number of apps being updated

        Returns:
            tuple containing:
            - bool: True if update was successful, False otherwise
            - Optional[tuple[str, Any]]: Additional result data (for async mode)

        """
        # Extract app name from config file
        app_name = app_data["name"]

        # Load app definition FIRST to get static metadata
        app_info = load_app_definition(app_name)
        if not app_info:
            self._logger.error(
                "No app definition found for %s. Please ensure %s.json exists in the apps/ directory.",
                app_name,
                app_name,
            )
            return False, {
                "error": "No app definition found for %s. Please ensure %s.json exists in the apps/ directory."
                % (app_name, app_name)
            }

        # set the app name in config manager to enable property access
        app_config.set_app_name(app_name)

        # Load user config for this app (version, appimage_name)
        app_config.load_appimage_config(app_data["config_file"])

        # Initialize GitHub API using app definition data
        # For use_asset_digest apps, use auto detection instead of None values
        checksum_file_name_param = (
            app_info.checksum_file_name if app_info.checksum_file_name else "auto"
        )
        checksum_hash_type_param = (
            app_info.checksum_hash_type if app_info.checksum_hash_type else "auto"
        )

        github_api = GitHubAPI(
            owner=app_info.owner,
            repo=app_info.repo,
            checksum_file_name=checksum_file_name_param,
            checksum_hash_type=checksum_hash_type_param,
            arch_keyword=None,  # Use app definition's preferred_characteristic_suffixes
        )

        current_version = app_config.version or ""

        # First check for updates with version_check_only=True to avoid unnecessary SHA processing
        update_available, version_info = github_api.check_latest_version(
            current_version, version_check_only=True, is_batch=is_batch
        )

        if "error" in version_info:
            self._logger.error(
                "Error checking latest version from GitHub API: %s", version_info["error"]
            )
            return False, {
                "error": "Error checking latest version from GitHub API: %s"
                % version_info["error"]
            }

        if not update_available:
            self._logger.info(
                "No update available for %s. Current: %s, Latest: %s",
                app_data["name"],
                current_version,
                version_info.get("latest_version", "unknown"),
            )
            return False, {"status": "no_update"}

        # Now that we know an update is available, do a full release processing to get SHA info
        self._logger.debug(
            "Update available for %s, processing full release info including SHA",
            app_data["name"],
        )
        full_result = github_api.get_latest_release(
            version_check_only=False, is_batch=is_batch
        )

        # Handle variable return values (2 or 3 elements)
        if len(full_result) == 2:
            full_success, full_release_data = full_result
        else:
            full_success, full_release_data, _ = full_result

        if not full_success:
            self._logger.error(
                "Error getting full release data from GitHub API: %s", full_release_data
            )
            return False, {
                "error": "Error getting full release data from GitHub API: %s"
                % full_release_data
            }

        # Download and verify AppImage
        try:
            # Download AppImage or get existing file
            download_manager = DownloadManager(
                github_api, app_index=app_index, total_apps=total_apps
            )
            downloaded_file_path, was_existing_file = download_manager.download()

            # Handle download status messages based on context
            if was_existing_file:
                download_message = f"Found existing file: {github_api.appimage_name}"
                if not is_async:
                    print(f"\n{download_message}")
            else:
                download_message = (
                    f"✓ Downloaded {github_api.appimage_name}"
                    if github_api.appimage_name
                    else "✓ Download completed"
                )
                if not is_async:
                    print(f"\n{download_message}")

            # Define verification status message
            verification_status_message = (
                "Verifying existing file..."
                if was_existing_file
                else "Verifying download integrity..."
            )
            if not is_async:
                print(verification_status_message)

            # Determine per-file cleanup behavior: skip interactive prompts in batch or async
            cleanup = False if is_batch else True

            # Delegate verification to VerificationManager
            verification_manager = VerificationManager(
                checksum_file_name=github_api.checksum_file_name,
                checksum_file_download_url=github_api.checksum_file_download_url,
                appimage_name=github_api.appimage_name,
                checksum_hash_type=github_api.checksum_hash_type or "sha256",
                asset_digest=github_api.asset_digest,
            )

            verification_result, verification_skipped = verification_manager.verify_for_update(
                downloaded_file_path, cleanup_on_failure=cleanup
            )
            if not verification_result:
                self._logger.warning("Verification failed for %s.", app_data["name"])
                return False, {
                    "error": "Verification failed for %s." % app_data["name"],
                    "appimage_name": github_api.appimage_name,
                    "checksum_file_name": github_api.checksum_file_name,
                }

            # Handle file operations
            file_handler = self._create_file_handler(github_api, app_config, global_config)

            # Download app icon if possible
            from my_unicorn.icon_manager import IconManager

            icon_manager = IconManager()
            icon_success, icon_path = icon_manager.ensure_app_icon(
                github_api.owner, github_api.repo, app_rename=app_config.app_rename
            )

            # Perform file operations and update config
            if file_handler.handle_appimage_operations(
                icon_path=icon_path if icon_success else None
            ):
                app_config.update_version(
                    new_version=github_api.version,
                    new_appimage_name=github_api.appimage_name,
                )

                # Create appropriate success message based on verification status
                if verification_skipped:
                    success_msg = (
                        f"Updated {app_data['name']} to version {github_api.version} "
                        "(verification skipped - no hash file provided by developer)"
                    )
                else:
                    success_msg = (
                        f"Successfully updated and verified {app_data['name']} "
                        f"to version {github_api.version}"
                    )

                self._logger.info(success_msg)
                # Store success message for summary instead of printing immediately
                return True, {
                    "status": "success",
                    "message": success_msg,
                    "new_version": github_api.version,
                    "verification_skipped": verification_skipped,
                    "appimage_name": github_api.appimage_name,
                    "checksum_file_name": github_api.checksum_file_name,
                    "download_message": download_message if is_async else "",
                    "verification_status_message": verification_status_message,
                    "success_message": success_msg if is_async else "",
                }
            else:
                self._logger.error(
                    "Failed to perform file operations for %s", app_data["name"]
                )
                return False, {
                    "error": "Failed to perform file operations for %s" % app_data["name"],
                    "appimage_name": github_api.appimage_name,
                    "checksum_file_name": github_api.checksum_file_name,
                }

        except Exception as e:
            self._logger.error("Error updating %s: %s", app_data["name"], e)
            # Include appimage_name and checksum_file_name if github_api was created successfully
            result = {"error": "Error updating %s: %s" % (app_data["name"], e)}
            if "github_api" in locals() and github_api.appimage_name:
                result["appimage_name"] = github_api.appimage_name
                if github_api.checksum_file_name:
                    result["checksum_file_name"] = github_api.checksum_file_name
            if is_async:
                result["download_message"] = (
                    download_message if "download_message" in locals() else ""
                )
                result["verification_message"] = (
                    verification_status_message
                    if "verification_status_message" in locals()
                    else ""
                )
            else:
                result["download_message"] = ""
                result["verification_message"] = ""
            return False, result

    def _create_file_handler(
        self,
        github_api: GitHubAPI,
        app_config: AppConfigManager,
        global_config: GlobalConfigManager,
    ) -> FileHandler:
        """Create a FileHandler instance with proper configuration."""
        # Ensure critical FileHandler parameters are not None
        if not all([github_api.appimage_name, github_api.repo, github_api.owner]):
            raise ValueError("Missing required parameters for FileHandler")

        return FileHandler(
            appimage_name=str(github_api.appimage_name),
            repo=str(github_api.repo),
            owner=str(github_api.owner),
            version=str(github_api.version),
            checksum_file_name=github_api.checksum_file_name,
            config_file=str(global_config.config_file),
            app_storage_path=Path(global_config.expanded_app_storage_path),
            app_backup_storage_path=Path(global_config.expanded_app_backup_storage_path),
            config_folder=str(app_config.config_folder) if app_config.config_folder else None,
            config_file_name=app_config.config_file_name,
            batch_mode=global_config.batch_mode,
            keep_backup=global_config.keep_backup,
            max_backups=global_config.max_backups,
            app_rename=str(app_config.app_rename),
        )

    def _should_retry_download(self, attempt: int, max_attempts: int) -> bool:
        """Ask user if they want to retry a failed download."""
        try:
            return input("Retry download? (y/N): ").strip().lower() == "y"
        except KeyboardInterrupt:
            self._logger.info("Retry cancelled by user (Ctrl+C)")
            print("\nRetry cancelled by user (Ctrl+C)")
            return False

    def _check_single_app_version(
        self, app_config: AppConfigManager, config_file: str
    ) -> dict[str, Any] | bool:
        """Check version for single AppImage."""
        # Extract app name from config file
        app_name = os.path.splitext(config_file)[0]

        # Load app definition FIRST to get static metadata
        app_info = load_app_definition(app_name)
        if not app_info:
            return {
                "config_file": config_file,
                "name": app_name,
                "error": f"No app definition found for {app_name}",
            }

        # set the app name in config manager to enable property access
        app_config.set_app_name(app_name)

        # Load user config (version, appimage_name)
        app_config.load_appimage_config(config_file)
        current_version = app_config.version

        # Initialize GitHub API using app definition data
        # For use_asset_digest apps, use auto detection instead of None values
        checksum_file_name_param = (
            app_info.checksum_file_name if app_info.checksum_file_name else "auto"
        )
        checksum_hash_type_param = (
            app_info.checksum_hash_type if app_info.checksum_hash_type else "auto"
        )

        github_api = GitHubAPI(
            owner=app_info.owner,
            repo=app_info.repo,
            checksum_file_name=checksum_file_name_param,
            checksum_hash_type=checksum_hash_type_param,
            arch_keyword=None,  # Use app definition's preferred_characteristic_suffixes
        )

        update_available, version_info = github_api.check_latest_version(
            current_version, version_check_only=True
        )
        latest_version = version_info.get("latest_version") if update_available else None

        if "error" in version_info:
            return {
                "config_file": config_file,
                "name": app_name,
                "error": version_info["error"],
            }
        elif latest_version and latest_version != current_version:
            self._logger.info(
                "Update available for %s: %s → %s",
                app_info.repo,
                current_version,
                latest_version,
            )
            return {
                "config_file": config_file,
                "name": app_name,
                "current": current_version,
                "latest": latest_version,
            }
        return False  # No update available

    def check_rate_limits(
        self, apps: list[dict[str, Any]]
    ) -> tuple[bool, list[dict[str, Any]], str]:
        """Generalized rate limit check logic.

        Args:
            apps: list of app information dictionaries

        Returns:
            tuple containing:
            - bool: True if we can proceed with all apps, False if partial/no update needed
            - list[tuple[str, Any]]: Filtered list of apps that can be processed
            - str: Status message explaining the rate limit situation

        """
        try:
            # Get current rate limit info
            remaining, limit, reset_time, auth = GitHubAuthManager.get_rate_limit_info()

            # Calculate requests needed (estimate 3 per app: version check, release info, icon check)
            # TODO: make sure that is also checked for each app
            # and auto and selective commands
            requests_per_app = 3
            total_requests_needed = len(apps) * requests_per_app

            # Check if we have enough requests for all apps
            if remaining >= total_requests_needed:
                message = f"Rate limit status: {remaining}/{limit} requests remaining. Sufficient for all {len(apps)} apps."
                self._logger.info(message)
                return True, apps, message

            # Show a warning if rate limits are low but don't prevent user from proceeding
            if remaining < 10:  # Now an int comparison
                print("\n--- GitHub API Rate Limit Warning ---")
                print(f"⚠️ Low API requests remaining: {remaining}/{limit}")
                self._logger.warning("Low API requests remaining: %s/%s", remaining, limit)
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

            # Not enough for all apps - see how many we can process
            apps_we_can_process = max(0, remaining // requests_per_app)

            if apps_we_can_process == 0:
                message = (
                    f"ERROR: Not enough API requests remaining ({remaining}/{limit}). "
                    f"Minimum requests required: {requests_per_app}. "
                    f"Rate limit resets at: {reset_time}"
                )
                self._logger.error(
                    "ERROR: Not enough API requests remaining (%d/%d). Minimum requests required: %d. Rate limit resets at: %s",
                    remaining,
                    limit,
                    requests_per_app,
                    reset_time,
                )
                return False, [], message

            # We can process some apps but not all
            filtered_apps = apps[:apps_we_can_process]
            message = (
                f"WARNING: Not enough API requests for all updates. "
                f"Can process {apps_we_can_process} out of {len(apps)} apps. "
                f"Remaining requests: {remaining}/{limit}"
            )
            return False, filtered_apps, message

        except Exception as e:
            self._logger.error("Error checking rate limits: %s", e)
            message = f"Error checking rate limits: {e}. Proceeding with caution."
            return True, apps, message

    def display_rate_limit_info(self) -> None:
        """Display current GitHub API rate limit information."""
        try:
            remaining, limit, reset_time, is_authenticated = (
                GitHubAuthManager.get_rate_limit_info()
            )

            # Ensure remaining is an integer
            if isinstance(remaining, str):
                remaining = int(remaining)

            print("\n--- GitHub API Rate Limits ---")
            if is_authenticated:
                print(f"Remaining requests: {remaining}/{limit}")
                if remaining < 100:  # Warning threshold for authenticated users
                    print("⚠️ Running low on API requests!")
            else:
                print(f"Remaining requests: {remaining}/{limit} (unauthenticated)")
                if remaining < 15:  # Warning threshold for unauthenticated users
                    print("⚠️ Low on unauthenticated requests!")
                    print(
                        "Tip: Add a GitHub token using option 6 in the main menu to increase rate limits (5000/hour)."
                    )

            print(f"Resets at: {reset_time}")

        except Exception as e:
            self._logger.error("Error displaying rate limit info: %s", e)
            print(f"Error retrieving rate limit information: {e}")

    def display_async_results(
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
            for app_name, result in results.items():
                if result.get("status") != "success":
                    message = result.get("message", "Unknown error")
                    elapsed = result.get("elapsed", 0)
                    print(f"  ✗ {app_name}: {message} ({elapsed:.1f}s)")

        print("\nUpdate process completed!")

        # Prompt to remove downloaded files for failed updates in batch
        if failure_count > 0:
            failed_apps = [
                name for name, res in results.items() if res.get("status") != "success"
            ]

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

    def update_apps_async_wrapper(self, apps_to_update: list[dict[str, Any]]) -> None:
        """Wrap the async update method to call it from a synchronous context.

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
                f"\nStarting asynchronous update of {len(apps_to_update)} AppImages "
                f"(max {self.max_concurrent_updates} concurrent)..."
            )
            self._logger.info(
                "Starting asynchronous update of %d AppImages with concurrency limit %d",
                len(apps_to_update),
                self.max_concurrent_updates,
            )
            # set the main event loop in ui_utils
            ui_utils.set_main_event_loop(loop)

            # Initialize progress manager for all downloads
            DownloadManager.get_or_create_progress(len(apps_to_update))

            # Run the async function using the base class method
            success_count, failure_count, results = loop.run_until_complete(
                self._update_apps_async(apps_to_update)
            )

            # Clean up progress manager after all downloads complete
            DownloadManager.stop_progress()

            # Display results
            self.display_async_results(
                success_count, failure_count, results, len(apps_to_update)
            )

        except KeyboardInterrupt:
            self._logger.info("Update process cancelled by user (Ctrl+C)")
            print("\nUpdate process cancelled by user (Ctrl+C)")
        except Exception as e:
            self._logger.error("Error in async update process: %s", str(e), exc_info=True)
            print(f"\nError in update process: {e!s}")

    def find_updatable_apps(
        self, selected_files: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Find AppImages that have updates available.

        Args:
            selected_files (Optional[list[str]]): List of selected configuration files to check.
                                                    If None, all available files will be checked.

        Returns:
            list[tuple[str, Any]]: list of updatable app information dictionaries

        """
        updatable_apps = []

        try:
            # Get the list of files to process
            if selected_files is None:
                json_files = self.app_config.list_json_files()
                if not json_files:
                    logger.warning("No AppImage configuration files found")
                    print(
                        "No AppImage configuration files found. Use the Download option first."
                    )
                    return []
                print(f"Checking {len(json_files)} AppImage configurations...")
            else:
                json_files = selected_files
                print(f"Checking {len(json_files)} selected AppImage configurations...")

            # Check each app for updates
            for config_file in json_files:
                try:
                    # Create a temporary app config for checking this app
                    app_name = os.path.splitext(config_file)[0]  # Remove .json extension

                    # Directly check version without redirecting output
                    app_data = self._check_single_app_version(self.app_config, config_file)

                    if (
                        isinstance(app_data, dict)
                        and "current" in app_data
                        and "latest" in app_data
                    ):
                        print(
                            f"{app_name}: update available: {app_data['current']} → "
                            f"{app_data['latest']}"
                        )
                        updatable_apps.append(app_data)
                    elif app_data is False:
                        print(f"{app_name}: already up to date")
                    else:
                        print(f"{app_name}, unexpected result: {app_data}")

                except Exception as e:
                    self._logger.error("Error checking %s: %s", config_file, e)
                    print(f"{app_name}: error: {e}")
                except KeyboardInterrupt:
                    self._logger.info("Update check cancelled by user (Ctrl+C)")
                    print("\nUpdate check cancelled by user (Ctrl+C)")
                    return updatable_apps

        except Exception as e:
            self._logger.error("Error during update check: %s", e)
            print("Error during update check:", e)

        return updatable_apps
