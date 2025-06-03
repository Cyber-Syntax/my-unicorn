#!/usr/bin/env python3
"""Install app by name command module.

This module provides a command to install applications from the app catalog
by name, without requiring the user to enter URLs.
"""

import logging
from pathlib import Path

from src.api.github_api import GitHubAPI
from src.app_catalog import AppInfo, get_all_apps
from src.app_config import AppConfigManager
from src.commands.base import Command
from src.download import DownloadManager
from src.file_handler import FileHandler
from src.global_config import GlobalConfigManager
from src.icon_manager import IconManager
from src.verify import VerificationManager


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
            print("2. Return to main menu")

            try:
                choice = int(input("\nEnter your choice: "))

                if choice == 1:
                    self._display_all_apps()
                elif choice == 2:
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
        self._display_app_list(list(apps.values()))

    def _display_app_list(self, apps: list[AppInfo]) -> None:
        """Display a list of applications and allow user to select one for installation.

        Args:
            apps: List of AppInfo objects to display

        """
        if not apps:
            print("No applications available.")
            return

        # Sort apps alphabetically by app_rename
        apps = sorted(apps, key=lambda app: app.app_rename)

        print(f"\nFound {len(apps)} applications:")
        for idx, app in enumerate(apps, 1):
            print(f"{idx}. {app.app_rename} - {app.description}")

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
        """Confirm and install the selected application.

        Args:
            app_info: AppInfo object for the selected application

        """
        print(f"\n=== Install {app_info.app_rename} ===")
        print(f"Name: {app_info.app_rename}")
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

            print(f"\nInstalling {app_info.app_rename}...")
            self._install_app(app_info)
        except KeyboardInterrupt:
            print("\nInstallation cancelled.")

    def _install_app(self, app_info: AppInfo) -> None:
        """Download and install the application with verification."""
        # Create a properly initialized app config manager for this app
        app_config = AppConfigManager()
        app_config.set_app_name(app_info.repo)

        # Initialize GitHubAPI with proper parameters
        # Use auto-detection when no specific values are provided
        sha_name_param = app_info.sha_name if app_info.sha_name else "auto"
        hash_type_param = app_info.hash_type if app_info.hash_type else "auto"
        
        api = GitHubAPI(
            owner=app_info.owner,
            repo=app_info.repo,
            sha_name=sha_name_param,
            hash_type=hash_type_param,
            arch_keyword=None,  # Enable architecture auto-detection
        )
        
        if app_info.sha_name:
            self._logger.debug(f"Using SHA file from app catalog: {app_info.sha_name}")
        else:
            self._logger.debug("Using automatic SHA file detection")

        # Get release data with full processing including SHA/asset digest detection
        success, full_response = api.get_latest_release()
        if not success:
            print(f"Error during processing: {full_response}")
            return

        # Log what was detected by the API
        self._logger.debug(
            f"API detection results: appimage={api.appimage_name}, "
            f"sha={api.sha_name}, hash_type={api.hash_type}, arch={api.arch_keyword}"
        )

        # Track verification success and skip status across attempts
        verification_success = False
        verification_skipped = False  # New flag to track if verification was skipped
        downloaded_file_path: str | None = None

        # Try up to MAX_ATTEMPTS times to download and verify
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                # Update app config with user-specific data (version and appimage_name are stored in config)
                app_config.version = api.version
                app_config.appimage_name = api.appimage_name

                # Ensure config is saved (temporarily) before download
                app_config.temp_save_config()

                # Download the AppImage or get existing file
                if api.appimage_name:
                    download = DownloadManager(api)
                    downloaded_file_path, was_existing_file = download.download()

                    if not downloaded_file_path:
                        raise ValueError("Download failed: No file path returned")

                    if was_existing_file:
                        print(f"Found existing file: {api.appimage_name}")
                    else:
                        print(f"✓ Downloaded {api.appimage_name}")

                    # Handle verification based on skip_verification flag
                    if app_config.skip_verification or api.skip_verification:
                        logging.info("Skipping verification due to skip_verification setting.")
                        print("Skipping verification (verification disabled for this app).")
                        verification_success = True
                        verification_skipped = True  # Set the flag that verification was skipped
                        break
                    else:
                        # Single verification point for both existing and downloaded files
                        if was_existing_file:
                            print("Verifying existing file...")
                        else:
                            print("Verifying download integrity...")
                        
                        # Debug logging for API values
                        logging.debug(f"API values before VerificationManager creation:")
                        logging.debug(f"  api.sha_name: {api.sha_name}")
                        logging.debug(f"  api.hash_type: {api.hash_type}")
                        logging.debug(f"  api.asset_digest: {api.asset_digest}")
                        logging.debug(f"  api.skip_verification: {api.skip_verification}")
                        
                        verification_manager = VerificationManager(
                            sha_name=api.sha_name,
                            sha_url=api.sha_url,
                            appimage_name=api.appimage_name,
                            hash_type=api.hash_type,
                            asset_digest=api.asset_digest,
                        )

                        # Set the full path to the downloaded file
                        verification_manager.set_appimage_path(downloaded_file_path)
                        is_valid = verification_manager.verify_appimage(cleanup_on_failure=True)

                        if is_valid:
                            verification_success = True
                            print("Verification successful!")
                            break
                        # Verification failed
                        elif attempt == self.MAX_ATTEMPTS:
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

            except Exception as e:
                logging.error(f"Download attempt {attempt} failed: {e!s}", exc_info=True)
                print(f"Error during download: {e!s}")

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
        if not verification_success or not downloaded_file_path or not api.appimage_name:
            return

        # Handle file operations
        file_handler = FileHandler(
            appimage_name=api.appimage_name,
            repo=api.repo,
            owner=api.owner,
            version=api.version,
            sha_name=api.sha_name,
            config_file=str(self.global_config.config_file),
            app_storage_path=Path(self.global_config.expanded_app_storage_path),
            app_backup_storage_path=Path(self.global_config.expanded_app_backup_storage_path),
            config_folder=str(app_config.config_folder) if app_config.config_folder else None,
            config_file_name=app_config.config_file_name,
            batch_mode=self.global_config.batch_mode,
            keep_backup=self.global_config.keep_backup,
            max_backups=self.global_config.max_backups,
            app_rename=app_info.app_rename,
        )

        # Download app icon if possible
        icon_manager = IconManager()
        icon_success, icon_path = icon_manager.ensure_app_icon(
            api.owner, api.repo, app_rename=app_info.app_rename
        )

        # Perform file operations
        print("Finalizing installation...")
        success = file_handler.handle_appimage_operations(
            github_api=api, icon_path=icon_path if icon_success else None
        )

        if success:
            # Save the configuration only if all previous steps succeed
            app_config.save_config()

            # Display success message with paths
            if verification_skipped:
                print(f"\n✅ {app_info.app_rename} successfully installed!")
                print("⚠️ Note: AppImage was not verified because developers did not provide")
                print("   a SHA file for this AppImage.")
            else:
                print(f"\n✅ {app_info.app_rename} successfully installed and verified!")

            # Show config file location
            if app_config.config_file:
                config_path = Path(app_config.config_file)
                print(f"Config file created at: {config_path}")

            # Show location of executable
            if api.appimage_name:
                app_path = Path(self.global_config.expanded_app_storage_path) / api.appimage_name
                print(f"Application installed to: {app_path}")
                print("You can run it from the command line or create a desktop shortcut.")
        else:
            print("Error during file operations. Installation failed.")
            return
