
import os
import logging
from .api import GitHubAPI
from .verify import VerificationManager
from .download import DownloadManager
from .file_handler import FileHandler


class AppImageUpdater:
    """Handles the AppImage update process."""

    def __init__(self, app_config, global_config):
        self.app_config = app_config
        self.global_config = global_config

    def select_files(self):
        """List available JSON configuration files and allow the user to select multiple."""
        json_files = self.app_config.list_json_files()
        if not json_files:
            print("No configuration files found. Please create one first.")
            return None

        print("Available configuration files:")
        for idx, json_file in enumerate(json_files, start=1):
            print(f"{idx}. {json_file}")

        user_input = input(
            "Enter the numbers of the configuration files you want to update (comma-separated): "
        ).strip()

        try:
            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]
            if any(idx < 0 or idx >= len(json_files) for idx in selected_indices):
                raise ValueError("Invalid selection.")
            return [json_files[idx] for idx in selected_indices]
        except (ValueError, IndexError):
            print("Invalid selection. Please enter valid numbers.")
            return None

    def check_versions(self, selected_files):
        """Check if the AppImages in the selected configuration files need updates."""
        appimages_to_update = []

        for config_file in selected_files:
            self.app_config.load_appimage_config(config_file)

            # Initialize GitHubAPI
            github_api = GitHubAPI(
                owner=self.app_config.owner,
                repo=self.app_config.repo,
                sha_name=self.app_config.sha_name,
                hash_type=self.app_config.hash_type,
            )
            latest_version = github_api.check_latest_version(
                self.app_config.owner, self.app_config.repo
            )

            if latest_version and latest_version != self.app_config.version:
                print("-------------------------------------------------")
                print(f"{self.app_config.appimage_name} is not up to date")
                print(f"\033[42mLatest version: {self.app_config.version}\033[0m")
                print(f"Current version: {latest_version}")
                print("-------------------------------------------------")
                appimages_to_update.append(
                    {
                        "config_file": config_file,
                        "latest_version": latest_version,
                        "appimage_name": self.app_config.appimage_name,
                    }
                )
            else:
                print(
                    f"{self.app_config.appimage_name} is already up to date (version {self.app_config.version})."
                )

        return appimages_to_update

    def update_selected_appimages(self, appimages_to_update):
        """Update the selected AppImages."""
        for appimage_data in appimages_to_update:
            self.app_config.load_appimage_config(appimage_data["config_file"])
            self._update_appimage(appimage_data)

    def _update_appimage(self, appimage_data):
        """Update a single AppImage."""
        # Initialize GitHubAPI
        github_api = GitHubAPI(
            owner=self.app_config.owner,
            repo=self.app_config.repo,
            sha_name=self.app_config.sha_name,
            hash_type=self.app_config.hash_type,
        )
        github_api.get_response()

        # Download the new AppImage
        print(f"Downloading {self.app_config.appimage_name}...")
        download_manager = DownloadManager(github_api)
        download_manager.download()

        # Verify the AppImage
        verification_manager = VerificationManager(
            sha_name=github_api.sha_name,
            sha_url=github_api.sha_url,
            appimage_name=github_api.appimage_name,
            hash_type=github_api.hash_type,
        )
        if not verification_manager.verify_appimage():
            print(f"Verification failed for {self.app_config.appimage_name}. Update aborted.")
            return

        # Update configuration and handle file operations
        # self.app_config.version = appimage_data["latest_version"]

        file_handler = FileHandler(
            appimage_name=github_api.appimage_name,
            repo=github_api.repo,
            version=github_api.version,
            config_file=self.global_config.config_file,
            appimage_download_folder_path=self.global_config.expanded_appimage_download_folder_path,
            appimage_download_backup_folder_path=self.global_config.expanded_appimage_download_backup_folder_path,
            config_folder=self.app_config.config_folder,
            config_file_name=self.app_config.config_file_name,
            batch_mode=self.global_config.batch_mode,
            keep_backup=self.global_config.keep_backup,
        )
        file_handler.handle_appimage_operations()
