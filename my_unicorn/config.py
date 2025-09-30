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
from typing import TypedDict, cast

import orjson

# Module-level constants
DEFAULT_CONFIG_VERSION: str = "1.0.1"


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
    console_log_level: str
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


class IconAsset(TypedDict):
    """Icon configuration."""

    url: str
    name: str
    installed: bool


class AppConfig(TypedDict):
    """Per-application configuration."""

    owner: str
    repo: str
    config_version: str
    appimage: AppImageConfig
    github: GitHubConfig
    verification: VerificationConfig
    icon: IconAsset


class CatalogAppImageConfig(TypedDict):
    """AppImage configuration within catalog entry."""

    rename: str
    name_template: str
    characteristic_suffix: list[str]


class CatalogEntry(TypedDict):
    """Catalog entry for an application."""

    owner: str
    repo: str
    appimage: CatalogAppImageConfig
    verification: VerificationConfig
    icon: IconAsset | None


class DirectoryManager:
    """Manages directory operations and path resolution."""

    def __init__(
        self, config_dir: Path | None = None, catalog_dir: Path | None = None
    ) -> None:
        """Initialize directory manager.

        Args:
            config_dir: Optional custom config directory. Defaults to ~/.config/my-unicorn/
            catalog_dir: Optional custom catalog directory. Defaults to bundled catalog.

        """
        self._config_dir: Path = (
            config_dir or Path.home() / ".config" / "my-unicorn"
        )
        self._settings_file: Path = self._config_dir / "settings.conf"
        self._apps_dir: Path = self._config_dir / "apps"
        # Use provided catalog directory or bundled catalog directory
        self._catalog_dir: Path = (
            catalog_dir or Path(__file__).parent / "catalog"
        )

    @property
    def config_dir(self) -> Path:
        """Get the configuration directory path."""
        return self._config_dir

    @property
    def settings_file(self) -> Path:
        """Get the settings file path."""
        return self._settings_file

    @property
    def apps_dir(self) -> Path:
        """Get the apps configuration directory path."""
        return self._apps_dir

    @property
    def catalog_dir(self) -> Path:
        """Get the catalog directory path."""
        return self._catalog_dir

    def expand_path(self, path_str: str) -> Path:
        """Expand and resolve path with ~ and relative path support.

        Args:
            path_str: Path string to expand

        Returns:
            Expanded and resolved Path

        """
        return Path(path_str).expanduser().resolve()

    def ensure_user_directories(self) -> None:
        """Create necessary user directories if they don't exist."""
        # Only create user config directories, catalog is bundled
        for directory in [self._config_dir, self._apps_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def validate_catalog_directory(self) -> None:
        """Validate that the bundled catalog directory exists and contains apps.

        Raises:
            FileNotFoundError: If catalog directory or files don't exist
            NotADirectoryError: If catalog path is not a directory

        """
        if not self._catalog_dir.exists():
            raise FileNotFoundError(
                f"Bundled catalog directory not found: {self._catalog_dir}\n"
                "This indicates a packaging or installation issue."
            )

        if not self._catalog_dir.is_dir():
            raise NotADirectoryError(
                f"Catalog path is not a directory: {self._catalog_dir}"
            )

        # Check if catalog has any JSON files
        catalog_files = list(self._catalog_dir.glob("*.json"))
        if not catalog_files:
            raise FileNotFoundError(
                f"No catalog entries found in: {self._catalog_dir}\n"
                "Expected to find *.json files with app catalog entries."
            )

    def ensure_directories_from_config(self, config: GlobalConfig) -> None:
        """Ensure all directories from config exist.

        Args:
            config: Global configuration containing directory paths

        """
        for directory in config["directory"].values():
            if isinstance(directory, Path):
                directory.mkdir(parents=True, exist_ok=True)


class GlobalConfigManager:
    """Manages global INI configuration."""

    def __init__(self, directory_manager: DirectoryManager) -> None:
        """Initialize global config manager.

        Args:
            directory_manager: Directory manager for path operations

        """
        self.directory_manager = directory_manager

    def get_default_global_config(self) -> dict[str, str | dict[str, str]]:
        """Get default global configuration values.

        Returns:
            Default configuration dictionary

        """
        home = Path.home()
        return {
            "config_version": DEFAULT_CONFIG_VERSION,
            "max_concurrent_downloads": "5",
            "max_backup": "1",
            "batch_mode": "true",
            "locale": "en_US",
            "log_level": "INFO",
            "console_log_level": "WARNING",
            "network": {"retry_attempts": "3", "timeout_seconds": "10"},
            "directory": {
                "repo": str(home / ".local" / "share" / "my-unicorn-repo"),
                "package": str(home / ".local" / "share" / "my-unicorn"),
                "download": str(home / "Downloads"),
                "storage": str(home / "Applications"),
                "backup": str(home / "Applications" / "backups"),
                "icon": str(home / "Applications" / "icons"),
                "settings": str(self.directory_manager.config_dir),
                "logs": str(self.directory_manager.config_dir / "logs"),
                "cache": str(self.directory_manager.config_dir / "cache"),
                "tmp": str(self.directory_manager.config_dir / "tmp"),
            },
        }

    def load_global_config(self) -> GlobalConfig:
        """Load global configuration from INI file.

        Returns:
            Loaded global configuration

        """
        config = configparser.ConfigParser()

        # Set defaults
        defaults = self.get_default_global_config()
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
        if self.directory_manager.settings_file.exists():
            config.read(self.directory_manager.settings_file)
        else:
            # Create default config file
            self.save_global_config(self._convert_to_global_config(defaults))

        return self._convert_to_global_config(config)

    def save_global_config(self, config: GlobalConfig) -> None:
        """Save global configuration to INI file.

        Args:
            config: Global configuration to save

        """
        parser = configparser.ConfigParser()

        # Main section
        parser["DEFAULT"] = {
            "config_version": config["config_version"],
            "max_concurrent_downloads": str(
                config["max_concurrent_downloads"]
            ),
            "max_backup": str(config["max_backup"]),
            "batch_mode": str(config["batch_mode"]).lower(),
            "locale": config["locale"],
            "log_level": config["log_level"],
            "console_log_level": config["console_log_level"],
        }

        # Network section
        parser["network"] = {
            "retry_attempts": str(config["network"]["retry_attempts"]),
            "timeout_seconds": str(config["network"]["timeout_seconds"]),
        }

        # Directory section
        parser["directory"] = {
            key: str(path) for key, path in config["directory"].items()
        }

        with open(
            self.directory_manager.settings_file, "w", encoding="utf-8"
        ) as f:
            parser.write(f)

    def _convert_to_global_config(
        self,
        config: configparser.ConfigParser | dict[str, str | dict[str, str]],
    ) -> GlobalConfig:
        """Convert configparser or dict to typed GlobalConfig.

        Args:
            config: Configuration to convert

        Returns:
            Typed global configuration

        """
        if isinstance(config, configparser.ConfigParser):
            config_dict: dict[str, str | dict[str, str]] = {}

            # Extract sections without DEFAULT values bleeding in
            for section_name in config.sections():
                section_dict = {}
                for key in config.options(section_name):
                    # Only get keys that are explicitly in this section, not from DEFAULT
                    if config.has_option(
                        section_name, key
                    ) and not config.has_option("DEFAULT", key):
                        section_dict[key] = config.get(section_name, key)
                config_dict[section_name] = section_dict

            # Add DEFAULT section items separately
            for key, value in config.defaults().items():
                config_dict[key] = value
        else:
            config_dict = config

        # Helper function to safely get scalar config values
        def get_scalar_config(key: str, default: str | int) -> str | int:
            """Get a scalar config value, ensuring it's not a dict."""
            value = config_dict.get(key, default)
            if isinstance(value, dict):
                # This shouldn't happen for scalar values, but use default if it does
                return default
            return value

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
                    directory_config[key] = self.directory_manager.expand_path(
                        value
                    )

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
        batch_mode_str = get_scalar_config("batch_mode", "true")
        batch_mode = (
            batch_mode_str.lower() == "true"
            if isinstance(batch_mode_str, str)
            else True
        )

        return GlobalConfig(
            config_version=str(
                get_scalar_config("config_version", DEFAULT_CONFIG_VERSION)
            ),
            max_concurrent_downloads=int(
                get_scalar_config("max_concurrent_downloads", 5)
            ),
            max_backup=int(get_scalar_config("max_backup", 1)),
            batch_mode=batch_mode,
            locale=str(get_scalar_config("locale", "en_US")),
            log_level=str(get_scalar_config("log_level", "INFO")),
            console_log_level=str(
                get_scalar_config("console_log_level", "WARNING")
            ),
            network=network_config,
            directory=DirectoryConfig(
                repo=directory_config.get(
                    "repo",
                    Path.home() / ".local" / "share" / "my-unicorn-repo",
                ),
                package=directory_config.get(
                    "package", Path.home() / ".local" / "share" / "my-unicorn"
                ),
                download=directory_config.get(
                    "download", Path.home() / "Downloads"
                ),
                storage=directory_config.get(
                    "storage", Path.home() / "Applications"
                ),
                backup=directory_config.get(
                    "backup", Path.home() / "Applications" / "backups"
                ),
                icon=directory_config.get(
                    "icon", Path.home() / "Applications" / "icons"
                ),
                settings=directory_config.get(
                    "settings", self.directory_manager.config_dir
                ),
                logs=directory_config.get(
                    "logs", self.directory_manager.config_dir / "logs"
                ),
                cache=directory_config.get(
                    "cache", self.directory_manager.config_dir / "cache"
                ),
                tmp=directory_config.get(
                    "tmp", self.directory_manager.config_dir / "tmp"
                ),
            ),
        )


class AppConfigManager:
    """Manages app-specific JSON configurations."""

    def __init__(self, directory_manager: DirectoryManager) -> None:
        """Initialize app config manager.

        Args:
            directory_manager: Directory manager for path operations

        """
        self.directory_manager = directory_manager

    def load_app_config(self, app_name: str) -> AppConfig | None:
        """Load app-specific configuration.

        Args:
            app_name: Name of the application

        Returns:
            App configuration or None if not found

        Raises:
            ValueError: If config file is invalid

        """
        app_file = self.directory_manager.apps_dir / f"{app_name}.json"
        if not app_file.exists():
            return None

        try:
            with open(app_file, "rb") as f:
                config_data = orjson.loads(f.read())

            # Migrate old 'hash' field to 'digest' field
            config_data = self._migrate_app_config(config_data)
            return cast(AppConfig, config_data)
        except (Exception, OSError) as e:
            raise ValueError(
                f"Failed to load app config for {app_name}: {e}"
            ) from e

    def save_app_config(self, app_name: str, config: AppConfig) -> None:
        """Save app-specific configuration.

        Args:
            app_name: Name of the application
            config: App configuration to save

        Raises:
            ValueError: If config cannot be saved

        """
        app_file = self.directory_manager.apps_dir / f"{app_name}.json"

        try:
            with open(app_file, "wb") as f:
                f.write(orjson.dumps(config, option=orjson.OPT_INDENT_2))
        except OSError as e:
            raise ValueError(
                f"Failed to save app config for {app_name}: {e}"
            ) from e

    def list_installed_apps(self) -> list[str]:
        """Get list of installed apps.

        Returns:
            List of installed application names

        """
        if not self.directory_manager.apps_dir.exists():
            return []

        return [
            f.stem
            for f in self.directory_manager.apps_dir.glob("*.json")
            if f.is_file()
        ]

    def remove_app_config(self, app_name: str) -> bool:
        """Remove app configuration file.

        Args:
            app_name: Name of the application

        Returns:
            True if file was removed, False if it didn't exist

        """
        app_file = self.directory_manager.apps_dir / f"{app_name}.json"
        if app_file.exists():
            app_file.unlink()
            return True
        return False

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


class CatalogManager:
    """Manages catalog entries for available applications."""

    def __init__(self, directory_manager: DirectoryManager) -> None:
        """Initialize catalog manager.

        Args:
            directory_manager: Directory manager for path operations

        """
        self.directory_manager = directory_manager

    def load_catalog_entry(self, app_name: str) -> CatalogEntry | None:
        """Load catalog entry for an app from bundled catalog.

        Args:
            app_name: Name of the application

        Returns:
            Catalog entry or None if not found

        Raises:
            ValueError: If catalog entry is invalid

        """
        catalog_file = self.directory_manager.catalog_dir / f"{app_name}.json"
        if not catalog_file.exists():
            return None

        try:
            with open(catalog_file, "rb") as f:
                return cast(CatalogEntry, orjson.loads(f.read()))
        except (Exception, OSError) as e:
            raise ValueError(
                f"Failed to load catalog entry for {app_name}: {e}"
            ) from e

    def list_catalog_apps(self) -> list[str]:
        """Get list of available apps in bundled catalog.

        Returns:
            List of available application names

        """
        if not self.directory_manager.catalog_dir.exists():
            # This should not happen if validate_catalog_directory() passed
            return []

        return [
            f.stem
            for f in self.directory_manager.catalog_dir.glob("*.json")
            if f.is_file()
        ]


class ConfigManager:
    """Facade that coordinates all configuration managers."""

    DEFAULT_CONFIG_VERSION: str = (
        DEFAULT_CONFIG_VERSION  # Maintain backward compatibility
    )

    def __init__(
        self, config_dir: Path | None = None, catalog_dir: Path | None = None
    ) -> None:
        """Initialize configuration manager.

        Args:
            config_dir: Optional custom config directory. Defaults to ~/.config/my-unicorn/
            catalog_dir: Optional custom catalog directory. Defaults to bundled catalog.

        """
        self.directory_manager = DirectoryManager(config_dir, catalog_dir)
        self.global_config_manager = GlobalConfigManager(
            self.directory_manager
        )
        self.app_config_manager = AppConfigManager(self.directory_manager)
        self.catalog_manager = CatalogManager(self.directory_manager)

        # Initialize directories and validation
        self.directory_manager.ensure_user_directories()
        self.directory_manager.validate_catalog_directory()

    # Directory manager delegates
    @property
    def config_dir(self) -> Path:
        """Get the configuration directory path."""
        return self.directory_manager.config_dir

    @property
    def settings_file(self) -> Path:
        """Get the settings file path."""
        return self.directory_manager.settings_file

    @property
    def apps_dir(self) -> Path:
        """Get the apps configuration directory path."""
        return self.directory_manager.apps_dir

    @property
    def catalog_dir(self) -> Path:
        """Get the catalog directory path."""
        return self.directory_manager.catalog_dir

    def ensure_directories_from_config(self, config: GlobalConfig) -> None:
        """Ensure all directories from config exist."""
        self.directory_manager.ensure_directories_from_config(config)

    # Global config manager delegates
    def load_global_config(self) -> GlobalConfig:
        """Load global configuration from INI file."""
        return self.global_config_manager.load_global_config()

    def save_global_config(self, config: GlobalConfig) -> None:
        """Save global configuration to INI file."""
        self.global_config_manager.save_global_config(config)

    # App config manager delegates
    def load_app_config(self, app_name: str) -> AppConfig | None:
        """Load app-specific configuration."""
        return self.app_config_manager.load_app_config(app_name)

    def save_app_config(self, app_name: str, config: AppConfig) -> None:
        """Save app-specific configuration."""
        self.app_config_manager.save_app_config(app_name, config)

    def list_installed_apps(self) -> list[str]:
        """Get list of installed apps."""
        return self.app_config_manager.list_installed_apps()

    def remove_app_config(self, app_name: str) -> bool:
        """Remove app configuration file."""
        return self.app_config_manager.remove_app_config(app_name)

    # Catalog manager delegates
    def load_catalog_entry(self, app_name: str) -> CatalogEntry | None:
        """Load catalog entry for an app from bundled catalog."""
        return self.catalog_manager.load_catalog_entry(app_name)

    def list_catalog_apps(self) -> list[str]:
        """Get list of available apps in bundled catalog."""
        return self.catalog_manager.list_catalog_apps()


# Global instance for easy access
config_manager = ConfigManager()
