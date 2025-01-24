from commands.base import Command
from src.app_config import AppConfigManager
from src.api import GitHubAPI
from src.verify import VerificationManager
from src.global_config import GlobalConfigManager
from src.file_handler import FileHandler
from src.update import AppImageUpdater
from src.download import DownloadManager


class UpdateCommand(Command):
    """Command to update AppImages based on existing configuration files."""

    def execute(self):
        # Load global configuration
        global_config = GlobalConfigManager()
        global_config.load_config()

        # Initialize AppConfigManager
        app_config = AppConfigManager()

        # Step 1: List and select configuration files
        update_manager = AppImageUpdater(app_config, global_config)
        selected_files = update_manager.select_files()
        if not selected_files:
            return  # Exit if no files are selected or available

        # Step 2: Check versions for selected files
        appimages_to_update = update_manager.check_versions(selected_files)

        if not appimages_to_update:
            print("All selected AppImages are up to date.")
            return

        # Step 3: Update selected AppImages
        update_manager.update_selected_appimages(appimages_to_update)

        # # Initialize GitHubAPI
        # github_api = GitHubAPI(
        #     owner=app_config.owner,
        #     repo=app_config.repo,
        #     sha_name=app_config.sha_name,
        #     hash_type=app_config.hash_type,
        # )
        # github_api.get_response()
        #
        # update_manager.check_version(
        #     latest_version=github_api.version, current_version=app_config.version
        # )
        #
        # # Download the new AppImage
        # print(f"Downloading {app_config.appimage_name}...")
        # download_manager = DownloadManager(github_api)
        # download_manager.download()  # Pass the appimage URL to download method
        #
        # verification_manager = VerificationManager(
        #     sha_name=github_api.sha_name,
        #     sha_url=github_api.sha_url,
        #     appimage_name=github_api.appimage_name,
        #     hash_type=github_api.hash_type,
        # )
        #
        # # Perform verification
        # if verification_manager.verify_appimage():
        #     # if verification correct, make executable, change name, move appimage to user choosed dir
        #     file_handler = FileHandler(
        #         appimage_name=github_api.appimage_name,
        #         repo=github_api.repo,
        #         version=github_api.version,
        #         config_file=global_config.config_file,
        #         appimage_download_folder_path=global_config.expanded_appimage_download_folder_path,
        #         appimage_download_backup_folder_path=global_config.expanded_appimage_download_backup_folder_path,
        #         config_folder=app_config.config_folder,
        #         config_file_name=app_config.config_file_name,
        #     )
        #     file_handler.handle_appimage_operations()
        # print(f"{app_config.appimage_name} updated successfully.")
