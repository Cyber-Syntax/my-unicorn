import os
import json
import logging


class AppConfigManager:
    """Manages app-specific configuration settings."""

    def __init__(
        self,
        owner: str = None,
        repo: str = None,
        version: str = None,
        sha_name: str = None,
        hash_type: str = "sha256",
        appimage_name: str = None,
        config_folder: str = "~/Documents/appimages/config_files/",
    ):
        self.owner = owner
        self.repo = repo
        self.version = version
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.appimage_name = appimage_name
        self.config_folder = os.path.expanduser(config_folder)
        self.config_file_name = f"{self.repo}.json"
        self.config_file = (
            os.path.join(self.config_folder, self.config_file_name)
            if self.config_file_name
            else None
        )

        # Ensure the configuration directory exists
        os.makedirs(self.config_folder, exist_ok=True)

    def load_appimage_config(self, config_file_name: str):
        """Load a specific AppImage configuration file."""
        config_file_path = os.path.join(self.config_folder, config_file_name)
        if os.path.isfile(config_file_path):  # Check if the file exists
            try:
                with open(config_file_path, "r", encoding="utf-8") as file:
                    config = json.load(file)
                    # Update instance variables with the loaded config
                    self.owner = config.get("owner", self.owner)
                    self.repo = config.get("repo", self.repo)
                    self.version = config.get("version", self.version)
                    self.sha_name = config.get("sha_name", self.sha_name)
                    self.hash_type = config.get("hash_type", self.hash_type)
                    self.appimage_name = config.get("appimage_name", self.appimage_name)
                    return config
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in the configuration file: {e}")
                raise ValueError("Failed to parse JSON from the configuration file.")
        else:
            logging.warning(f"Configuration file {config_file_name} not found.")
            return None

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

        #TODO: Debug is WIP:
        # joplin works, siyuan works
        self.sha_name = input("Enter the SHA file name (Leave blank if you want auto detect): ").strip() or None
        self.hash_type = (
            input("Enter the hash type (default: 'sha256'): ").strip() or "sha256"
        )

        return self.sha_name, self.hash_type
