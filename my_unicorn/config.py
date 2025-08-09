"""Configuration management for my-unicorn AppImage installer.

This module handles both global INI configuration and per-app JSON configurations.
It provides path resolution, validation, and default values as specified in the
architecture documentation.

The catalog system uses bundled catalog files (v2/catalog/*.json) rather than
copying them to the user's config directory, reducing disk usage and ensuring
the catalog is always up-to-date with the package.

Requirements:
    - orjson: High-performance JSON library (required for all JSON operations)
"""

import configparser
from pathlib import Path
from typing import TypedDict

import orjson


class NetworkConfig(TypedDict):
    """Network configuration options."""

    retry_attempts: int
    timeout_seconds: int


class DirectoryConfig(TypedDict):
    """Directory paths configuration."""

    repo: Path
    package: Path
    download: Path
    storage: Path
    backup: Path
    icon: Path
    settings: Path
    logs: Path
    cache: Path
    tmp: Path


class GlobalConfig(TypedDict):
    """Global application configuration."""

    config_version: str
    max_concurrent_downloads: int
    max_backup: int
    batch_mode: bool
    locale: str
    log_level: str
    network: NetworkConfig
    directory: DirectoryConfig


class AppImageConfig(TypedDict):
    """AppImage specific configuration."""

    version: str
    name: str
    rename: str
    name_template: str
    characteristic_suffix: list[str]
    installed_date: str
    digest: str


class GitHubConfig(TypedDict):
    """GitHub API configuration options."""

    repo: bool
    prerelease: bool


class VerificationConfig(TypedDict):
    """Verification configuration options."""

    digest: bool
    skip: bool
    checksum_file: str
    checksum_hash_type: str


class IconConfig(TypedDict):
    """Icon configuration."""

    url: str
    name: str
    installed: bool


class AppConfig(TypedDict):
    """Per-application configuration."""

    config_version: str
    appimage: AppImageConfig
    owner: str
    repo: str
    github: GitHubConfig
    verification: VerificationConfig
    icon: IconConfig


class CatalogEntry(TypedDict):
    """Catalog entry for an application."""

    owner: str
    repo: str
    appimage: dict[str, str | list[str]]
    verification: VerificationConfig
    icon: IconConfig | None


class ConfigManager:
    """Manages global and app-specific configurations."""

    DEFAULT_CONFIG_VERSION: str = "1.0.0"

    def __init__(self, config_dir: Path | None = None):
        """Initialize configuration manager.

        Args:
            config_dir: Optional custom config directory. Defaults to ~/.config/my-unicorn/

        """
        self.config_dir: Path = config_dir or Path.home() / ".config" / "my-unicorn"
        self.settings_file: Path = self.config_dir / "settings.conf"
        self.apps_dir: Path = self.config_dir / "apps"
        # Use bundled catalog directory instead of user config catalog
        self.catalog_dir: Path = Path(__file__).parent / "catalog"

        # Ensure directories exist
        self._ensure_directories()

        # Validate bundled catalog exists
        self._validate_catalog_directory()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        # Only create user config directories, catalog is bundled
        for directory in [self.config_dir, self.apps_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def _validate_catalog_directory(self) -> None:
        """Validate that the bundled catalog directory exists and contains apps."""
        if not self.catalog_dir.exists():
            raise FileNotFoundError(
                f"Bundled catalog directory not found: {self.catalog_dir}\n"
                "This indicates a packaging or installation issue."
            )

        if not self.catalog_dir.is_dir():
            raise NotADirectoryError(f"Catalog path is not a directory: {self.catalog_dir}")

        # Check if catalog has any JSON files
        catalog_files = list(self.catalog_dir.glob("*.json"))
        if not catalog_files:
            raise FileNotFoundError(
                f"No catalog entries found in: {self.catalog_dir}\n"
                "Expected to find *.json files with app catalog entries."
            )

    def _expand_path(self, path_str: str) -> Path:
        """Expand and resolve path with ~ and relative path support."""
        return Path(path_str).expanduser().resolve()

    def _get_default_global_config(self) -> dict[str, str | dict[str, str]]:
        """Get default global configuration values."""
        home = Path.home()
        return {
            "config_version": self.DEFAULT_CONFIG_VERSION,
            "max_concurrent_downloads": "5",
            "max_backup": "1",
            "batch_mode": "true",
            "locale": "en_US",
            "log_level": "INFO",
            "network": {"retry_attempts": "3", "timeout_seconds": "10"},
            "directory": {
                "repo": str(home / ".local" / "share" / "my-unicorn-repo"),
                "package": str(home / ".local" / "share" / "my-unicorn"),
                "download": str(home / "Downloads"),
                "storage": str(home / "Applications"),
                "backup": str(home / "Applications" / "backups"),
                "icon": str(home / "Applications" / "icons"),
                "settings": str(self.config_dir),
                "logs": str(self.config_dir / "logs"),
                "cache": str(self.config_dir / "cache"),
                "tmp": str(self.config_dir / "tmp"),
            },
        }

    def load_global_config(self) -> GlobalConfig:
        """Load global configuration from INI file."""
        config = configparser.ConfigParser()

        # Set defaults
        defaults = self._get_default_global_config()
        # Convert nested dicts to flat structure for configparser
        flat_defaults = {}
        for key, value in defaults.items():
            if isinstance(value, dict):
                # Skip nested dicts for configparser defaults
                continue
            flat_defaults[key] = str(value)
        config.read_dict({"DEFAULT": flat_defaults})

        # Add sections for nested configs
        for key, value in defaults.items():
            if isinstance(value, dict):
                config.add_section(key)
                for subkey, subvalue in value.items():
                    config.set(key, subkey, str(subvalue))

        # Read user config if it exists
        if self.settings_file.exists():
            config.read(self.settings_file)
        else:
            # Create default config file
            self.save_global_config(self._convert_to_global_config(defaults))

        return self._convert_to_global_config(config)

    def _convert_to_global_config(
        self, config: configparser.ConfigParser | dict[str, str | dict[str, str]]
    ) -> GlobalConfig:
        """Convert configparser or dict to typed GlobalConfig."""
        if isinstance(config, configparser.ConfigParser):
            config_dict: dict[str, str | dict[str, str]] = {}

            # Extract sections without DEFAULT values bleeding in
            for section_name in config.sections():
                section_dict = {}
                for key in config.options(section_name):
                    # Only get keys that are explicitly in this section, not from DEFAULT
                    if config.has_option(section_name, key) and not config.has_option(
                        "DEFAULT", key
                    ):
                        section_dict[key] = config.get(section_name, key)
                config_dict[section_name] = section_dict

            # Add DEFAULT section items separately
            for key, value in config.defaults().items():
                config_dict[key] = value
        else:
            config_dict = config

        # Convert directory paths (only from explicit directory section)
        directory_config: dict[str, Path] = {}
        directory_dict = config_dict.get("directory", {})
        if isinstance(directory_dict, dict):
            # Only process known directory keys to avoid config values
            known_dir_keys = {
                "repo",
                "package",
                "download",
                "storage",
                "backup",
                "icon",
                "settings",
                "logs",
                "cache",
                "tmp",
            }
            for key, value in directory_dict.items():
                if isinstance(value, str) and key in known_dir_keys:
                    directory_config[key] = self._expand_path(value)

        # Get network config
        network_dict = config_dict.get("network", {})
        network_config = NetworkConfig(
            retry_attempts=int(network_dict.get("retry_attempts", 3))
            if isinstance(network_dict, dict)
            else 3,
            timeout_seconds=int(network_dict.get("timeout_seconds", 10))
            if isinstance(network_dict, dict)
            else 10,
        )

        # Get batch mode value
        batch_mode_str = config_dict.get("batch_mode", "true")
        batch_mode = (
            batch_mode_str.lower() == "true" if isinstance(batch_mode_str, str) else True
        )

        return GlobalConfig(
            config_version=str(config_dict.get("config_version", self.DEFAULT_CONFIG_VERSION)),
            max_concurrent_downloads=int(config_dict.get("max_concurrent_downloads", 5)),
            max_backup=int(config_dict.get("max_backup", 1)),
            batch_mode=batch_mode,
            locale=str(config_dict.get("locale", "en_US")),
            log_level=str(config_dict.get("log_level", "INFO")),
            network=network_config,
            directory=DirectoryConfig(**directory_config),
        )

    def save_global_config(self, config: GlobalConfig) -> None:
        """Save global configuration to INI file."""
        parser = configparser.ConfigParser()

        # Main section
        parser["DEFAULT"] = {
            "config_version": config["config_version"],
            "max_concurrent_downloads": str(config["max_concurrent_downloads"]),
            "max_backup": str(config["max_backup"]),
            "batch_mode": str(config["batch_mode"]).lower(),
            "locale": config["locale"],
            "log_level": config["log_level"],
        }

        # Network section
        parser["network"] = {
            "retry_attempts": str(config["network"]["retry_attempts"]),
            "timeout_seconds": str(config["network"]["timeout_seconds"]),
        }

        # Directory section
        parser["directory"] = {key: str(path) for key, path in config["directory"].items()}

        with open(self.settings_file, "w") as f:
            parser.write(f)

    def load_app_config(self, app_name: str) -> AppConfig | None:
        """Load app-specific configuration."""
        app_file = self.apps_dir / f"{app_name}.json"
        if not app_file.exists():
            return None

        try:
            with open(app_file, "rb") as f:
                config_data = orjson.loads(f.read())

            # Migrate old 'hash' field to 'digest' field
            config_data = self._migrate_app_config(config_data)
            return config_data
        except (Exception, OSError) as e:
            raise ValueError(f"Failed to load app config for {app_name}: {e}") from e

    def _migrate_app_config(self, config_data: dict) -> dict:
        """Migrate old config format to new format.

        Args:
            config_data: Raw config data from file

        Returns:
            Migrated config data

        """
        # Migrate 'hash' field to 'digest' field in appimage section
        if "appimage" in config_data and "hash" in config_data["appimage"]:
            hash_value = config_data["appimage"].pop("hash")
            config_data["appimage"]["digest"] = hash_value

        return config_data

    def save_app_config(self, app_name: str, config: AppConfig) -> None:
        """Save app-specific configuration."""
        app_file = self.apps_dir / f"{app_name}.json"

        try:
            with open(app_file, "wb") as f:
                f.write(orjson.dumps(config, option=orjson.OPT_INDENT_2))
        except OSError as e:
            raise ValueError(f"Failed to save app config for {app_name}: {e}") from e

    def load_catalog_entry(self, app_name: str) -> CatalogEntry | None:
        """Load catalog entry for an app from bundled catalog."""
        catalog_file = self.catalog_dir / f"{app_name}.json"
        if not catalog_file.exists():
            return None

        try:
            with open(catalog_file, "rb") as f:
                return orjson.loads(f.read())
        except (Exception, OSError) as e:
            raise ValueError(f"Failed to load catalog entry for {app_name}: {e}") from e

    def list_installed_apps(self) -> list[str]:
        """Get list of installed apps."""
        if not self.apps_dir.exists():
            return []

        return [f.stem for f in self.apps_dir.glob("*.json") if f.is_file()]

    def list_catalog_apps(self) -> list[str]:
        """Get list of available apps in bundled catalog."""
        if not self.catalog_dir.exists():
            # This should not happen if _validate_catalog_directory() passed
            return []

        return [f.stem for f in self.catalog_dir.glob("*.json") if f.is_file()]

    def remove_app_config(self, app_name: str) -> bool:
        """Remove app configuration file."""
        app_file = self.apps_dir / f"{app_name}.json"
        if app_file.exists():
            app_file.unlink()
            return True
        return False

    def ensure_directories_from_config(self, config: GlobalConfig) -> None:
        """Ensure all directories from config exist."""
        for directory in config["directory"].values():
            if isinstance(directory, Path):
                directory.mkdir(parents=True, exist_ok=True)


# Global instance for easy access
config_manager = ConfigManager()
