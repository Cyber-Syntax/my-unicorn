from commands.base import Command
import logging
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
        self.appimage_updater = AppImageUpdater()

    def execute(self):
        """Main update execution flow"""
        self.global_config.load_config()

        # 1. Find updatable apps
        updatable = self.version_checker.find_updatable_apps(self.app_config)
        if not updatable:
            logging.info("All AppImages are up to date!")
            return

        # 2. Get user confirmation
        if not self._confirm_updates(updatable):
            logging.info("Update cancelled by user")
            print("Update cancelled")
            return

        # 3. Perform updates
        self.appimage_updater.execute_batch(updatable, self.global_config)

    def _confirm_updates(self, updatable):
        """Handle user confirmation based on batch mode"""
        if self.global_config.batch_mode:
            logging.info("Batch mode: Auto-confirming updates")
            print("Batch mode: Auto-confirming updates")
            return True

        logging.info(f"Found {len(updatable)} apps to update")
        print("\nApps to update:")
        for idx, app in enumerate(updatable, 1):
            update_msg = f"{idx}. {app['name']} ({app['current']} → {app['latest']})"
            logging.info(update_msg)
            print(update_msg)

        return input("Proceed with updates? [y/N]: ").strip().lower() == "y"


class VersionChecker:
    """Encapsulates version checking logic"""

    def find_updatable_apps(self, app_config):
        """
        Find applications that can be updated.
        
        Args:
            app_config (AppConfig): The application configuration object.
            
        Returns:
            list: A list of updatable applications.
        """
        updatable_apps = []
        
        # Check if app_config is None or if select_files() returns None
        selected_files = app_config.select_files() if app_config else None
        if not selected_files:
            print("No configuration files selected or available.")
            return updatable_apps
        
        for config_file in selected_files:
            app_data = self._check_single(app_config, config_file)
            if app_data:
                updatable_apps.append(app_data)
        return updatable_apps

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
            logging.info(
                f"Update available for {app_config.repo}: {current_version} → {latest_version}"
            )
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
        logging.info(f"Beginning batch update of {len(updatable)} AppImages")
        for app_data in updatable:
            self._update_single(app_data, global_config)

    def _update_single(self, app_data, global_config):
        """
        Update single AppImage with improved error handling to ensure
        the update process continues to the next app on failure.

        Args:
            app_data (dict): Contains app information including config_file, name, etc.
            global_config (GlobalConfigManager): Global configuration settings
        """
        try:
            update_msg = f"\nUpdating {app_data['name']}..."
            logging.info(update_msg)
            print(update_msg)

            # 1. Load config
            app_config = AppConfigManager()
            global_config = GlobalConfigManager()
            app_config.load_appimage_config(app_data["config_file"])

            # 2. Fetch release data
            github_api = GitHubAPI(
                owner=app_config.owner,
                repo=app_config.repo,
                sha_name=app_config.sha_name,
                hash_type=app_config.hash_type,
                arch_keyword=app_config.arch_keyword,
            )

            try:
                # Get release data
                github_api.get_response()

                # 3. Download & verify
                DownloadManager(github_api).download()
                if not self._verify(app_config, github_api):
                    verification_failed_msg = (
                        f"Verification failed for {app_data['name']}. Skipping update."
                    )
                    logging.warning(verification_failed_msg)
                    print(verification_failed_msg)
                    return
            except Exception as e:
                error_msg = f"Error fetching or downloading for {app_data['name']}: {str(e)}"
                logging.error(error_msg)
                print(f"Error updating {app_data['name']}: {str(e)}. Skipping to next app.")
                return

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
            # Install icon for the appimage
            icon_success, icon_msg = file_handler.download_app_icon(
                github_api.owner, github_api.repo
            )
            if icon_success:
                print(f"Icon installed: {icon_msg}")
            else:
                print(f"No icon installed: {icon_msg}")

            success = file_handler.handle_appimage_operations()
            if success:
                try:
                    app_config.update_version(
                        new_version=github_api.version,
                        new_appimage_name=github_api.appimage_name,
                    )
                    success_msg = (
                        f"Successfully updated {app_data['name']} to version {github_api.version}"
                    )
                    logging.info(success_msg)
                    print(success_msg)
                except Exception as e:
                    error_msg = f"Failed to update version in config file: {str(e)}"
                    logging.error(error_msg)
                    print(error_msg)
            else:
                error_msg = f"Failed to update AppImage for {app_data['name']}"
                logging.error(error_msg)
                print(error_msg)

        except Exception as e:
            # Catch any unexpected exceptions to ensure we continue to the next app
            error_msg = f"Unexpected error updating {app_data['name']}: {str(e)}"
            logging.error(error_msg)
            print(
                f"Unexpected error updating {app_data['name']}: {str(e)}. Continuing to next app."
            )

        finished_msg = f"Finished processing {app_data['name']}"
        logging.info(finished_msg)
        print(finished_msg)  # Always print this regardless of success/failure

    def _verify(self, app_config, github_api):
        """
        Handle verification process for downloaded AppImage.

        Args:
            app_config (AppConfigManager): App configuration
            github_api (GitHubAPI): GitHub API handler with release info

        Returns:
            bool: True if verification passed or skipped, False if failed
        """
        if github_api.sha_name == "no_sha_file":
            logging.info("Skipping verification for beta version")
            print("Skipping verification for beta version")
            return True

        return VerificationManager(
            sha_name=app_config.sha_name,
            sha_url=github_api.sha_url,
            appimage_name=github_api.appimage_name,
            hash_type=app_config.hash_type,
        ).verify_appimage()
