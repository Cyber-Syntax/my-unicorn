#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base update command module.

This module provides a base class for AppImage update commands with common
functionality for version checking and update operations, including both
synchronous and asynchronous update capabilities.
"""

import logging
import os
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple, Set, Union

from src.commands.base import Command
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler
from src.auth_manager import GitHubAuthManager


class BaseUpdateCommand(Command):
    """
    Base class for AppImage update commands.

    This class provides common functionality for checking and updating AppImages,
    to be inherited by specific update command implementations. Supports both
    synchronous and asynchronous update operations.
    """

    def __init__(self):
        """Initialize base update command with necessary configuration managers."""
        self.global_config = GlobalConfigManager()
        self.app_config = AppConfigManager()
        self._logger = logging.getLogger(__name__)

        # For async operations - will be properly set after global_config is loaded
        self.semaphore: Optional[asyncio.Semaphore] = None

        # Set max_concurrent_updates from global config after it's loaded in post_init
        if hasattr(self.global_config, "max_concurrent_updates"):
            self.max_concurrent_updates = self.global_config.max_concurrent_updates
            self._logger.debug(
                f"Set max_concurrent_updates to {self.max_concurrent_updates} from global config"
            )

    def execute(self):
        """
        Abstract execute method to be implemented by subclasses.

        Raises:
            NotImplementedError: This method must be overridden by subclasses.
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def _update_single_app(
        self,
        app_data: Dict[str, Any],
        is_batch: bool = False,
        app_config: Optional[AppConfigManager] = None,
        global_config: Optional[GlobalConfigManager] = None,
    ) -> bool:
        """
        Update a single AppImage with error handling.

        Args:
            app_data: Dictionary with app information (config_file, name, current, latest)
            is_batch: Whether this update is part of a batch operation
            app_config: Optional app configuration manager instance
            global_config: Optional global configuration manager instance

        Returns:
            bool: True if update was successful, False otherwise
        """
        # Use provided config managers or instance variables
        app_config = app_config or self.app_config
        global_config = global_config or self.global_config

        try:
            update_msg = f"\nUpdating {app_data['name']}..."
            self._logger.info(update_msg)
            print(update_msg)

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

            # 3. Determine max retry attempts
            max_attempts = 1  # Default to 1 attempt for batch updates

            # For single app updates in interactive mode, allow retries
            if not is_batch and not global_config.batch_mode:
                max_attempts = 3

            # 4. Attempt update with possible retries
            for attempt in range(1, max_attempts + 1):
                try:
                    success = self._perform_update_attempt(
                        github_api=github_api,
                        app_config=app_config,
                        global_config=global_config,
                        app_data=app_data,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        is_batch=is_batch,
                    )

                    if success:
                        return True

                    # If we reach here and it's the last attempt or user declined retry, break
                    if attempt == max_attempts or is_batch:
                        break

                    # For single app with retries remaining, ask to retry
                    if not self._should_retry_download(attempt, max_attempts):
                        self._logger.info("User declined to retry download")
                        print("Update cancelled.")
                        break

                except Exception as e:
                    error_msg = f"Error updating {app_data['name']}: {str(e)}"
                    self._logger.error(error_msg)

                    # For batch updates or last attempt, skip to next app
                    if is_batch or attempt == max_attempts:
                        if is_batch:
                            print(f"Error: {str(e)}. Skipping to next app.")
                        else:
                            print(f"Error: {str(e)}. Maximum retry attempts reached.")
                        return False

                    # For single app update with retries remaining, ask to retry
                    print(f"Download failed. Attempt {attempt} of {max_attempts}. Error: {str(e)}")
                    if not self._should_retry_download(attempt, max_attempts):
                        print("Update cancelled.")
                        break

            finished_msg = f"Finished processing {app_data['name']}"
            self._logger.info(finished_msg)
            print(finished_msg)
            return False

        except Exception as e:
            # Catch any unexpected exceptions to ensure we continue to the next app
            error_msg = f"Unexpected error updating {app_data['name']}: {str(e)}"
            self._logger.error(error_msg)
            print(
                f"Unexpected error updating {app_data['name']}: {str(e)}. Continuing to next app."
            )
            return False

    def _perform_update_attempt(
        self,
        github_api: GitHubAPI,
        app_config: AppConfigManager,
        global_config: GlobalConfigManager,
        app_data: Dict[str, Any],
        attempt: int,
        max_attempts: int,
        is_batch: bool,
    ) -> bool:
        """
        Perform a single update attempt for an AppImage.

        Args:
            github_api: GitHub API instance for this app
            app_config: App configuration manager for this app
            global_config: Global configuration manager
            app_data: Dictionary with app information
            attempt: Current attempt number (1-based)
            max_attempts: Maximum number of attempts
            is_batch: Whether this is part of a batch update

        Returns:
            bool: True if update was successful, False otherwise

        Raises:
            Exception: Any error during the update process
        """
        # Get release data
        success, response = github_api.get_response()
        if not success:
            error_msg = f"Error fetching data from GitHub API: {response}"
            self._logger.error(error_msg)
            print(error_msg)
            raise ValueError(error_msg)

        # Verify appimage_name was properly set during release processing
        if not github_api.appimage_name or not github_api.appimage_url:
            error_msg = (
                f"AppImage information not found for {app_data['name']}. Check repository content."
            )
            self._logger.error(error_msg)
            print(error_msg)
            raise ValueError(error_msg)

        # Download AppImage
        print(f"Downloading {github_api.appimage_name}...")
        DownloadManager(github_api).download()

        # Verify the download
        if not self._verify_appimage(github_api, cleanup_on_failure=True):
            verification_failed_msg = f"Verification failed for {app_data['name']}."
            self._logger.warning(verification_failed_msg)

            # For batch updates or last attempt, skip to next app
            if is_batch or attempt == max_attempts:
                if is_batch:
                    print(f"{verification_failed_msg} Skipping to next app.")
                else:
                    print(f"{verification_failed_msg} Maximum retry attempts reached.")
                return False

            # For single app update with retries remaining
            print(f"{verification_failed_msg} Attempt {attempt} of {max_attempts}.")
            return False

        # Handle file operations
        file_handler = self._create_file_handler(github_api, app_config, global_config)

        # Try to download icon
        file_handler.download_app_icon(github_api.owner, github_api.repo)

        # Perform file operations and update config
        if file_handler.handle_appimage_operations(github_api=github_api):
            try:
                app_config.update_version(
                    new_version=github_api.version,
                    new_appimage_name=github_api.appimage_name,
                )
                success_msg = (
                    f"Successfully updated {app_data['name']} to version {github_api.version}"
                )
                self._logger.info(success_msg)
                print(success_msg)
                return True
            except Exception as e:
                error_msg = f"Failed to update version in config file: {str(e)}"
                self._logger.error(error_msg)
                print(error_msg)
                return False
        else:
            error_msg = f"Failed to update AppImage for {app_data['name']}"
            self._logger.error(error_msg)
            print(error_msg)
            return False

    def _create_file_handler(
        self,
        github_api: GitHubAPI,
        app_config: AppConfigManager,
        global_config: GlobalConfigManager,
    ) -> FileHandler:
        """
        Create a FileHandler instance with proper configuration.

        Args:
            github_api: GitHub API instance with release info
            app_config: App configuration manager
            global_config: Global configuration manager

        Returns:
            FileHandler: Configured file handler
        """
        return FileHandler(
            appimage_name=github_api.appimage_name,
            repo=github_api.repo,
            version=github_api.version,
            sha_name=github_api.sha_name,
            config_file=global_config.config_file,
            appimage_download_folder_path=global_config.expanded_appimage_download_folder_path,
            appimage_download_backup_folder_path=global_config.expanded_appimage_download_backup_folder_path,
            config_folder=app_config.config_folder,
            config_file_name=app_config.config_file_name,
            batch_mode=global_config.batch_mode,
            keep_backup=global_config.keep_backup,
            max_backups=global_config.max_backups,
        )

    def _verify_appimage(self, github_api: GitHubAPI, cleanup_on_failure: bool = True) -> bool:
        """
        Verify the downloaded AppImage using the SHA file.

        Args:
            github_api: GitHub API instance with release info
            cleanup_on_failure: Whether to delete the file on verification failure

        Returns:
            bool: True if verification succeeds or is skipped, False otherwise
        """
        # Skip verification for beta versions or when SHA file is not available
        if github_api.sha_name == "no_sha_file":
            self._logger.info("Skipping verification for beta version")
            print("Skipping verification for beta version")
            return True

        verification_manager = VerificationManager(
            sha_name=github_api.sha_name,
            sha_url=github_api.sha_url,
            appimage_name=github_api.appimage_name,
            hash_type=github_api.hash_type,
        )

        # Verify and clean up on failure if requested
        return verification_manager.verify_appimage(cleanup_on_failure=cleanup_on_failure)

    def _should_retry_download(self, attempt: int, max_attempts: int) -> bool:
        """
        Ask user if they want to retry a failed download.

        Args:
            attempt: Current attempt number
            max_attempts: Maximum number of attempts

        Returns:
            bool: True if retry should be attempted, False otherwise
        """
        try:
            return input("Retry download? (y/N): ").strip().lower() == "y"
        except KeyboardInterrupt:
            self._logger.info("Retry cancelled by user (Ctrl+C)")
            print("\nRetry cancelled by user (Ctrl+C)")
            return False

    def _display_update_list(self, updatable_apps: List[Dict[str, Any]]) -> None:
        """
        Display list of apps to update.

        Args:
            updatable_apps: List of updatable app dictionaries
        """
        print(f"\nFound {len(updatable_apps)} apps to update:")
        for idx, app in enumerate(updatable_apps, 1):
            update_msg = f"{idx}. {app['name']} ({app['current']} → {app['latest']})"
            self._logger.info(update_msg)
            print(update_msg)

    def _check_single_app_version(
        self, app_config: AppConfigManager, config_file: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check version for single AppImage.

        Args:
            app_config: App configuration manager
            config_file: Path to the configuration file

        Returns:
            dict or None: App data if update available, None otherwise
        """
        # Load the specified config file
        app_config.load_appimage_config(config_file)
        current_version = app_config.version

        # Get latest version from GitHub
        github_api = GitHubAPI(
            owner=app_config.owner,
            repo=app_config.repo,
            sha_name=app_config.sha_name,
            hash_type=app_config.hash_type,
        )

        # Call check_latest_version without owner and repo arguments
        update_available, version_info = github_api.check_latest_version(current_version)
        latest_version = version_info.get("latest_version") if update_available else None

        if "error" in version_info:
            return {
                "config_file": config_file,
                "name": os.path.splitext(config_file)[0],
                "error": version_info["error"],
            }
        elif latest_version and latest_version != current_version:
            self._logger.info(
                f"Update available for {app_config.repo}: {current_version} → {latest_version}"
            )
            return {
                "config_file": config_file,
                "name": os.path.splitext(config_file)[0],  # Remove .json extension
                "current": current_version,
                "latest": latest_version,
            }
        return None

    def _update_apps(self, apps_to_update: List[Dict[str, Any]]) -> None:
        """
        Update the specified apps using the base implementation.

        Args:
            apps_to_update: List of app information dictionaries to update
        """
        logging.info(f"Beginning update of {len(apps_to_update)} AppImages")
        total_apps = len(apps_to_update)
        success_count = 0
        failure_count = 0

        try:
            # Check rate limits before proceeding
            can_proceed, filtered_apps, rate_limit_message = self._check_rate_limits(apps_to_update)
            print(rate_limit_message)
            if not can_proceed:
                print("Update process aborted due to rate limit constraints.")
                return

            # Process each app one by one
            for index, app_data in enumerate(filtered_apps, 1):
                try:
                    success = self._update_single_app(app_data, is_batch=(len(filtered_apps) > 1))
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

            # Display rate limit information after updates
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

    def _display_rate_limit_info(self) -> None:
        """Display GitHub API rate limit information after updates."""
        try:
            # Use the cached rate limit info to avoid unnecessary API calls
            remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

            print("\n--- GitHub API Rate Limits ---")
            if is_authenticated:
                print(f"Remaining requests: {remaining}/{limit}")
                if reset_time:
                    print(f"Resets at: {reset_time}")

                if remaining < 100:
                    print("⚠️ Running low on API requests!")
            else:
                print(f"Remaining requests: {remaining}/60 (unauthenticated)")

                if remaining < 20:
                    print("⚠️ Low on unauthenticated requests!")
                    print(
                        "Tip: Add a GitHub token using option 6 in the main menu to increase rate limits (5000/hour)."
                    )

            # Indicate that this is an estimate, not a real-time value
            print("Note: Rate limit information is an estimate based on usage since last refresh.")
        except Exception as e:
            # Silently handle any errors to avoid breaking update completion
            logging.debug(f"Error displaying rate limit info: {e}")

    def _check_rate_limits(
        self, apps_to_update: List[Dict[str, Any]]
    ) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Check if updating the specified apps would exceed GitHub API rate limits.

        Calculates required API requests and compares against remaining limits.
        Each app update requires at least 1 API request, plus potentially 1 more for icon download.

        Args:
            apps_to_update: List of app information dictionaries to update

        Returns:
            Tuple containing:
                - bool: True if update can proceed, False if rate limits would be exceeded
                - List[Dict[str, Any]]: Filtered list of apps that can be updated within limits
                - str: Message explaining rate limit status
        """
        # Get current rate limit information
        remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

        # Calculate required API requests (1 for update check + potentially 1 for icon)
        required_requests = 0
        apps_with_icons = []

        # First pass: determine which apps need icon downloads by checking if they already exist
        for app_data in apps_to_update:
            required_requests += 1  # Base request for update

            # Check if app already has an icon
            config_file = app_data["config_file"]
            app_config = AppConfigManager()
            app_config.load_appimage_config(config_file)

            # Extract owner and repo for icon check
            owner = app_config.owner
            repo = app_config.repo

            icon_exists = False
            icon_locations = [
                # Primary location
                os.path.expanduser(f"~/.local/share/icons/myunicorn/{repo}/{repo}_icon.svg"),
                os.path.expanduser(f"~/.local/share/icons/myunicorn/{repo}/{repo}_icon.png"),

                # System theme locations that might be used
                os.path.expanduser(
                    f"~/.local/share/icons/hicolor/scalable/apps/{repo.lower()}.svg"
                ),
                os.path.expanduser(f"~/.local/share/icons/hicolor/256x256/apps/{repo.lower()}.png"),
            ]

            # Check if any icon exists
            for icon_path in icon_locations:
                if os.path.exists(icon_path):
                    icon_exists = True
                    self._logger.debug(f"Icon found at: {icon_path}")
                    break

            if not icon_exists:
                required_requests += 1  # Add request for icon download
                apps_with_icons.append(app_data["name"])
                self._logger.debug(f"Icon not found for {repo}, will need to download")

        # Determine if we have enough requests available
        can_proceed = remaining >= required_requests

        # Create status message
        status_message = (
            f"Rate limit status: {remaining}/{limit} requests remaining"
            f"{' (authenticated)' if is_authenticated else ' (unauthenticated)'}\n"
        )

        if reset_time:
            status_message += f"Resets at: {reset_time}\n"

        status_message += f"Required API requests: {required_requests}\n"

        if apps_with_icons:
            status_message += f"Apps needing icon downloads ({len(apps_with_icons)}): {', '.join(apps_with_icons)}\n"

        # If we can't proceed with all apps, determine how many we can update
        if not can_proceed:
            # Prioritize apps without icon downloads first (they use fewer requests)
            prioritized_apps = []
            remaining_requests = remaining

            for app_data in apps_to_update:
                app_name = app_data["name"]
                requests_needed = 2 if app_name in apps_with_icons else 1

                if remaining_requests >= requests_needed:
                    prioritized_apps.append(app_data)
                    remaining_requests -= requests_needed
                else:
                    break

            if prioritized_apps:
                status_message += (
                    f"⚠️ WARNING: Not enough API requests for all updates.\n"
                    f"Can update {len(prioritized_apps)}/{len(apps_to_update)} apps within current limits.\n"
                    f"Consider adding a GitHub token to increase rate limits (5000/hour)."
                )
                return False, prioritized_apps, status_message
            else:
                status_message += (
                    f"❌ ERROR: Not enough API requests to perform any updates.\n"
                    f"Please wait until rate limits reset or add a GitHub token."
                )
                return False, [], status_message

        return True, apps_to_update, status_message

    # --- Async Update Methods ---

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
        global_config.load_config()

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
                file_handler.download_app_icon(github_api.owner, github_api.repo)

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

    async def _update_app_async(
        self, app_data: Dict[str, Any], idx: int, total_apps: int = 0
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Asynchronous wrapper for single app update.

        Args:
            app_data: Dictionary with app information
            idx: Index of app being processed (1-based)
            total_apps: Total number of apps being updated

        Returns:
            Tuple containing success flag and result information
        """
        app_name = app_data["name"]

        # Acquire semaphore to limit concurrency
        async with self.semaphore:
            # Print status if needed
            start_time = time.time()

            try:
                # Call the update logic in a thread executor to make it non-blocking
                # Pass app index and total apps count to the update method
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._update_single_app_async(
                        app_data, is_batch=True, app_index=idx, total_apps=total_apps
                    ),
                )

                # Calculate elapsed time
                elapsed_time = time.time() - start_time

                if result:
                    return (
                        True,
                        {
                            "status": "success",
                            "message": f"Updated {app_name} to {app_data['latest']}",
                            "elapsed": elapsed_time,
                        },
                    )
                else:
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

                return (
                    False,
                    {"status": "error", "message": error_message, "elapsed": elapsed_time},
                )

    async def _update_apps_async(
        self, apps_to_update: List[Dict[str, Any]]
    ) -> Tuple[int, int, List[Dict[str, Any]]]:
        """
        Update multiple apps concurrently using asyncio.

        Args:
            apps_to_update: List of app information dictionaries to update

        Returns:
            Tuple containing success count, failure count, and list of results
        """
        # Set up progress tracking
        total_apps = len(apps_to_update)
        success_count = 0
        failure_count = 0

        # Store results for summary display
        results: List[Dict[str, Any]] = []

        try:
            logging.info(f"Beginning asynchronous update of {total_apps} AppImages")

            # Create a semaphore to limit concurrent operations if not already created
            if self.semaphore is None:
                self.semaphore = asyncio.Semaphore(self.max_concurrent_updates)

            # Create task list
            tasks = []

            # Add all update tasks
            for idx, app_data in enumerate(apps_to_update, 1):
                tasks.append(self._update_app_async(app_data, idx, total_apps))

            # Run all tasks and wait for completion
            update_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(update_results):
                app_data = apps_to_update[i]
                app_name = app_data["name"]

                # Store app data and result for return
                result_entry = {"app": app_data}

                if isinstance(result, tuple) and len(result) == 2:
                    success, result_data = result
                    result_entry["result"] = result_data

                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                else:
                    # Handle exceptions that escaped the task
                    failure_count += 1
                    error_msg = str(result) if isinstance(result, Exception) else "Unknown error"
                    logging.error(f"Update of {app_name} failed with exception: {error_msg}")
                    result_entry["result"] = {
                        "status": "exception",
                        "message": error_msg,
                        "elapsed": 0,
                    }

                results.append(result_entry)

            return success_count, failure_count, results

        except Exception as e:
            logging.error(f"Error in async update process: {str(e)}", exc_info=True)
            return success_count, failure_count, results
