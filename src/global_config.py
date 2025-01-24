import os
import json
import logging
from dataclasses import dataclass, field


@dataclass
class GlobalConfigManager:
    """Manages global configuration settings."""

    config_file: str = field(
        default="~/Documents/appimages/config_files/other_settings/settings.json"
    )
    appimage_download_folder_path: str = field(
        default_factory=lambda: "~/Documents/appimages"
    )
    appimage_download_backup_folder_path: str = field(
        default_factory=lambda: "~/Documents/appimages/backups"
    )
    keep_backup: bool = field(default=True)
    batch_mode: bool = field(default=False)
    locale: str = field(default="en")

    def __post_init__(self):
        # Expand only the config file path during initialization
        self.config_file = os.path.expanduser(self.config_file)
        self.load_config()

    def expanded_path(self, path):
        """Expand and return a user path."""
        return os.path.expanduser(path)

    def load_config(self):
        """Load global settings from a JSON file or initialize defaults."""
        if os.path.isfile(self.config_file):  # Check if file exists
            try:
                with open(self.config_file, "r", encoding="utf-8") as file:
                    config = json.load(file)
                    # Safely load each configuration item
                    self.appimage_download_folder_path = config.get(
                        "appimage_download_folder_path",
                        self.appimage_download_folder_path,
                    )
                    self.appimage_download_backup_folder_path = config.get(
                        "appimage_download_backup_folder_path",
                        self.appimage_download_backup_folder_path,
                    )
                    self.keep_backup = config.get("keep_backup", self.keep_backup)
                    self.batch_mode = config.get("batch_mode", self.batch_mode)
                    self.locale = config.get("locale", self.locale)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse the configuration file: {e}")
                raise ValueError("Invalid JSON format in the configuration file.")
        else:
            logging.info(
                f"Configuration file not found at {self.config_file}. Creating one..."
            )
            self.create_global_config()
            return False

        return True

    def to_dict(self):
        """Convert the dataclass to a dictionary."""
        return {
            "appimage_download_folder_path": self.appimage_download_folder_path,
            "appimage_download_backup_folder_path": self.appimage_download_backup_folder_path,
            "keep_backup": self.keep_backup,
            "batch_mode": self.batch_mode,
            "locale": self.locale,
        }

    def create_global_config(self):
        """Sets up global configuration interactively."""
        print("Setting up global configuration...")

        # Use default values if input is blank
        appimage_download_folder_path = (
            input(
                "Enter the folder path to save appimages (default: '~/Documents/appimages'): "
            ).strip()
            or "~/Documents/appimages"
        )
        keep_backup = (
            input("Enable backup for old appimages? (yes/no, default: yes): ")
            .strip()
            .lower()
            or "yes"
        )
        batch_mode = (
            input("Enable batch mode? (yes/no, default: no): ").strip().lower() or "no"
        )
        locale = input("Select your locale (en/tr, default: en): ").strip() or "en"

        # Update current instance values
        self.appimage_download_folder_path = appimage_download_folder_path
        self.appimage_download_backup_folder_path = "~/Documents/appimages/backups"
        self.keep_backup = keep_backup == "yes"
        self.batch_mode = batch_mode == "yes"
        self.locale = locale

        # Save the configuration
        self.save_config()
        print("Global configuration saved successfully!")

    def save_config(self):
        """Save global settings to a JSON file."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)

    # Properties to access expanded paths on demand
    @property
    def expanded_appimage_download_folder_path(self):
        return os.path.expanduser(self.appimage_download_folder_path)

    @property
    def expanded_appimage_download_backup_folder_path(self):
        return os.path.expanduser(self.appimage_download_backup_folder_path)

