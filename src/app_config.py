import os
import json
import logging
from dataclasses import dataclass, field
from .parser import ParseURL
from .api import GitHubAPI


@dataclass
class AppConfigManager:
    """Manages app-specific configuration settings."""

    appimage_name: str = None
    config_folder: str = field(default="~/Documents/appimages/config_files/")
    #FIX: repo came None or became None in this class
    owner: str = field(default=None)
    repo: str = field(default=None)
    version: str = None
    sha_name: str = None
    hash_type: str = field(default="sha256")
    config_file_name: str = field(default=None)

    def __post_init__(self):
        self.repo = self.repo
        self.config_folder = os.path.expanduser(self.config_folder)
        os.makedirs(self.config_folder, exist_ok=True)
        # Use the default name if no specific config file name is provided
        self.config_file_name = f"{self.repo}.json"
        self.config_file = os.path.join(self.config_folder, self.config_file_name)

    def load_config(self):
        """Load app-specific configuration from a JSON file."""
        if os.path.isfile(self.config_file):  # Check if the file exists
            try:
                with open(self.config_file, "r", encoding="utf-8") as file:
                    config = json.load(file)
                    # Load values, falling back to current defaults if keys are missing
                    self.owner = config.get("owner", self.owner)
                    self.repo = config.get("repo", self.repo)
                    self.version = config.get("version", self.version)
                    self.sha_name = config.get("sha_name", self.sha_name)
                    self.hash_type = config.get("hash_type", self.hash_type)
                    self.appimage_name = config.get("appimage_name", self.appimage_name)
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in the configuration file: {e}")
                raise ValueError("Failed to parse JSON from the configuration file.")
        else:
            logging.info(f"Configuration file {config_file} not found. Starting fresh.")

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as file:
            config_data = self.to_dict()
            logging.info(f"Saving configuration: {config_data}")
            json.dump(config_data, file, indent=4)

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
    # def from_github_api(sha_name=None, hash_type="sha256"):
    #     """Create an instance using data fetched from GitHub API."""
    #     github = GitHubAPI()
    #     github.get_response()
    #
    #     return AppConfigManager(
    #         appimage_name=github.appimage_name,
    #         # owner=owner,
    #         # repo=repo,
    #         version=github.version,
    #         sha_name=sha_name or github.sha_name,
    #         hash_type=hash_type,
    #     )

    def list_json_files(self):
        """List JSON files in the configuration directory."""
        try:
            json_files = [
                file
                for file in os.listdir(self.config_folder)
                if file.endswith(".json")
            ]
            return json_files if json_files else []
        except FileNotFoundError as error:
            logging.error(f"Error accessing configuration folder: {error}")
            raise FileNotFoundError("Configuration folder does not exist.")

    def ask_sha_hash(self):
        """Set up app-specific configuration interactively."""
        print("Setting up app-specific configuration...")

        # TODO: if detected, don't ask? Need to change command sorting
        # We need to use api to detect first before asking those
        self.sha_name = input("Enter the SHA file name : ").strip()
        self.hash_type = (
            input("Enter the hash type (default: 'sha256'): ").strip() or "sha256"
        )
        # # Update the current instance with values from GitHub API
        # app_config = AppConfigManager.from_github_api(
        #     sha_name=sha_name, hash_type=hash_type
        # )

        return self.sha_name, self.hash_type
