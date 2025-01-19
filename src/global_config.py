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

    def __post_init__(self):
        self.config_file = os.path.expanduser(self.config_file)
        self.load_config()

    def load_config(self):
        """Load global settings from a JSON file."""
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as file:
                config = json.load(file)
                self.appimage_download_folder_path = config.get(
                    "appimage_download_folder_path", self.appimage_download_folder_path
                )
                self.appimage_download_backup_folder_path = config.get(
                    "appimage_download_backup_folder_path",
                    self.appimage_download_backup_folder_path,
                )
                self.keep_backup = config.get("keep_backup", self.keep_backup)
                self.batch_mode = config.get("batch_mode", self.batch_mode)

    def save_config(self):
        """Save global settings to a JSON file."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4)

    def to_dict(self):
        """Convert the dataclass to a dictionary."""
        return {
            "appimage_download_folder_path": self.appimage_download_folder_path,
            "appimage_download_backup_folder_path": self.appimage_download_backup_folder_path,
            "keep_backup": self.keep_backup,
            "batch_mode": self.batch_mode,
        }


class GlobalConfigSetup:
    """Handles one-time setup for global configuration."""

    @staticmethod
    def create_global_config():
        print("Setting up global configuration...")
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

        config = GlobalConfigManager(
            appimage_download_folder_path=appimage_download_folder_path,
            keep_backup=(keep_backup == "yes"),
            batch_mode=(batch_mode == "yes"),
        )
        config.save_config()
        print("Global configuration saved successfully!")
        return config
