from commands.base import Command
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler

# TESTING: making this update class and follow command design pattern


class UpdateCommand(Command):
    """Command to update all outdated AppImages with batch mode support."""

    def __init__(self):
        self.app_config = AppConfigManager()
        self.global_config = GlobalConfigManager()

    def execute(self):
        global_config = GlobalConfigManager()
        global_config.load_config()
        app_config = AppConfigManager()

        # TODO: check version command

        # Auto-select all files in batch mode
        selected_files = app_config.select_files()
        if not selected_files:
            return None

        # Instead of returning immediately, store the result
        outdated_apps = self.check_versions(selected_files)

        # Now, proceed with the update logic
        if not outdated_apps:
            print("All AppImages are already up to date!")
            return

        # Handle confirmation based on batch mode
        if global_config.batch_mode:
            print("Batch mode: Automatically updating all outdated AppImages")
            self._perform_update(global_config, outdated_apps)
        else:
            self._show_confirmation_prompt(outdated_apps, global_config)

    def _show_confirmation_prompt(self, outdated_apps, global_config):
        """Show interactive confirmation prompt."""
        print("\nThe following AppImages will be updated:")
        for idx, app in enumerate(outdated_apps, 1):
            print(f"{idx}. {app['appimage_name']} (v{app['latest_version']})")

        confirm = (
            input("\nDo you want to proceed with updates? [y/N]: ").strip().lower()
        )
        if confirm == "y":
            self._perform_update(global_config, outdated_apps)
        else:
            print("Update cancelled.")

    def _perform_update(self, global_config, outdated_apps):
        """Execute the actual update process."""
        self.update_selected_appimages(outdated_apps)

    def _update_appimage(self, appimage_data):
        """Update a single AppImage."""
        # Initialize GitHubAPI
        github_api = GitHubAPI(
            owner=self.app_config.owner,
            repo=self.app_config.repo,
            sha_name=self.app_config.sha_name,
            hash_type=self.app_config.hash_type,
            arch_keyword=self.app_config.arch_keyword,
        )
        github_api.get_response()

        # Download the new AppImage
        print(f"Downloading {self.app_config.appimage_name}...")
        download_manager = DownloadManager(github_api)
        download_manager.download()

        # Verify the AppImage
        verification_manager = VerificationManager(
            sha_name=self.app_config.sha_name,
            sha_url=github_api.sha_url,
            appimage_name=github_api.appimage_name,
            hash_type=self.app_config.hash_type,
        )

        # Save temporary configuration
        self.app_config.temp_save_config()

        # Beta versions don't have a SHA file
        if github_api.sha_name != "no_sha_file":
            is_valid = verification_manager.verify_appimage()
            if not is_valid:
                return
        else:
            print("Skipping verification for beta version")

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

        file_handler.handle_appimage_operations()

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
                arch_keyword=self.app_config.arch_keyword,
            )
            latest_version = github_api.check_latest_version(
                self.app_config.owner, self.app_config.repo
            )

            if latest_version and latest_version != self.app_config.version:
                print("-------------------------------------------------")
                print(f"{self.app_config.appimage_name} is not up to date")
                print(f"\033[42mLatest version: {latest_version}\033[0m")
                print(f"Current version: {self.app_config.version}")
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
