from commands.base import Command
from src.download import DownloadManager
from src.parser import ParseURL
from src.api import GitHubAPI
from src.app_config import AppConfigManager
from src.verify import VerificationManager
from src.file_handler import FileHandler
from src.global_config import GlobalConfigManager


class DownloadCommand(Command):
    """Command to download the latest release's AppImage."""

    def execute(self):
        # 1. Initialize the URL parser
        parser = ParseURL()
        parser.ask_url()  # Get owner and repo by asking the user for the URL
        #
        # 2. Get the owner and repo from ParseURL instance
        owner, repo = parser.owner, parser.repo

        # Get hash_type and sha_name from user
        # TODO: able to learn without user input.
        app_config = AppConfigManager(owner=owner, repo=repo)
        sha_name, hash_type = (
            app_config.ask_sha_hash()
        )  # Returns sha_name and hash_type

        # 3. Initialize the GitHubAPI with the parsed owner and repo
        api = GitHubAPI(owner=owner, repo=repo, sha_name=sha_name, hash_type=hash_type)
        api.get_response()  # Fetch release data from GitHub API

        # 4. Update the AppConfigManager with the fetched attributes
        # app_config.owner = parser.owner
        # app_config.repo = parser.repo
        app_config.version = api.version  # Assume version is fetched in GitHubAPI
        app_config.appimage_name = api.appimage_name
        app_config.sha_name = api.sha_name
        app_config.hash_type = api.hash_type

        # 4. Use DownloadManager to download the AppImage
        download = DownloadManager(api)
        download.download()  # Pass the appimage URL to download method

        # Pass data to VerificationManager
        verification_manager = VerificationManager(
            sha_name=api.sha_name,
            sha_url=api.sha_url,
            appimage_name=api.appimage_name,
            hash_type=api.hash_type,
        )

        global_config = GlobalConfigManager()
        global_config.load_config()
        # Perform verification
        if verification_manager.verify_appimage():
            # if verification correct save current attiributes to app config file
            app_config.save_config()
            # if verification correct, make executable, change name, move appimage to user choosed dir
            file_handler = FileHandler(
                appimage_name=api.appimage_name,
                repo=api.repo,
                version=api.version,
                config_file=global_config.config_file,
                appimage_download_folder_path=global_config.expanded_appimage_download_folder_path,
                appimage_download_backup_folder_path=global_config.expanded_appimage_download_backup_folder_path,
                config_folder=app_config.config_folder,
                config_file_name=app_config.config_file_name,
            )
            file_handler.handle_appimage_operations()
