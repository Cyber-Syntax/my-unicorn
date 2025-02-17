# commands/update_single_app.py
from commands.base import Command
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler


class UpdateSingleAppCommand(Command):
    """Command to update a single AppImage."""

    def __init__(self, app_config, global_config, appimage_data):
        self.app_config = app_config
        self.global_config = global_config
        self.appimage_data = appimage_data

    def execute(self):
        self.app_config.load_appimage_config(self.appimage_data["config_file"])

        # Initialize GitHubAPI
        github_api = GitHubAPI(
            owner=self.app_config.owner,
            repo=self.app_config.repo,
            sha_name=self.app_config.sha_name,
            hash_type=self.app_config.hash_type,
        )
        github_api.get_response()

        # Download
        print(f"Downloading {self.app_config.appimage_name}...")
        DownloadManager(github_api).download()

        # Verify
        verification_manager = VerificationManager(
            sha_name=github_api.sha_name,
            sha_url=github_api.sha_url,
            appimage_name=github_api.appimage_name,
            hash_type=github_api.hash_type,
        )
        if not verification_manager.verify_appimage():
            print(f"Verification failed for {self.app_config.appimage_name}.")
            return

        # File operations
        FileHandler(
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
        ).handle_appimage_operations()
