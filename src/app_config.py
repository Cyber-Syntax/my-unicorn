@dataclass
class AppConfigManager:
    """Manages app-specific configuration settings."""

    appimage_name: str
    config_folder: str = field(default="~/Documents/appimages/config_files/")
    owner: str = None
    repo: str = None
    version: str = None
    sha_name: str = None
    hash_type: str = field(default="sha256")

    def __post_init__(self):
        self.config_folder = os.path.expanduser(self.config_folder)
        os.makedirs(self.config_folder, exist_ok=True)

    def get_config_file_path(self):
        """Get the full path for an app-specific configuration file."""
        return os.path.join(self.config_folder, f"{self.appimage_name}.json")

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
        }

    @staticmethod
    def from_url(
        url,
        appimage_name,
        version=None,
        sha_name="latest-linux.yml",
        hash_type="sha256",
    ):
        """Create an instance using a URL."""
        owner, repo = ParseURL.parse(url)  # Extract owner and repo
        return AppConfigManager(
            appimage_name=appimage_name,
            owner=owner,
            repo=repo,
            version=version,
            sha_name=sha_name,
            hash_type=hash_type,
        )


class AppConfigSetup:
    """Handles one-time setup for app-specific configuration."""

    @staticmethod
    def create_app_config():
        print("Setting up app-specific configuration...")
        # TODO: calling ParseURL or ?
        url = input("Enter the GitHub URL for the AppImage: ").strip()
        sha_name = (
            input("Enter the SHA file name (default: 'latest-linux.yml'): ").strip()
            or "latest-linux.yml"
        )
        hash_type = (
            input("Enter the hash type (default: 'sha256'): ").strip() or "sha256"
        )

        config = AppConfigManager.from_url(
            url=url,
            sha_name=sha_name,
            hash_type=hash_type,
        )
        config.save_config()
        print(f"Configuration for {appimage_name} saved successfully!")
        return config
