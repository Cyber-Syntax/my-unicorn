import os
import json
from dataclasses import dataclass, field
from .parser import ParseURL
from .api import GitHubAPI


@dataclass
class AppConfigManager:
    """Manages app-specific configuration settings."""

    appimage_name: str = None
    config_folder: str = field(default="~/Documents/appimages/config_files/")
    owner: str = None
    repo: str = None
    version: str = None
    sha_name: str = None
    hash_type: str = field(default="sha256")
    config_file_name: str = field(default=None)

    def __post_init__(self):
        self.config_folder = os.path.expanduser(self.config_folder)
        os.makedirs(self.config_folder, exist_ok=True)
        # Use the default name if no specific config file name is provided
        self.config_file_name = f"{self.repo}.json"

    def get_config_file_path(self):
        """Get the full path for an app-specific configuration file."""
        return os.path.join(self.config_folder, self.config_file_name)

    def load_config(self):
        """Load app-specific configuration from a JSON file."""
        config_file = self.get_config_file_path()
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as file:
                config = json.load(file)
                self.owner = config.get("owner", self.owner)
                self.repo = config.get("repo", self.repo)
                self.version = config.get("version", self.version)
                self.sha_name = config.get("sha_name", self.sha_name)
                self.hash_type = config.get("hash_type", self.hash_type)
                self.appimage_name = config.get("appimage_name", self.appimage_name)

    def save_config(self):
        """Save app-specific configuration to a JSON file."""
        config_file = self.get_config_file_path()
        with open(config_file, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)

    def to_dict(self):
        """Convert the dataclass to a dictionary."""
        return {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "sha_name": self.sha_name,
            "hash_type": self.hash_type,
            "appimage_name": self.appimage_name,
        }

    @staticmethod
    def from_github_api(owner, repo, sha_name=None, hash_type="sha256"):
        """Create an instance using data fetched from GitHub API."""

        github = GitHubAPI(owner, repo)
        github.get_response()

        return AppConfigManager(
            appimage_name=github.appimage_name,
            owner=owner,
            repo=repo,
            version=github.version,
            sha_name=sha_name or github.sha_name,
            hash_type=hash_type,
        )

    def list_json_files(self):
        """List JSON files in the configuration directory."""
        try:
            json_files = [
                file
                for file in os.listdir(self.config_folder)
                if file.endswith(".json")
            ]
            if json_files:
                return json_files
            else:
                print(_("No JSON files found."))
                return []
        except FileNotFoundError as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(_("Error: {error}. Exiting...").format(error=error))
            sys.exit(1)

    @staticmethod
    def create_app_config():
        print("Setting up app-specific configuration...")

        # Parse the GitHub URL using ParseURL

        parser = ParseURL()
        parser.ask_url()

        sha_name = (
            input("Enter the SHA file name (leave blank to auto-detect): ").strip()
            or None
        )
        hash_type = (
            input("Enter the hash type (default: 'sha256'): ").strip() or "sha256"
        )

        # Create config using GitHubAPI
        config = AppConfigManager.from_github_api(
            owner=parser.owner, repo=parser.repo, sha_name=sha_name, hash_type=hash_type
        )

        config.save_config()
        print(f"Configuration for {config.appimage_name} saved successfully!")
        return config
