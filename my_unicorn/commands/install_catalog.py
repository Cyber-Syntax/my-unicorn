#!/usr/bin/env python3
"""Install app by name command module.

This module provides a command to install applications from the app catalog
by name, without requiring the user to enter URLs.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import override

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


@dataclass
class VerificationResult:
    """Verification result dataclass."""

    success: bool
    file_path: str | None = None
    status_msg: str = ""
    was_existing: bool = False


class InstallAppCommand(Command):
    """Command to install an application from the catalog by name."""

    # Maximum number of download/verification attempts
    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        """Initialize the command with configuration managers."""
        super().__init__()
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

    @override
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
        """Download, verify, and install the application."""
        # Setup phase
        app_config, api = self._setup_app_installation(app_info)
        if not api:
            return

        # Download and verification phase
        verification_result = self._download_and_verify_app(api, app_config)
        if not verification_result.success:
            return

        # Final installation phase
        self._finalize_installation(api, app_config, app_info, verification_result)

    # ----------------- Helper Methods -----------------

    def _setup_app_installation(
        self, app_info: AppInfo
    ) -> tuple[AppConfigManager, GitHubAPI | None]:
        """Initialize configuration and API for installation."""
        app_config = AppConfigManager()
        app_config.set_app_name(app_info.repo)

        checksum_file_name_param = app_info.checksum_file_name or "auto"
        checksum_hash_type_param = app_info.checksum_hash_type or "auto"

        api = GitHubAPI(
            owner=app_info.owner,
            repo=app_info.repo,
            checksum_file_name=checksum_file_name_param,
            checksum_hash_type=checksum_hash_type_param,
            arch_keyword=None,
        )

        # Get release data
        release_result = api.get_latest_release()
        if not release_result[0]:
            print(f"Error during processing: {release_result[1]}")
            return app_config, None

        logger.debug(
            "API detection: appimage=%s, sha=%s, hash_type=%s, arch=%s",
            api.appimage_name,
            api.checksum_file_name,
            api.checksum_hash_type,
            api.arch_keyword,
        )

        return app_config, api

    def _download_and_verify_app(
        self, api: GitHubAPI, app_config: AppConfigManager
    ) -> VerificationResult:
        """Handle download and verification with retry logic."""
        result = VerificationResult(success=False)

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                # Update config with version info
                app_config.version = api.version
                app_config.appimage_name = api.appimage_name
                app_config.temp_save_config()

                # Initialize progress bar for this attempt
                DownloadManager.get_or_create_progress(1)

                # Perform download
                result = self._attempt_download_and_verification(api, attempt)

                # Stop progress immediately after download before printing
                DownloadManager.stop_progress()

                if result.success:
                    return result

            except Exception as e:
                DownloadManager.stop_progress()
                logger.error("Download attempt %s failed: %s", attempt, e, exc_info=True)
                print(f"Error during download: {e!s}")

            # Handle retry logic
            if not self._should_retry(attempt, result):
                break

        return result

    def _attempt_download_and_verification(
        self, api: GitHubAPI, attempt: int
    ) -> VerificationResult:
        """Perform a single download and verification attempt."""
        if not api.appimage_name:
            raise ValueError("AppImage name not available")

        download = DownloadManager(api)
        downloaded_file_path, was_existing_file = download.download()

        # Handle download status
        if was_existing_file:
            print(f"Found existing file: {api.appimage_name}")
        else:
            print(f"✓ Downloaded {api.appimage_name}")

        # Create verification manager
        verification_manager = VerificationManager(
            checksum_file_name=api.checksum_file_name,
            checksum_file_download_url=api.checksum_file_download_url,
            appimage_name=api.appimage_name,
            checksum_hash_type=api.checksum_hash_type or "sha256",
            asset_digest=api.asset_digest,
        )
        verification_manager.set_appimage_path(downloaded_file_path)

        # Perform verification
        is_valid, verification_skipped = verification_manager.verify_for_update(
            downloaded_file_path, cleanup_on_failure=True
        )

        # Handle verification result
        if is_valid:
            status_msg = (
                "Verification skipped: no hash file provided."
                if verification_skipped
                else "Verification successful."
            )
            print(status_msg)
            return VerificationResult(
                success=True,
                file_path=downloaded_file_path,
                status_msg=status_msg,
                was_existing=was_existing_file,
            )

        # Verification failed
        print(f"Verification failed. Attempt {attempt} of {self.MAX_ATTEMPTS}.")
        return VerificationResult(success=False)

    def _should_retry(self, attempt: int, result: VerificationResult) -> bool:
        """Determine if we should retry the download."""
        if attempt >= self.MAX_ATTEMPTS:
            print(f"Maximum retry attempts ({self.MAX_ATTEMPTS}) reached.")
            return False

        if result.success:
            return False

        retry = input("Retry download? (y/N): ").strip().lower()
        if retry != "y":
            print("Installation cancelled.")
            return False

        return True

    def _finalize_installation(
        self,
        api: GitHubAPI,
        app_config: AppConfigManager,
        app_info: AppInfo,
        verification_result: VerificationResult,
    ) -> None:
        """Handle final installation steps."""
        try:
            # Create file handler
            file_handler = FileHandler(
                appimage_name=api.appimage_name,
                repo=api.repo,
                owner=api.owner,
                version=api.version,
                checksum_file_name=api.checksum_file_name,
                config_file=str(self.global_config.config_file),
                app_storage_path=Path(self.global_config.expanded_app_storage_path),
                app_backup_storage_path=Path(
                    self.global_config.expanded_app_backup_storage_path
                ),
                config_folder=str(app_config.config_folder)
                if app_config.config_folder
                else None,
                config_file_name=app_config.config_file_name,
                batch_mode=self.global_config.batch_mode,
                keep_backup=self.global_config.keep_backup,
                max_backups=self.global_config.max_backups,
                app_rename=app_info.app_rename,
            )

            # Download icon
            icon_manager = IconManager()
            icon_success, icon_path = icon_manager.ensure_app_icon(
                api.owner, api.repo, app_rename=app_info.app_rename
            )

            # Perform file operations
            print("Finalizing installation...")
            success = file_handler.handle_appimage_operations(
                icon_path=icon_path if icon_success else None
            )

            if success:
                app_config.save_config()
                self._show_installation_details(api, app_config, verification_result)
            else:
                print("Error during file operations. Installation failed.")

        finally:
            DownloadManager.stop_progress()

    def _show_installation_details(
        self,
        api: GitHubAPI,
        app_config: AppConfigManager,
        verification_result: VerificationResult,
    ) -> None:
        """Display installation success details."""
        if app_config.config_file:
            config_path = Path(app_config.config_file)
            print(f"Config file created at: {config_path}")
            print(f"Verification status: {verification_result.status_msg}")

        if api.appimage_name:
            app_path = Path(self.global_config.expanded_app_storage_path) / api.appimage_name
            print(f"Application installed to: {app_path}")
            print("You can run it from the command line or create a desktop shortcut.")

    # ----------------- Data Classes -----------------
