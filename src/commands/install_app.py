#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Install app by name command module.

This module provides a command to install applications from the app catalog
by name, without requiring the user to enter URLs.
"""

import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from src.commands.base import Command
from src.app_catalog import (
    APP_CATALOG,
    get_app_info,
    get_all_apps,
    get_apps_by_category,
    get_categories,
    search_apps,
    AppInfo,
)
from src.api import GitHubAPI
from src.app_config import AppConfigManager
from src.download import DownloadManager
from src.file_handler import FileHandler
from src.global_config import GlobalConfigManager
from src.verify import VerificationManager
from src.icon_manager import IconManager


class InstallAppCommand(Command):
    """Command to install an application from the catalog by name."""

    # Maximum number of download/verification attempts
    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        """Initialize the command with configuration managers."""
        self._logger = logging.getLogger(__name__)
        self.global_config = GlobalConfigManager()
        self.global_config.load_config()

    def execute(self) -> None:
        """Execute the install app command to browse and install applications."""
        print("\n=== Install Application ===")

        # Show browsing options
        self._display_browse_menu()

    def _display_browse_menu(self) -> None:
        """Display menu for browsing applications."""
        while True:
            print("\nHow would you like to browse applications?")
            print("1. View all applications")
            print("2. Browse by category")
            print("3. Search by name or keyword")
            print("4. Return to main menu")

            try:
                choice = int(input("\nEnter your choice: "))

                if choice == 1:
                    self._display_all_apps()
                elif choice == 2:
                    self._browse_by_category()
                elif choice == 3:
                    self._search_apps()
                elif choice == 4:
                    return
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return

    def _display_all_apps(self) -> None:
        """Display and allow selection from all applications."""
        apps = get_all_apps()
        self._display_app_list(apps)

    def _browse_by_category(self) -> None:
        """Browse applications by category."""
        categories = get_categories()

        print("\n=== Application Categories ===")
        for idx, category in enumerate(categories, 1):
            print(f"{idx}. {category}")

        try:
            choice = int(input("\nSelect a category (0 to go back): "))
            if choice == 0:
                return

            if 1 <= choice <= len(categories):
                category = categories[choice - 1]
                apps = get_apps_by_category(category)
                print(f"\n=== Applications in {category} ===")
                self._display_app_list(apps)
            else:
                print("Invalid choice.")
        except ValueError:
            print("Please enter a number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")

    def _search_apps(self) -> None:
        """Search for applications by name or keyword."""
        try:
            query = input("\nEnter search term: ")
            if not query:
                return

            results = search_apps(query)

            if not results:
                print(f"No applications found matching '{query}'.")
                return

            print(f"\n=== Search Results for '{query}' ===")
            self._display_app_list(results)
        except KeyboardInterrupt:
            print("\nSearch cancelled.")

    def _display_app_list(self, apps: List[AppInfo]) -> None:
        """
        Display a list of applications and allow user to select one for installation.

        Args:
            apps: List of AppInfo objects to display
        """
        if not apps:
            print("No applications available in this category.")
            return

        # Sort apps alphabetically by name
        apps = sorted(apps, key=lambda app: app.name)

        print(f"\nFound {len(apps)} applications:")
        for idx, app in enumerate(apps, 1):
            print(f"{idx}. {app.name} - {app.description}")

        try:
            choice = int(input("\nSelect an application to install (0 to go back): "))
            if choice == 0:
                return

            if 1 <= choice <= len(apps):
                selected_app = apps[choice - 1]
                self._confirm_and_install_app(selected_app)
            else:
                print("Invalid choice.")
        except ValueError:
            print("Please enter a number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")

    def _confirm_and_install_app(self, app_info: AppInfo) -> None:
        """
        Confirm and install the selected application.

        Args:
            app_info: AppInfo object for the selected application
        """
        print(f"\n=== Install {app_info.name} ===")
        print(f"Name: {app_info.name}")
        print(f"Description: {app_info.description}")
        print(f"Repository: {app_info.owner}/{app_info.repo}")
        print(f"Category: {app_info.category}")
        if app_info.tags:
            print(f"Tags: {', '.join(app_info.tags)}")

        try:
            confirm = input("\nInstall this application? (y/N): ").strip().lower()
            if confirm != "y":
                print("Installation cancelled.")
                return

            print(f"\nInstalling {app_info.name}...")
            self._install_app(app_info)
        except KeyboardInterrupt:
            print("\nInstallation cancelled.")

    def _install_app(self, app_info: AppInfo) -> None:
        """
        Download and install the application with verification.
        """
        # Create a properly initialized app config manager for this app
        app_config = AppConfigManager(
            owner=app_info.owner,
            repo=app_info.repo,
            app_id=app_info.app_id,  # Pass the app_id from catalog
        )

        # Initialize GitHubAPI with parameters based on app catalog information
        if app_info.sha_name != "no_sha_file":
            # Use the SHA file and hash type from app catalog directly (trusted source)
            api = GitHubAPI(
                owner=app_info.owner,
                repo=app_info.repo,
                sha_name=app_info.sha_name,
                hash_type=app_info.hash_type,
                arch_keyword=None,  # Enable architecture auto-detection
            )
            self._logger.debug(f"Using SHA file from app catalog: {app_info.sha_name}")
        else:
            # No SHA file in catalog, let API auto-detect
            api = GitHubAPI(
                owner=app_info.owner,
                repo=app_info.repo,
                sha_name="auto",  # Use "auto" to enable automatic SHA detection
                hash_type="auto",  # Use "auto" to enable automatic hash type detection
                arch_keyword=None,  # Enable architecture auto-detection
            )
            self._logger.debug("Using automatic SHA file detection")

        # Get release data to allow API's auto-detection to work
        success, response = api.get_response()
        if not success:
            print(f"Error: {response}")
            return

        # Log what was detected by the API
        self._logger.debug(
            f"API detection results: appimage={api.appimage_name}, "
            f"sha={api.sha_name}, hash_type={api.hash_type}, arch={api.arch_keyword}"
        )

        # Track verification success across attempts
        verification_success = False

        # Try up to MAX_ATTEMPTS times to download and verify
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                # Update app config with all API data
                app_config.owner = api.owner
                app_config.repo = api.repo
                app_config.version = api.version
                app_config.appimage_name = api.appimage_name
                app_config.arch_keyword = api.arch_keyword
                app_config.sha_name = api.sha_name
                app_config.hash_type = api.hash_type

                # Ensure config is saved (temporarily) before download
                app_config.temp_save_config()

                # Log config paths for debugging
                self._logger.debug(f"Config folder: {app_config.config_folder}")
                self._logger.debug(f"Config file: {app_config.config_file}")

                # Download the AppImage
                print(f"Downloading {api.appimage_name}...")
                download = DownloadManager(api)
                downloaded_file_path = (
                    download.download()
                )  # Capture the full path to the downloaded file

                # Handle verification based on SHA file availability
                if api.sha_name == "no_sha_file":
                    logging.info("Skipping verification due to no_sha_file setting.")
                    print("Skipping verification (no SHA file specified).")
                    verification_success = True
                    break
                else:
                    # Perform verification with cleanup on failure
                    print("Verifying download integrity...")
                    verification_manager = VerificationManager(
                        sha_name=api.sha_name,
                        sha_url=api.sha_url,
                        appimage_name=api.appimage_name,
                        hash_type=api.hash_type,
                    )

                    # Set the full path to the downloaded file
                    verification_manager.set_appimage_path(downloaded_file_path)

                    is_valid = verification_manager.verify_appimage(cleanup_on_failure=True)

                    if is_valid:
                        verification_success = True
                        print("Verification successful!")
                        break
                    else:
                        # Verification failed
                        if attempt == self.MAX_ATTEMPTS:
                            print(
                                f"Verification failed. Maximum retry attempts ({self.MAX_ATTEMPTS}) reached."
                            )
                            return
                        else:
                            print(f"Verification failed. Attempt {attempt} of {self.MAX_ATTEMPTS}.")
                            retry = input("Retry download? (y/N): ").strip().lower()
                            if retry != "y":
                                print("Installation cancelled.")
                                return
                            # Continue to next attempt

            except Exception as e:
                logging.error(f"Download attempt {attempt} failed: {str(e)}", exc_info=True)
                print(f"Error during download: {str(e)}")

                if attempt == self.MAX_ATTEMPTS:
                    print(f"Maximum retry attempts ({self.MAX_ATTEMPTS}) reached.")
                    return
                else:
                    print(f"Download failed. Attempt {attempt} of {self.MAX_ATTEMPTS}.")
                    retry = input("Retry download? (y/N): ").strip().lower()
                    if retry != "y":
                        print("Installation cancelled.")
                        return

        # If verification wasn't successful after all attempts, exit
        if not verification_success:
            return

        # Handle file operations
        file_handler = FileHandler(
            appimage_name=api.appimage_name,
            repo=api.repo,
            owner=api.owner,
            version=api.version,
            sha_name=api.sha_name,
            config_file=self.global_config.config_file,
            appimage_download_folder_path=self.global_config.expanded_appimage_download_folder_path,
            appimage_download_backup_folder_path=self.global_config.expanded_appimage_download_backup_folder_path,
            config_folder=app_config.config_folder,
            config_file_name=app_config.config_file_name,
            batch_mode=self.global_config.batch_mode,
            keep_backup=self.global_config.keep_backup,
            max_backups=self.global_config.max_backups,
            app_id=app_info.app_id,  # Pass app_id from app_info to FileHandler
        )

        # Download app icon if possible
        icon_manager = IconManager()
        icon_manager.ensure_app_icon(api.owner, api.repo)

        # Perform file operations
        print("Finalizing installation...")
        success = file_handler.handle_appimage_operations(github_api=api)

        if success:
            # Save the configuration only if all previous steps succeed
            app_config.save_config()

            # Display success message with paths
            print(f"\n✅ {app_info.name} successfully installed!")

            # Show config file location
            config_path = Path(app_config.config_file)
            print(f"Config file created at: {config_path}")

            # Show location of executable
            app_path = (
                Path(self.global_config.expanded_appimage_download_folder_path) / api.appimage_name
            )
            print(f"Application installed to: {app_path}")
            print("You can run it from the command line or create a desktop shortcut.")
        else:
            print("Error during file operations. Installation failed.")
            return
