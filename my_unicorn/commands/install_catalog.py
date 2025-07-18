#!/usr/bin/env python3
"""Install app by name command module.

This module provides a command to install applications from the app catalog
by name, without requiring the user to enter URLs.
"""

import logging
from pathlib import Path

from my_unicorn.api.github_api import GitHubAPI
from my_unicorn.app_config import AppConfigManager
from my_unicorn.catalog import AppInfo, get_all_apps
from my_unicorn.commands.base import Command
from my_unicorn.download import DownloadManager
from my_unicorn.file_handler import FileHandler
from my_unicorn.global_config import GlobalConfigManager
from my_unicorn.icon_manager import IconManager
from my_unicorn.verify import VerificationManager

logger = logging.getLogger(__name__)


class InstallAppCommand(Command):
    """Command to install an application from the catalog by name."""

    # Maximum number of download/verification attempts
    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        """Initialize the command with configuration managers."""
        self.global_config = GlobalConfigManager()
        self.global_config.load_config()
        self._app_name = None
        self._cli_mode = False

    def set_app_name(self, app_name: str) -> None:
        """Set the app name for direct installation."""
        self._app_name = app_name
        self._cli_mode = True

    def list_apps(self) -> None:
        """List all available applications in the catalog."""
        apps = get_all_apps()
        if not apps:
            print("No applications available in catalog.")
            return

        # Sort apps alphabetically by app_rename
        sorted_apps = sorted(apps.values(), key=lambda app: app.app_rename)

        print(f"\n=== Available Applications ({len(sorted_apps)}) ===")
        print("-" * 60)

        for app in sorted_apps:
            print(f"Name: {app.app_rename}")
            print(f"  Repository: {app.owner}/{app.repo}")
            print(f"  Description: {app.description}")
            print(f"  Category: {app.category}")
            if app.tags:
                print(f"  Tags: {', '.join(app.tags)}")
            print()

        print("Usage: python run.py install <app_name>")
        print("Example: python run.py install joplin")

    def execute(self) -> None:
        """Execute the install app command to browse and install applications."""
        print("\n=== Install Application ===")

        # If app name is provided via CLI, install directly
        if self._app_name:
            self._install_app_by_name(self._app_name)
            return

        # Show browsing options
        self._display_browse_menu()

    def _install_app_by_name(self, app_name: str) -> None:
        """Install an application by name directly.

        Args:
            app_name: Name of the application to install

        """
        apps = get_all_apps()

        # Simple lowercase matching - check if app_name (lowercase) exists as a key
        app_name_lower = app_name.lower()

        if app_name_lower in apps:
            app_info = apps[app_name_lower]
            self._confirm_and_install_app(app_info)
            return

        # If not found, show available apps
        print(f"Application '{app_name}' not found in catalog.")
        print("Available applications:")
        for repo_name, app in sorted(apps.items()):
            print(f"  - {repo_name} ({app.app_rename})")
        return

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

    def _display_all_apps(self) -> None:
        """Display and allow selection from all applications."""
        apps = get_all_apps()
        self._display_app_list(list(apps.values()))

    def _display_app_list(self, apps: list[AppInfo]) -> None:
        """Display a list of applications and allow user to select one for installation.

        Args:
            apps: list of AppInfo objects to display

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

        # In CLI mode, auto-confirm installation
        if self._cli_mode:
            print(f"\nInstalling {app_info.app_rename}...")
            self._install_app(app_info)
            return

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
        checksum_file_name_param = (
            app_info.checksum_file_name if app_info.checksum_file_name else "auto"
        )
        checksum_hash_type_param = (
            app_info.checksum_hash_type if app_info.checksum_hash_type else "auto"
        )

        api = GitHubAPI(
            owner=app_info.owner,
            repo=app_info.repo,
            checksum_file_name=checksum_file_name_param,
            checksum_hash_type=checksum_hash_type_param,
            arch_keyword=None,  # Enable architecture auto-detection
        )

        if app_info.checksum_file_name:
            logger.debug("Using SHA file from app catalog: %s", app_info.checksum_file_name)
        else:
            logger.debug("Using automatic SHA file detection")

        # Get release data with full processing including SHA/asset digest detection
        release_result = api.get_latest_release()
        if not release_result[0]:
            print(f"Error during processing: {release_result[1]}")
            return

        # Log what was detected by the API
        logger.debug(
            "API detection results: appimage=%s, sha=%s, checksum_hash_type=%s, arch=%s",
            api.appimage_name,
            api.checksum_file_name,
            api.checksum_hash_type,
            api.arch_keyword,
        )

        # Initialize progress bar for single download
        DownloadManager.get_or_create_progress(1)

        # Track verification success and skip status across attempts
        verification_success = False
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

                    # Debug logger.for API values
                    logger.debug("API values before VerificationManager creation:")
                    logger.debug("  api.checksum_file_name: %s", api.checksum_file_name)
                    logger.debug("  api.checksum_hash_type: %s", api.checksum_hash_type)
                    logger.debug("  api.asset_digest: %s", api.asset_digest)
                    logger.debug("  api.skip_verification: %s", api.skip_verification)

                    verification_manager = VerificationManager(
                        checksum_file_name=api.checksum_file_name,
                        checksum_file_download_url=api.checksum_file_download_url,
                        appimage_name=api.appimage_name,
                        checksum_hash_type=api.checksum_hash_type or "sha256",
                        asset_digest=api.asset_digest,
                    )

                    # Define verification status message
                    verification_status_message = (
                        "Verification skipped: no hash file provided."
                        if api.skip_verification
                        else "Verification completed successfully."
                    )

                    # set the full path to the downloaded file
                    verification_manager.set_appimage_path(downloaded_file_path)
                    is_valid, verification_skipped = verification_manager.verify_for_update(
                        downloaded_file_path, cleanup_on_failure=True
                    )

                    if is_valid:
                        verification_success = True
                        print(f"Verification successful! {verification_status_message}")
                        break
                    # Verification failed
                    elif attempt == self.MAX_ATTEMPTS:
                        print(
                            f"Verification failed. Maximum retry attempts ({self.MAX_ATTEMPTS}) reached."
                        )
                        return
                    else:
                        print(
                            f"Verification failed. Attempt {attempt} of {self.MAX_ATTEMPTS}."
                        )
                        retry = input("Retry download? (y/N): ").strip().lower()
                        if retry != "y":
                            print("Installation cancelled.")
                            return

            except Exception as e:
                logger.error("Download attempt %s failed: %s", attempt, e, exc_info=True)
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
            # Clean up progress display
            DownloadManager.stop_progress()
            return

        # Handle file operations
        file_handler = FileHandler(
            appimage_name=api.appimage_name,
            repo=api.repo,
            owner=api.owner,
            version=api.version,
            checksum_file_name=api.checksum_file_name,
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
            icon_path=icon_path if icon_success else None
        )

        # Clean up progress display
        DownloadManager.stop_progress()

        if success:
            # Save the configuration only if all previous steps succeed
            app_config.save_config()

            # # Display success message with paths
            # if verification_skipped:
            #     print(f"\n✅ {app_info.app_rename} successfully installed!")
            #     print("⚠️ Note: AppImage was not verified because developers did not provide")
            #     print("   a SHA file for this AppImage.")
            # else:
            #     print(f"\n✅ {app_info.app_rename} successfully installed and verified!")

            # Show config file location
            if app_config.config_file:
                config_path = Path(app_config.config_file)
                print(f"Config file created at: {config_path}")
                print(f"Verification status: {verification_status_message}")

            # Show location of executable
            if api.appimage_name:
                app_path = (
                    Path(self.global_config.expanded_app_storage_path) / api.appimage_name
                )
                print(f"Application installed to: {app_path}")
                print("You can run it from the command line or create a desktop shortcut.")
        else:
            print("Error during file operations. Installation failed.")
