import json
import logging
import os
from dataclasses import dataclass, field


@dataclass
class GlobalConfigManager:
    """Manages global configuration settings."""

    config_file: str = field(default="~/.config/myunicorn/settings.json")
    appimage_download_folder_path: str = field(default_factory=lambda: "~/Documents/appimages")
    appimage_download_backup_folder_path: str = field(
        default_factory=lambda: "~/Documents/appimages/backups"
    )
    keep_backup: bool = field(default=True)
    batch_mode: bool = field(default=False)
    locale: str = field(default="en")

    def __post_init__(self):
        # Expand only the config file path during initialization
        self.config_file = os.path.expanduser(self.config_file)
        # Ensure the XDG config directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
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
                    self.github_token = config.get("github_token", self.github_token)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse the configuration file: {e}")
                raise ValueError("Invalid JSON format in the configuration file.")
        else:
            logging.info(f"Configuration file not found at {self.config_file}. Creating one...")
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
            "github_token": self.github_token,
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
            input("Enable backup for old appimages? (yes/no, default: yes): ").strip().lower()
            or "yes"
        )
        batch_mode = input("Enable batch mode? (yes/no, default: no): ").strip().lower() or "no"
        locale = input("Select your locale (en/tr, default: en): ").strip() or "en"
        github_token = (
            input("Enter your GitHub token (optional, press Enter to skip): ").strip() or ""
        )

        # Update current instance values
        self.appimage_download_folder_path = appimage_download_folder_path
        self.appimage_download_backup_folder_path = "~/Documents/appimages/backups"
        self.keep_backup = keep_backup == "yes"
        self.batch_mode = batch_mode == "yes"
        self.locale = locale
        self.github_token = github_token

        # Save the configuration
        self.save_config()
        print("Global configuration saved successfully!")

    def save_config(self):
        """Save global settings to a JSON file."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)
        logging.info(f"Global configuration saved to {self.config_file}")

    # Properties to access expanded paths on demand
    @property
    def expanded_appimage_download_folder_path(self):
        return os.path.expanduser(self.appimage_download_folder_path)

    @property
    def expanded_appimage_download_backup_folder_path(self):
        return os.path.expanduser(self.appimage_download_backup_folder_path)

    def customize_global_config(self):
        """Customize the configuration settings for the Global Config."""
        self.load_config()

        print("Select which key to modify:")
        print("=================================================")
        print(f"1. AppImage Download Folder: {self.appimage_download_folder_path}")
        print(f"2. Enable Backup: {'Yes' if self.keep_backup else 'No'}")
        print(f"3. Batch Mode: {'Yes' if self.batch_mode else 'No'}")
        print(f"4. Locale: {self.locale}")
        print("5. Exit")
        print("=================================================")

        while True:
            choice = input("Enter your choice: ")
            if choice.isdigit() and 1 <= int(choice) <= 6:
                break
            else:
                print("Invalid choice, please enter a number between 1 and 5.")

        if choice == "5":
            print("Exiting without changes.")
            return

        config_dict = {
            "appimage_download_folder_path": self.appimage_download_folder_path,
            "keep_backup": self.keep_backup,
            "batch_mode": self.batch_mode,
            "locale": self.locale,
        }
        key = list(config_dict.keys())[int(choice) - 1]

        if key == "appimage_download_folder_path":
            new_value = (
                input("Enter the new folder path to save appimages: ").strip()
                or "~/Documents/appimages"
            )
        elif key == "keep_backup":
            new_value = input("Enable backup for old appimages? (yes/no): ").strip().lower() or "no"
            new_value = new_value == "yes"
        elif key == "batch_mode":
            new_value = input("Enable batch mode? (yes/no): ").strip().lower() or "no"
            new_value = new_value == "yes"
        elif key == "locale":
            new_value = input("Select your locale (en/tr, default: en): ").strip() or "en"

        setattr(self, key, new_value)
        self.save_config()
        print(f"\033[42m{key.capitalize()} updated successfully in settings.json\033[0m")
        print("=================================================")
