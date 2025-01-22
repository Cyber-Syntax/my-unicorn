from commands.base import Command
from src.download import DownloadManager
from src.parser import ParseURL
from src.api import GitHubAPI
from src.app_config import AppConfigManager


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
        app_config = AppConfigManager()
        sha_name, hash_type = (
            app_config.ask_sha_hash()
        )  # Returns sha_name and hash_type
        # app_config.ask_sha_hash()
        # sha_name, hash_type = app_config.sha_name, app_config.hash_type
        print(sha_name, hash_type)

        # 3. Initialize the GitHubAPI with the parsed owner and repo
        api = GitHubAPI(owner=owner, repo=repo, sha_name=sha_name, hash_type=hash_type)
        api.get_response()  # Fetch release data from GitHub API

        # 4. Use DownloadManager to download the AppImage
        download = DownloadManager(api)
        download.download()  # Pass the appimage URL to download method
