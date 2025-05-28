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
from typing import Any, Dict, List, Optional, Tuple

from src.api.github_api import GitHubAPI
from src.app_catalog import load_app_definition
from src.app_config import AppConfigManager
from src.commands.base import Command
from src.download import DownloadManager
from src.file_handler import FileHandler
from src.global_config import GlobalConfigManager
from src.verify import VerificationManager


class BaseUpdateCommand(Command):
    """Base class for AppImage update commands.

    This class provides common functionality for checking and updating AppImages,
    to be inherited by specific update command implementations. Supports both
    synchronous and asynchronous update operations.
    """

    def __init__(self):
        """Initialize base update command with necessary configuration managers."""
        self.global_config = GlobalConfigManager()
        self.app_config = AppConfigManager()
        self._logger = logging.getLogger(__name__)

        # Ensure global config is loaded
        self.global_config.load_config()

        self.max_concurrent_updates = self.global_config.max_concurrent_updates
        self._logger.debug(
            f"Set max_concurrent_updates to {self.max_concurrent_updates} from global config"
        )

        # Initialize semaphore in __init__
        if not isinstance(self.max_concurrent_updates, int) or self.max_concurrent_updates <= 0:
            self._logger.warning(
                f"Invalid max_concurrent_updates value: {self.max_concurrent_updates} from global config. Defaulting to 1 for semaphore."
            )
            # Ensure max_concurrent_updates is a positive int for Semaphore
            semaphore_value = 1
        else:
            semaphore_value = self.max_concurrent_updates

        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(semaphore_value)
        self._logger.debug(f"Semaphore initialized with value: {semaphore_value}")

        # Ensure base directory paths exist
        os.makedirs(self.global_config.expanded_app_storage_path, exist_ok=True)
        os.makedirs(self.global_config.expanded_app_backup_storage_path, exist_ok=True)
        os.makedirs(self.global_config.expanded_app_download_path, exist_ok=True)

    def execute(self):
        """Abstract execute method to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement execute()")

    async def _update_apps_async(self, apps_to_update: List[Dict[str, Any]]) -> Tuple[int, int, Dict[str, Dict[str, Any]]]:
        """Update multiple apps concurrently using asyncio.

        This method provides the core async update functionality that can be used
        by any subclass. It handles concurrency control, progress tracking, and
        error handling consistently across all async update operations.

        Args:
            apps_to_update: List of app information dictionaries to update

        Returns:
            Tuple containing:
            - int: Number of successfully updated apps
            - int: Number of failed updates
            - Dict[str, Dict[str, Any]]: Dictionary mapping app names to their results
        """
        total_apps = len(apps_to_update)
        success_count = 0
        failure_count = 0
        results = {}

        try:
            self._logger.info(f"Beginning asynchronous update of {total_apps} AppImages")

            # Create tasks for all apps
            tasks = []
            for idx, app_data in enumerate(apps_to_update, 1):
                task = self._update_single_app_async(app_data, idx, total_apps)
                tasks.append(task)

            # Run all tasks concurrently
            update_results = await asyncio.gather(*tasks, return_exceptions=True)

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
                    error_msg = str(result)
                    self._logger.error(f"Update of {app_name} failed with exception: {error_msg}")
                    results[app_name] = {"status": "exception", "message": error_msg, "elapsed": 0}
                else:
                    # Handle unexpected result format
                    failure_count += 1
                    self._logger.error(f"Unexpected result format for {app_name}: {result}")
                    results[app_name] = {"status": "error", "message": "Unexpected result format", "elapsed": 0}

        except Exception as e:
            self._logger.error(f"Error in async update process: {e!s}", exc_info=True)

        return success_count, failure_count, results

    async def _update_single_app_async(
        self,
        app_data: Dict[str, Any],
        app_index: int,
        total_apps: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """Update a single app asynchronously with concurrency control.

        This method handles the async wrapper around the core update logic,
        providing consistent behavior for all async update operations.

        Args:
            app_data: Dictionary with app information
            app_index: Index of app being processed (1-based)
            total_apps: Total number of apps being updated

        Returns:
            Tuple containing:
            - bool: True if update was successful, False otherwise
            - Dict[str, Any]: Result information including status, message, and elapsed time
        """
        app_name = app_data["name"]

        # Acquire semaphore to limit concurrency
        async with self.semaphore:
            start_time = time.time()

            try:
                self._logger.info(f"[{app_index}/{total_apps}] Starting update for {app_name}")

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
                    )
                )

                # Calculate elapsed time
                elapsed_time = time.time() - start_time

                if result[0]:  # result is (success, result_data)
                    self._logger.info(f"[{app_index}/{total_apps}] ✓ Successfully updated {app_name} ({elapsed_time:.1f}s)")
                    return True, {
                        "status": "success",
                        "message": f"Updated to {app_data['latest']}",
                        "elapsed": elapsed_time,
                    }
                else:
                    self._logger.warning(f"[{app_index}/{total_apps}] ✗ Failed to update {app_name} ({elapsed_time:.1f}s)")
                    return False, {
                        "status": "failed",
                        "message": result[1].get("error", "Update failed") if result[1] else "Update failed",
                        "elapsed": elapsed_time,
                    }

            except Exception as e:
                error_message = str(e)
                elapsed_time = time.time() - start_time
                self._logger.error(f"Error updating {app_name}: {error_message}", exc_info=True)

                return False, {
                    "status": "error",
                    "message": error_message,
                    "elapsed": elapsed_time,
                }

    def _perform_app_update_core(
        self,
        app_data: Dict[str, Any],
        app_config: AppConfigManager,
        global_config: GlobalConfigManager,
        is_async: bool = False,
        is_batch: bool = False,
        app_index: int = 0,
        total_apps: int = 0,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:  # pylint: disable=method-hidden
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
            Tuple containing:
            - bool: True if update was successful, False otherwise
            - Optional[Dict[str, Any]]: Additional result data (for async mode)

        """
        # Extract app name from config file
        app_name = app_data["name"]

        # Load app definition FIRST to get static metadata
        app_info = load_app_definition(app_name)
        if not app_info:
            error_msg = f"No app definition found for {app_name}. Please ensure {app_name}.json exists in the apps/ directory."
            self._logger.error(error_msg)
            return False, {"error": error_msg}

        # Set the app name in config manager to enable property access
        app_config.set_app_name(app_name)

        # Load user config for this app (version, appimage_name)
        app_config.load_appimage_config(app_data["config_file"])

        # Initialize GitHub API using app definition data
        github_api = GitHubAPI(
            owner=app_info.owner,
            repo=app_info.repo,
            sha_name=app_info.sha_name,
            hash_type=app_info.hash_type,
            arch_keyword=None,  # Use app definition's preferred_characteristic_suffixes
        )

        current_version = app_config.version or ""
        update_available, version_info = github_api.check_latest_version(current_version)

        if "error" in version_info:
            error_msg = f"Error checking latest version from GitHub API: {version_info['error']}"
            self._logger.error(error_msg)
            return False, {"error": error_msg}

        if not update_available:
            self._logger.info(
                f"No update available for {app_data['name']}. Current: {current_version}, Latest: {version_info.get('latest_version', 'unknown')}"
            )
            return False, {"status": "no_update"}

        # Download and verify AppImage
        try:
            # Download AppImage
            print(f"\nDownloading {github_api.appimage_name}...")
            download_manager = DownloadManager(
                github_api, app_index=app_index, total_apps=total_apps
            )
            downloaded_file_path = download_manager.download()

            # Verify the download
            verification_result, verification_skipped = self._verify_appimage(
                github_api, downloaded_file_path, cleanup_on_failure=True
            )
            if not verification_result:
                error_msg = f"Verification failed for {app_data['name']}."
                self._logger.warning(error_msg)
                return False, {"error": error_msg}

            # Handle file operations
            file_handler = self._create_file_handler(github_api, app_config, global_config)

            # Download app icon if possible
            from src.icon_manager import IconManager

            icon_manager = IconManager()
            icon_success, icon_path = icon_manager.ensure_app_icon(
                github_api.owner, github_api.repo, app_display_name=app_config.app_display_name
            )

            # Perform file operations and update config
            if file_handler.handle_appimage_operations(
                github_api=github_api, icon_path=icon_path if icon_success else None
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
                    success_msg = f"Successfully updated and verified {app_data['name']} to version {github_api.version}"

                self._logger.info(success_msg)
                print(success_msg)
                return True, {
                    "status": "success",
                    "message": success_msg,
                    "new_version": github_api.version,
                    "verification_skipped": verification_skipped,
                }
            else:
                error_msg = f"Failed to perform file operations for {app_data['name']}"
                self._logger.error(error_msg)
                return False, {"error": error_msg}

        except Exception as e:
            error_msg = f"Error updating {app_data['name']}: {e!s}"
            self._logger.error(error_msg)
            return False, {"error": error_msg}

    def _update_single_app(
        self,
        app_data: Dict[str, Any],
        is_batch: bool = False,
        app_config: Optional[AppConfigManager] = None,
        global_config: Optional[GlobalConfigManager] = None,
    ) -> bool:
        """Update a single AppImage with error handling."""
        # Use provided config managers or instance variables
        app_config = app_config or self.app_config
        global_config = global_config or self.global_config

        try:
            update_msg = f"\nUpdating {app_data['name']}..."
            self._logger.info(update_msg)
            print(update_msg)

            # Determine max retry attempts
            max_attempts = 1  # Default to 1 attempt for batch updates

            # For single app updates in interactive mode, allow retries
            if not is_batch and not global_config.batch_mode:
                max_attempts = 3

            # Attempt update with possible retries
            for attempt in range(1, max_attempts + 1):
                try:
                    # Use the core update method
                    success, result = self._perform_app_update_core(  # pylint: disable=no-member
                        app_data=app_data,
                        app_config=app_config,
                        global_config=global_config,
                        is_async=False,
                        is_batch=is_batch,
                    )

                    if success:
                        return True

                    # Check if we got a "no update needed" status
                    if result and result.get("status") == "no_update":
                        return False

                    # If we reach here and it's the last attempt or batch mode, break
                    if attempt == max_attempts or is_batch:
                        break

                    # For single app with retries remaining, ask to retry
                    if not self._should_retry_download(attempt, max_attempts):
                        self._logger.info("User declined to retry download")
                        print("Update cancelled.")
                        break

                except Exception as e:
                    error_msg = f"Error updating {app_data['name']}: {e!s}"
                    self._logger.error(error_msg)

                    # For batch updates or last attempt, skip to next app
                    if is_batch or attempt == max_attempts:
                        if is_batch:
                            print(f"Error: {e!s}. Skipping to next app.")
                        else:
                            print(f"Error: {e!s}. Maximum retry attempts reached.")
                        return False

                    # For single app update with retries remaining, ask to retry
                    print(f"Download failed. Attempt {attempt} of {max_attempts}. Error: {e!s}")
                    if not self._should_retry_download(attempt, max_attempts):
                        print("Update cancelled.")
                        break

            finished_msg = f"Finished processing {app_data['name']}"
            self._logger.info(finished_msg)
            print(finished_msg)
            return False

        except Exception as e:
            error_msg = f"Unexpected error updating {app_data['name']}: {e!s}"
            self._logger.error(error_msg)
            print(f"Unexpected error updating {app_data['name']}: {e!s}. Continuing to next app.")
            return False

    def _verify_appimage(
        self,
        github_api: GitHubAPI,
        downloaded_file_path: Optional[str] = None,
        cleanup_on_failure: bool = True,
    ) -> Tuple[bool, bool]:
        """Verify the downloaded AppImage using the SHA file.

        Args:
            github_api: The GitHub API instance with release information
            downloaded_file_path: Path to the downloaded file for verification
            cleanup_on_failure: Whether to delete the file on verification failure

        Returns:
            Tuple containing:
            - bool: True if verification succeeded or was skipped, False if failed
            - bool: True if verification was skipped, False otherwise

        """
        verification_skipped = False

        if github_api.sha_name == "no_sha_file":
            self._logger.info("Skipping verification - no hash file provided by the developer")
            print("Note: Verification skipped - no hash file provided by the developer")
            verification_skipped = True
            # Return verification_skipped=True instead of verification_success=True
            # This better reflects that verification didn't actually succeed but was skipped
            return True, verification_skipped

        # Ensure critical VerificationManager parameters are not None
        if github_api.appimage_name is None:
            raise ValueError(
                f"VerificationManager: appimage_name is None for {github_api.owner}/{github_api.repo}."
            )

        verification_manager = VerificationManager(
            sha_name=github_api.sha_name,
            sha_url=github_api.sha_url,
            appimage_name=str(github_api.appimage_name),
            hash_type=github_api.hash_type or "sha256",
        )

        # Set downloaded file path for verification
        if downloaded_file_path:
            verification_manager.set_appimage_path(downloaded_file_path)
            self._logger.info(f"Using specific file path for verification: {downloaded_file_path}")

        # Verify and clean up on failure if requested
        verification_result = verification_manager.verify_appimage(
            cleanup_on_failure=cleanup_on_failure
        )
        # Return the result along with verification_skipped flag (False in this case)
        return verification_result, verification_skipped

    def _create_file_handler(
        self,
        github_api: GitHubAPI,
        app_config: AppConfigManager,
        global_config: GlobalConfigManager,
    ) -> FileHandler:
        """Create a FileHandler instance with proper configuration."""
        # Ensure critical FileHandler parameters are not None
        required_fh_params = {
            "appimage_name": github_api.appimage_name,
            "repo": github_api.repo,
            "owner": github_api.owner,
            "version": github_api.version,
            "app_display_name": app_config.app_display_name,
        }

        for param, value in required_fh_params.items():
            if value is None:
                raise ValueError(
                    f"FileHandler critical parameter '{param}' is None before instantiation for {github_api.owner}/{github_api.repo}."
                )

        from pathlib import Path

        return FileHandler(
            appimage_name=str(github_api.appimage_name),
            repo=str(github_api.repo),
            owner=str(github_api.owner),
            version=str(github_api.version),
            sha_name=github_api.sha_name,
            config_file=str(global_config.config_file),
            app_storage_path=Path(global_config.expanded_app_storage_path),
            app_backup_storage_path=Path(global_config.expanded_app_backup_storage_path),
            config_folder=str(app_config.config_folder) if app_config.config_folder else None,
            config_file_name=app_config.config_file_name,
            batch_mode=global_config.batch_mode,
            keep_backup=global_config.keep_backup,
            max_backups=global_config.max_backups,
            app_display_name=str(app_config.app_display_name),
        )

    def _should_retry_download(self, attempt: int, max_attempts: int) -> bool:
        """Ask user if they want to retry a failed download."""
        try:
            return input("Retry download? (y/N): ").strip().lower() == "y"
        except KeyboardInterrupt:
            self._logger.info("Retry cancelled by user (Ctrl+C)")
            print("\nRetry cancelled by user (Ctrl+C)")
            return False

    def _display_update_list(self, updatable_apps: List[Dict[str, Any]]) -> None:
        """Display list of apps to update."""
        print(f"\nFound {len(updatable_apps)} apps to update:")
        for idx, app in enumerate(updatable_apps, 1):
            update_msg = f"{idx}. {app['name']} ({app['current']} → {app['latest']})"
            self._logger.info(update_msg)
            print(update_msg)

    def _check_single_app_version(
        self, app_config: AppConfigManager, config_file: str
    ) -> Optional[Dict[str, Any]]:
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

        # Set the app name in config manager to enable property access
        app_config.set_app_name(app_name)

        # Load user config (version, appimage_name)
        app_config.load_appimage_config(config_file)
        current_version = app_config.version

        # Initialize GitHub API using app definition data
        github_api = GitHubAPI(
            owner=app_info.owner,
            repo=app_info.repo,
            sha_name=app_info.sha_name,
            hash_type=app_info.hash_type,
            arch_keyword=None,  # Use app definition's preferred_characteristic_suffixes
        )

        update_available, version_info = github_api.check_latest_version(current_version)
        latest_version = version_info.get("latest_version") if update_available else None

        if "error" in version_info:
            return {
                "config_file": config_file,
                "name": app_name,
                "error": version_info["error"],
            }
        elif latest_version and latest_version != current_version:
            self._logger.info(
                f"Update available for {app_info.repo}: {current_version} → {latest_version}"
            )
            return {
                "config_file": config_file,
                "name": app_name,
                "current": current_version,
                "latest": latest_version,
            }
        return None
