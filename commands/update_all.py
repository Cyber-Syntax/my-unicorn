# commands/update.py
from commands.base import Command
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler


class UpdateCommand(Command):
    """Orchestrates AppImage update process using command pattern components"""

    def __init__(self):
        self.global_config = GlobalConfigManager()
        self.app_config = AppConfigManager()
        self.version_checker = VersionChecker()
        self.updater = AppImageUpdater()

    def execute(self):
        """Main update execution flow"""
        self.global_config.load_config()

        # 1. Find updatable apps
        updatable = self.version_checker.find_updatable_apps(self.app_config)
        if not updatable:
            print("All AppImages are up to date!")
            return

        # 2. Get user confirmation
        if not self._confirm_updates(updatable):
            print("Update cancelled")
            return

        # 3. Perform updates
        self.updater.execute_batch(updatable, self.global_config)

    def _confirm_updates(self, updatable):
        """Handle user confirmation based on batch mode"""
        if self.global_config.batch_mode:
            print("Batch mode: Auto-confirming updates")
            return True

        print("\nApps to update:")
        for idx, app in enumerate(updatable, 1):
            print(f"{idx}. {app['name']} ({app['current']} → {app['latest']})")

        return input("Proceed with updates? [y/N]: ").strip().lower() == "y"


class VersionChecker:
    """Encapsulates version checking logic"""

    def find_updatable_apps(self, app_config):
        """Return list of apps needing updates"""
        updatable = []
        for config_file in app_config.select_files():
            app_data = self._check_single(app_config, config_file)
            if app_data:
                updatable.append(app_data)
        return updatable

    def _check_single(self, app_config, config_file):
        """Check version for single AppImage"""
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
            return {
                "config_file": config_file,
                "name": app_config.appimage_name,
                "current": current_version,
                "latest": latest_version,
            }
        return None


class AppImageUpdater:
    """Handles actual update operations"""

    def execute_batch(self, updatable, global_config):
        """Update multiple AppImages with queue logic"""
        for app_data in updatable:
            if not global_config.batch_mode:
                # Confirm each update individually
                print(
                    f"\nReady to update {app_data['name']} ({app_data['current']} → {app_data['latest']})"
                )
                confirm = input("Proceed with this update? [y/N]: ").strip().lower()
                if confirm != "y":
                    print(f"Skipping {app_data['name']}")
                    continue  # Skip this update and move to the next

            self._update_single(app_data, global_config)

    def _update_single(self, app_data, global_config):
        """Update single AppImage"""
        print(f"\nUpdating {app_data['name']}...")

        # 1. Load config
        app_config = AppConfigManager()
        app_config.load_appimage_config(app_data["config_file"])

        # 2. Fetch release data
        github_api = GitHubAPI(
            owner=app_config.owner,
            repo=app_config.repo,
            sha_name=app_config.sha_name,
            hash_type=app_config.hash_type,
            arch_keyword=app_config.arch_keyword,
        )

        github_api.get_response()

        # 3. Download & verify
        DownloadManager(github_api).download()
        if not self._verify(app_config, github_api):
            return

        global_config = GlobalConfigManager()

        # 4. Handle file operations
        file_handler = FileHandler(
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
        )
        file_handler.handle_appimage_operations()

    def _verify(self, app_config, github_api):
        """Handle verification process"""
        if github_api.sha_name == "no_sha_file":
            print("Skipping verification for beta version")
            return True

        return VerificationManager(
            sha_name=app_config.sha_name,
            sha_url=github_api.sha_url,
            appimage_name=github_api.appimage_name,
            hash_type=app_config.hash_type,
        ).verify_appimage()
