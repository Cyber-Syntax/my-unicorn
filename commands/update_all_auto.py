from commands.base import Command
import logging
import os
from typing import List, Dict, Any
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler


class UpdateAllAutoCommand(Command):
    """Command to automatically check and update all AppImages without manual selection."""

    def __init__(self):
        """Initialize with necessary configuration managers."""
        self.global_config = GlobalConfigManager()
        self.app_config = AppConfigManager()

    def execute(self):
        """Check all AppImage configurations and update those with new versions available."""
        logging.info("Starting automatic check of all AppImages")
        print("Checking all AppImages for updates...")

        # Load global configuration
        self.global_config.load_config()

        # Find all updatable apps
        updatable_apps = self._find_all_updatable_apps()

        if not updatable_apps:
            print("All AppImages are up to date!")
            return

        # Display updatable apps to user
        print(f"\nFound {len(updatable_apps)} AppImages with updates available:")
        for idx, app in enumerate(updatable_apps, 1):
            print(f"{idx}. {app['name']} ({app['current']} → {app['latest']})")

        # Determine what to do based on batch mode
        if self.global_config.batch_mode:
            print(
                f"Batch mode enabled - updating all {len(updatable_apps)} AppImages automatically"
            )
            self._update_apps(updatable_apps)
        else:
            # In interactive mode, ask which apps to update
            self._handle_interactive_update(updatable_apps)

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
                print("No AppImage configuration files found. Use the Download option first.")
                return []

            print(f"Checking {len(json_files)} AppImage configurations...")

            # Check each app for updates
            for config_file in json_files:
                try:
                    # Load the app configuration
                    self.app_config.load_appimage_config(config_file)
                    app_name = os.path.splitext(config_file)[0]  # Remove .json extension

                    print(f"Checking {app_name}...", end="", flush=True)

                    # Check if update is available
                    github_api = GitHubAPI(
                        owner=self.app_config.owner,
                        repo=self.app_config.repo,
                        sha_name=self.app_config.sha_name,
                        hash_type=self.app_config.hash_type,
                    )

                    latest_version = github_api.check_latest_version(
                        owner=self.app_config.owner, repo=self.app_config.repo
                    )

                    if latest_version and latest_version != self.app_config.version:
                        print(f" update available: {self.app_config.version} → {latest_version}")

                        # Add to updatable list
                        updatable_apps.append(
                            {
                                "config_file": config_file,
                                "name": app_name,
                                "current": self.app_config.version,
                                "latest": latest_version,
                            }
                        )
                    else:
                        print(" already up to date")

                except Exception as e:
                    print(f" error: {str(e)}")

        except Exception as e:
            print(f"Error during update check: {str(e)}")

        return updatable_apps

    def _list_all_config_files(self) -> List[str]:
        """Get a list of all AppImage configuration files."""
        return self.app_config.list_json_files()

    def _handle_interactive_update(self, updatable_apps: List[Dict[str, Any]]) -> None:
        """
        Handle interactive mode where user selects which apps to update.

        Args:
            updatable_apps: List of updatable app information dictionaries
        """
        # Ask user which apps to update
        print("\nEnter the numbers of the AppImages you want to update (comma-separated):")
        print("For example: 1,3,4 or 'all' for all apps, or 'cancel' to exit")

        user_input = input("> ").strip().lower()

        if user_input == "cancel":
            print("Update cancelled.")
            return

        if user_input == "all":
            self._update_apps(updatable_apps)
            return

        try:
            # Parse user selection
            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]

            # Validate indices
            if any(idx < 0 or idx >= len(updatable_apps) for idx in selected_indices):
                print("Invalid selection. Please enter valid numbers.")
                return

            # Create list of selected apps
            selected_apps = [updatable_apps[idx] for idx in selected_indices]

            if selected_apps:
                print(f"Updating {len(selected_apps)} selected AppImages...")
                self._update_apps(selected_apps)
            else:
                print("No apps selected for update.")

        except ValueError:
            print("Invalid input. Please enter numbers separated by commas.")

    def _update_apps(self, apps_to_update: List[Dict[str, Any]]) -> None:
        """
        Update the specified apps.

        Args:
            apps_to_update: List of app information dictionaries to update
        """
        for app_data in apps_to_update:
            try:
                print(f"\nUpdating {app_data['name']}...")

                # 1. Load app config
                self.app_config.load_appimage_config(app_data["config_file"])

                # 2. Initialize GitHub API and get release info
                github_api = GitHubAPI(
                    owner=self.app_config.owner,
                    repo=self.app_config.repo,
                    sha_name=self.app_config.sha_name,
                    hash_type=self.app_config.hash_type,
                    arch_keyword=self.app_config.arch_keyword,
                )

                # Get release data
                github_api.get_response()

                # 3. Download AppImage
                print(f"Downloading {github_api.appimage_name}...")
                DownloadManager(github_api).download()

                # 4. Verify the download if SHA file is available
                if github_api.sha_name != "no_sha_file":
                    print("Verifying download...")
                    if not VerificationManager(
                        sha_name=github_api.sha_name,
                        sha_url=github_api.sha_url,
                        appimage_name=github_api.appimage_name,
                        hash_type=github_api.hash_type,
                    ).verify_appimage():
                        print(f"Verification failed for {app_data['name']}. Skipping.")
                        continue
                else:
                    print("Skipping verification (no SHA file available)")

                # 5. Handle file operations
                file_handler = FileHandler(
                    appimage_name=github_api.appimage_name,
                    repo=github_api.repo,
                    version=github_api.version,
                    sha_name=github_api.sha_name,
                    config_file=self.global_config.config_file,
                    appimage_download_folder_path=self.global_config.expanded_appimage_download_folder_path,
                    appimage_download_backup_folder_path=self.global_config.expanded_appimage_download_backup_folder_path,
                    config_folder=self.app_config.config_folder,
                    config_file_name=self.app_config.config_file_name,
                    batch_mode=self.global_config.batch_mode,
                    keep_backup=self.global_config.keep_backup,
                )

                # Try to download icon
                icon_success, icon_msg = file_handler.download_app_icon(
                    github_api.owner, github_api.repo
                )
                if icon_success:
                    print(f"Icon installed: {icon_msg}")

                # Perform file operations
                if file_handler.handle_appimage_operations():
                    # Update config file with new version
                    self.app_config.update_version(
                        new_version=github_api.version,
                        new_appimage_name=github_api.appimage_name,
                    )
                    print(
                        f"Successfully updated {app_data['name']} to version {github_api.version}"
                    )
                else:
                    print(f"Failed to update {app_data['name']}")

            except Exception as e:
                print(f"Error updating {app_data['name']}: {str(e)}")
                print("Continuing with next app...")

            print(f"Finished processing {app_data['name']}")

        print("\nUpdate process completed!")
