from commands.base import Command
from src.api import GitHubAPI
from src.app_config import AppConfigManager
from src.download import DownloadManager
from src.file_handler import FileHandler
from src.global_config import GlobalConfigManager
from src.parser import ParseURL
from src.verify import VerificationManager


class DownloadCommand(Command):
    """Command to download the latest release's AppImage.

    This class is responsible for downloading the latest release's AppImage
    from a specified GitHub repository. It extends the Command class and
    implements the execute method to define the specific behavior of
    downloading the AppImage.
    """

    def execute(self):
        """Execute the command to download the latest release's AppImage.

        This method initializes the URL parser, gets the owner and repo from
        the user, initializes the GitHubAPI, fetches release data, and
        downloads the AppImage. It also handles verification and file
        operations.
        """
        # 1. Initialize the URL parser
        parser = ParseURL()
        parser.ask_url()  # Get owner and repo by asking the user for the URL
        #
        # 2. Get the owner and repo from ParseURL instance
        owner, repo = parser.owner, parser.repo

        # Get hash_type and sha_name from user
        # TODO: able to learn without user input.
        app_config = AppConfigManager(owner=owner, repo=repo)
        sha_name, hash_type = app_config.ask_sha_hash()  # Returns sha_name and hash_type

        # 3. Initialize the GitHubAPI with the parsed owner and repo
        api = GitHubAPI(
            owner=owner,
            repo=repo,
            sha_name=sha_name,
            hash_type=hash_type,
            arch_keyword=None,
        )
        api.get_response()  # Fetch release data from GitHub API

        # Add these lines to sync ALL fields
        app_config.owner = api.owner  # Explicitly set owner/repo
        app_config.repo = api.repo  # (even if from parser)
        app_config.version = api.version
        app_config.appimage_name = api.appimage_name
        app_config.arch_keyword = api.arch_keyword
        app_config.sha_name = api.sha_name
        app_config.hash_type = api.hash_type

        # Save temporary configuration
        app_config.temp_save_config()

        # 4. Use DownloadManager to download the AppImage
        download = DownloadManager(api)
        download.download()  # Pass the appimage URL to download method

        global_config = GlobalConfigManager()
        global_config.load_config()

        # TODO: Those need to implement the update_all class too
        # Modify verification check to handle "no_sha_file" and None cases
        if api.sha_name != "no_sha_file":
            # HACK: workaround when user skip verification for non-beta apps.
            verification_manager = VerificationManager(
                sha_name=api.sha_name,
                sha_url=api.sha_url,
                appimage_name=api.appimage_name,
                hash_type=api.hash_type,
            )
            is_valid = verification_manager.verify_appimage()
            if not is_valid:
                return
        else:
            print("Skipping verification for beta version")

        # Handle file operations
        file_handler = FileHandler(
            appimage_name=api.appimage_name,
            repo=api.repo,
            version=api.version,
            sha_name=api.sha_name,
            config_file=global_config.config_file,
            appimage_download_folder_path=global_config.expanded_appimage_download_folder_path,
            appimage_download_backup_folder_path=global_config.expanded_appimage_download_backup_folder_path,
            config_folder=app_config.config_folder,
            config_file_name=app_config.config_file_name,
            batch_mode=global_config.batch_mode,
            keep_backup=global_config.keep_backup,
        )

        # Check if the file operations were successful
        success = file_handler.handle_appimage_operations()
        if success:
            # Save the configuration only if all previous steps succeed
            app_config.save_config()
            print("Configuration saved successfully.")
        else:
            print("An error occurred during file operations.")
