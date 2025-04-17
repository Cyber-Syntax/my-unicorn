#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base update command module.

This module provides a base class for AppImage update commands with common
functionality for version checking and update operations.
"""

import logging
import os
from typing import List, Dict, Any, Optional, Tuple

from src.commands.base import Command
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler


class BaseUpdateCommand(Command):
    """
    Base class for AppImage update commands.

    This class provides common functionality for checking and updating AppImages,
    to be inherited by specific update command implementations.
    """

    def __init__(self):
        """Initialize base update command with necessary configuration managers."""
        self.global_config = GlobalConfigManager()
        self.app_config = AppConfigManager()
        self._logger = logging.getLogger(__name__)

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
        github_api.get_response()

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
        icon_success, icon_msg = file_handler.download_app_icon(github_api.owner, github_api.repo)
        if icon_success:
            print(f"Icon installed: {icon_msg}")
        else:
            print(f"No icon installed: {icon_msg}")

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
            repo=github_api.repo,  # Use repo directly without lowering
            version=github_api.version,
            sha_name=github_api.sha_name,
            config_file=global_config.config_file,
            appimage_download_folder_path=global_config.expanded_appimage_download_folder_path,
            appimage_download_backup_folder_path=global_config.expanded_appimage_download_backup_folder_path,
            config_folder=app_config.config_folder,
            config_file_name=app_config.config_file_name,
            batch_mode=global_config.batch_mode,
            keep_backup=global_config.keep_backup,
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
        return input("Retry download? (y/N): ").strip().lower() == "y"

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

        latest_version = github_api.check_latest_version(
            owner=app_config.owner, repo=app_config.repo
        )

        if latest_version and latest_version != current_version:
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
