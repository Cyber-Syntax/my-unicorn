import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GlobalConfigManager:
    """Manages global configuration settings."""

    config_file: str = field(default="~/.config/myunicorn/settings.json")
    app_storage_path: str = field(default_factory=lambda: "~/.local/share/myunicorn")
    app_backup_storage_path: str = field(
        default_factory=lambda: "~/.local/share/myunicorn/backups"
    )
    app_download_path: str = field(default_factory=lambda: "~/Downloads")
    keep_backup: bool = field(default=True)
    max_backups: int = field(default=3)  # Number of backups to keep per app
    batch_mode: bool = field(default=False)
    locale: str = field(default="en")
    max_concurrent_updates: int = field(
        default=3
    )  # Default value for maximum concurrent updates

    def __post_init__(self):
        # Ensure the XDG config directory exists
        os.makedirs(self.expanded_app_storage_path, exist_ok=True)
        os.makedirs(self.expanded_app_backup_storage_path, exist_ok=True)
        os.makedirs(self.expanded_app_download_path, exist_ok=True)
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

        # Expand only the config file path during initialization
        self.config_file = os.path.expanduser(self.config_file)

        self.load_config()

    def load_config(self):
        """Load global settings from a JSON file or initialize defaults."""
        if os.path.isfile(self.config_file):  # Check if file exists
            try:
                with open(self.config_file, encoding="utf-8") as file:
                    config = json.load(file)

                    # Get all expected config keys from to_dict method
                    expected_keys = set(self.to_dict().keys())
                    found_keys = set(config.keys())

                    # Load each configuration item safely
                    self.app_storage_path = config.get(
                        "app_storage_path",
                        self.app_storage_path,
                    )
                    self.app_backup_storage_path = config.get(
                        "app_backup_storage_path",
                        self.app_backup_storage_path,
                    )
                    self.app_download_path = config.get(
                        "app_download_path",
                        self.app_download_path,
                    )
                    self.keep_backup = config.get("keep_backup", self.keep_backup)
                    self.max_backups = config.get("max_backups", self.max_backups)
                    self.batch_mode = config.get("batch_mode", self.batch_mode)
                    self.locale = config.get("locale", self.locale)
                    self.max_concurrent_updates = config.get(
                        "max_concurrent_updates", self.max_concurrent_updates
                    )

                    # If any expected keys are missing, log it
                    missing_keys = expected_keys - found_keys
                    if missing_keys:
                        logger.info("Config file is missing keys: %s", missing_keys)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse the configuration file: %s", e)
                raise ValueError("Invalid JSON format in the configuration file.")
        else:
            logger.info(
                "Configuration file not found at %s. Creating one...", self.config_file
            )
            self.create_global_config()
            return False

        return True

    def to_dict(self):
        """Convert the dataclass to a dictionary."""
        return {
            "app_storage_path": self.app_storage_path,
            "app_backup_storage_path": self.app_backup_storage_path,
            "app_download_path": self.app_download_path,
            "keep_backup": self.keep_backup,
            "max_backups": self.max_backups,
            "batch_mode": self.batch_mode,
            "locale": self.locale,
            "max_concurrent_updates": self.max_concurrent_updates,
        }

    def create_global_config(self):
        """Sets up global configuration interactively."""
        print("Setting up global configuration...")

        try:
            # Use default values if input is blank
            app_storage_path = (
                input(
                    "Enter the folder path to save appimages (default: '~/.local/share/myunicorn'): "
                ).strip()
                or "~/.local/share/myunicorn"
            )
            app_download_path = (
                input(
                    "Enter the folder path to download appimages (default: '~/Downloads'): "
                ).strip()
                or "~/Downloads"
            )
            keep_backup = (
                input("Enable backup for old appimages? (yes/no, default: yes): ")
                .strip()
                .lower()
                or "yes"
            )
            max_backups = (
                input("Max number of backups to keep per app (default: 3): ").strip() or "3"
            )
            batch_mode = (
                input("Enable batch mode? (yes/no, default: no): ").strip().lower() or "no"
            )
            locale = input("Select your locale (en/tr, default: en): ").strip() or "en"
            max_concurrent_updates = (
                input("Max number of concurrent updates (default: 3): ").strip() or "3"
            )

            # Update current instance values
            self.app_storage_path = app_storage_path
            self.app_backup_storage_path = "~/.local/share/myunicorn/backups"
            self.app_download_path = app_download_path
            self.keep_backup = keep_backup == "yes"
            self.max_backups = int(max_backups)
            self.batch_mode = batch_mode == "yes"
            self.locale = locale
            self.max_concurrent_updates = int(max_concurrent_updates)

            # Save the configuration
            self.save_config()
            print("Global configuration saved successfully!")
        except KeyboardInterrupt:
            logger.info("Global configuration setup interrupted by user")
            print("\nConfiguration setup interrupted. Using default values.")

            # set default values
            self.app_storage_path = "~/.local/share/myunicorn"
            self.app_backup_storage_path = "~/.local/share/myunicorn/backups"
            self.app_download_path = "~/Downloads"
            self.keep_backup = True
            self.max_backups = 3
            self.batch_mode = False
            self.locale = "en"
            self.max_concurrent_updates = 3

            # Save the default configuration
            self.save_config()
            print("Default global configuration saved.")

    def save_config(self):
        """Save global settings to a JSON file."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)
        logger.info("Global configuration saved to %s", self.config_file)

    # Properties to access expanded paths on demand
    @property
    def expanded_app_storage_path(self):
        return os.path.expanduser(self.app_storage_path)

    @property
    def expanded_app_backup_storage_path(self):
        return os.path.expanduser(self.app_backup_storage_path)

    @property
    def expanded_app_download_path(self):
        return os.path.expanduser(self.app_download_path)

    def customize_global_config(self):
        """Customize the configuration settings for the Global Config."""
        self.load_config()

        print("Select which key to modify:")
        print("=================================================")
        print(f"1. AppImage Download Folder: {self.app_storage_path}")
        print(f"2. AppImage Download Path: {self.app_download_path}")
        print(f"3. Enable Backup: {'Yes' if self.keep_backup else 'No'}")
        print(f"4. Max Backups Per App: {self.max_backups}")
        print(f"5. Batch Mode: {'Yes' if self.batch_mode else 'No'}")
        print(f"6. Locale: {self.locale}")
        print(f"7. Max Concurrent Updates: {self.max_concurrent_updates}")
        print("8. Exit")
        print("=================================================")

        try:
            while True:
                choice = input("Enter your choice: ")
                if choice.isdigit() and 1 <= int(choice) <= 8:
                    break
                else:
                    print("Invalid choice, please enter a number between 1 and 8.")

            if choice == "8":
                print("Exiting without changes.")
                return

            config_dict = {
                "app_storage_path": self.app_storage_path,
                "app_download_path": self.app_download_path,
                "keep_backup": self.keep_backup,
                "max_backups": self.max_backups,
                "batch_mode": self.batch_mode,
                "locale": self.locale,
                "max_concurrent_updates": self.max_concurrent_updates,
            }
            key = list(config_dict.keys())[int(choice) - 1]

            try:
                if key == "app_storage_path":
                    new_value = (
                        input("Enter the new folder path to save appimages: ").strip()
                        or "~/.local/share/myunicorn"
                    )
                elif key == "app_download_path":
                    new_value = (
                        input("Enter the new folder path to download appimages: ").strip()
                        or "~/Downloads"
                    )
                elif key == "keep_backup":
                    new_value = (
                        input("Enable backup for old appimages? (yes/no): ").strip().lower()
                        or "no"
                    )
                    new_value = new_value == "yes"
                elif key == "max_backups":
                    new_value_str = (
                        input("Enter max number of backups to keep per app: ").strip() or "3"
                    )
                    try:
                        new_value = int(new_value_str)
                        if new_value < 1:
                            print("Value must be at least 1. Setting to 1.")
                            new_value = 1
                    except ValueError:
                        print("Invalid number. Setting to default (3).")
                        new_value = 3
                elif key == "batch_mode":
                    new_value = input("Enable batch mode? (yes/no): ").strip().lower() or "no"
                    new_value = new_value == "yes"
                elif key == "locale":
                    new_value = (
                        input("Select your locale (en/tr, default: en): ").strip() or "en"
                    )
                elif key == "max_concurrent_updates":
                    new_value_str = (
                        input("Enter max number of concurrent updates: ").strip() or "3"
                    )
                    try:
                        new_value = int(new_value_str)
                        if new_value < 1:
                            print("Value must be at least 1. Setting to 1.")
                            new_value = 1
                    except ValueError:
                        print("Invalid number. Setting to default (3).")
                        new_value = 3

                setattr(self, key, new_value)
                self.save_config()
                print(
                    f"\033[42m{key.capitalize()} updated successfully in settings.json\033[0m"
                )
                print("=================================================")
            except KeyboardInterrupt:
                logger.info("User interrupted configuration update")
                print("\nConfiguration update cancelled. No changes were made.")
                return
        except KeyboardInterrupt:
            logger.info("User interrupted configuration customization")
            print("\nConfiguration customization cancelled. No changes were made.")
            return
