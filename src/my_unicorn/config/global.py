"""Global configuration manager for INI settings."""

import configparser
import logging
from pathlib import Path

from my_unicorn.config.migration.global_config import ConfigMigration
from my_unicorn.config.parser import (
    ConfigCommentManager,
    _strip_inline_comment,
)
from my_unicorn.config.paths import Paths
from my_unicorn.domain.constants import (
    DEFAULT_CONSOLE_LOG_LEVEL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_BACKUP,
    DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    DIRECTORY_KEYS,
    GLOBAL_CONFIG_VERSION,
    KEY_CONFIG_VERSION,
    KEY_CONSOLE_LOG_LEVEL,
    KEY_LOG_LEVEL,
    KEY_MAX_BACKUP,
    KEY_MAX_CONCURRENT_DOWNLOADS,
    SECTION_DEFAULT,
    SECTION_DIRECTORY,
    SECTION_NETWORK,
)
from my_unicorn.domain.types import (
    DirectoryConfig,
    GlobalConfig,
    NetworkConfig,
)

logger = logging.getLogger(__name__)

# Type alias for raw INI config dictionary
RawConfigDict = dict[str, str | dict[str, str]]


class GlobalConfigManager:
    """Manages global INI configuration."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize global config manager.

        Args:
            config_dir: Configuration directory path
                (defaults to Paths.CONFIG_DIR)

        """
        self.config_dir = config_dir or Paths.CONFIG_DIR
        self.settings_file = self.config_dir / "settings.conf"
        self.migration = ConfigMigration(self.config_dir, self.settings_file)

    def get_default_global_config(self) -> RawConfigDict:
        """Get default global configuration values.

        Returns:
            Default configuration dictionary

        """
        home = Path.home()
        return {
            KEY_CONFIG_VERSION: GLOBAL_CONFIG_VERSION,
            KEY_MAX_CONCURRENT_DOWNLOADS: str(
                DEFAULT_MAX_CONCURRENT_DOWNLOADS
            ),
            KEY_MAX_BACKUP: str(DEFAULT_MAX_BACKUP),
            KEY_LOG_LEVEL: DEFAULT_LOG_LEVEL,
            KEY_CONSOLE_LOG_LEVEL: DEFAULT_CONSOLE_LOG_LEVEL,
            SECTION_NETWORK: {"retry_attempts": "3", "timeout_seconds": "10"},
            SECTION_DIRECTORY: {
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

    def _create_config_from_defaults(
        self, defaults: RawConfigDict
    ) -> configparser.ConfigParser:
        """Create ConfigParser from defaults dictionary.

        Args:
            defaults: Default configuration values

        Returns:
            ConfigParser populated with defaults

        """
        config = configparser.ConfigParser(
            inline_comment_prefixes=("#", ";"),
            interpolation=None,
        )

        # Set flat defaults (skip nested dicts)
        flat_defaults = {}
        for key, value in defaults.items():
            if not isinstance(value, dict):
                flat_defaults[key] = str(value)
        config.read_dict({SECTION_DEFAULT: flat_defaults})

        # Add sections for nested configs
        for key, value in defaults.items():
            if isinstance(value, dict):
                config.add_section(key)
                for subkey, subvalue in value.items():
                    config.set(key, subkey, str(subvalue))

        return config

    def load_global_config(self) -> GlobalConfig:
        """Load global configuration from INI file.

        Returns:
            Loaded global configuration

        """
        defaults = self.get_default_global_config()

        # Read user config if it exists
        if self.settings_file.exists():
            # Create a config parser with only user settings first
            user_config = configparser.ConfigParser(
                inline_comment_prefixes=("#", ";"),
                interpolation=None,
            )
            user_config.read(self.settings_file)

            # Perform migration if needed
            if not self.migration.migrate_if_needed(user_config, defaults):
                # Migration failed, fall back to defaults
                logger.warning(
                    "Configuration migration failed. Resetting to defaults. "
                    "Your previous config has been backed up."
                )
                self.save_global_config(
                    self._convert_to_global_config(defaults)
                )
                # Re-read after saving defaults
                user_config.clear()
                user_config.read(self.settings_file)

            # Now set up config with defaults and user values
            config = self._create_config_from_defaults(defaults)

            # Override with user settings
            config.read(self.settings_file)
        else:
            # Create default config file and set up config
            self.save_global_config(self._convert_to_global_config(defaults))

            config = self._create_config_from_defaults(defaults)

        # After config loading, replay migration messages to logger
        self.migration.replay_messages_to_logger()

        return self._convert_to_global_config(config)

    def save_global_config(self, config: GlobalConfig) -> None:
        """Save global configuration to INI file with user-friendly comments.

        Args:
            config: Global configuration to save

        """
        comment_manager = ConfigCommentManager()

        # Build configuration content with comments
        with self.settings_file.open("w", encoding="utf-8") as f:
            # Write file header
            f.write(comment_manager.get_file_header())

            # Get section comments and key comments
            section_comments = comment_manager.get_section_comments()
            key_comments = comment_manager.get_key_comments()

            # Write DEFAULT section
            f.write(section_comments[SECTION_DEFAULT])
            f.write(f"[{SECTION_DEFAULT}]\n")
            default_data = {
                "config_version": config["config_version"],
                "max_concurrent_downloads": str(
                    config["max_concurrent_downloads"]
                ),
                "max_backup": str(config["max_backup"]),
                "log_level": config["log_level"],
                "console_log_level": config["console_log_level"],
            }

            for key, value in default_data.items():
                inline_comment = key_comments[SECTION_DEFAULT].get(key, "")
                if inline_comment:
                    f.write(f"{key} = {value}  {inline_comment}\n")
                else:
                    f.write(f"{key} = {value}\n")

            # Write network section
            f.write(section_comments[SECTION_NETWORK])
            f.write(f"[{SECTION_NETWORK}]\n")
            # Access network config directly (TypedDict works at runtime)
            network_section = config["network"]
            network_data: dict[str, str] = {
                "retry_attempts": str(network_section["retry_attempts"]),
                "timeout_seconds": str(network_section["timeout_seconds"]),
            }

            for key, value in network_data.items():
                inline_comment = key_comments[SECTION_NETWORK].get(key, "")
                if inline_comment:
                    f.write(f"{key} = {value}  {inline_comment}\n")
                else:
                    f.write(f"{key} = {value}\n")

            # Write directory section
            f.write(section_comments[SECTION_DIRECTORY])
            f.write(f"[{SECTION_DIRECTORY}]\n")
            directory_data: dict[str, str] = {
                key: str(path) for key, path in config["directory"].items()
            }

            for key, value in directory_data.items():
                inline_comment = key_comments[SECTION_DIRECTORY].get(key, "")
                if inline_comment:
                    f.write(f"{key} = {value}  {inline_comment}\n")
                else:
                    f.write(f"{key} = {value}\n")

    def _convert_to_global_config(
        self,
        config: configparser.ConfigParser | RawConfigDict,
    ) -> GlobalConfig:
        """Convert configparser or dict to typed GlobalConfig.

        Args:
            config: Configuration to convert

        Returns:
            Typed global configuration

        """
        if isinstance(config, configparser.ConfigParser):
            config_dict: RawConfigDict = {}

            # Extract sections without DEFAULT values bleeding in
            # Use items() with raw=True to get section-specific values only
            for section_name in config.sections():
                section_dict = {
                    key: value
                    for key, value in config.items(section_name, raw=True)
                    if not config.has_option(SECTION_DEFAULT, key)
                }
                config_dict[section_name] = section_dict

            # Add DEFAULT section items separately
            for key, raw_value in config.defaults().items():
                config_dict[key] = raw_value
        else:
            config_dict = config

        # Helper to strip comments from config values
        def strip_comments(value: str | Path) -> str | Path:
            """Strip inline comments from config values."""
            if isinstance(value, str):
                return _strip_inline_comment(value)
            return value

        # Helper function to safely get scalar config values
        def get_scalar_config(key: str, default: str | int) -> str | int:
            """Get a scalar config value, ensuring it's not a dict."""
            value = config_dict.get(key, default)
            if isinstance(value, dict):
                # This shouldn't happen for scalar values, use default
                return default
            # Strip comments from the value
            cleaned_value = strip_comments(value)
            return cleaned_value if cleaned_value is not None else default

        # Convert directory paths (only from explicit directory section)
        directory_config: dict[str, Path] = {}
        directory_dict = config_dict.get(SECTION_DIRECTORY, {})
        if isinstance(directory_dict, dict):
            # Only process known directory keys to avoid config values
            known_dir_keys = set(DIRECTORY_KEYS)
            for key, value in directory_dict.items():
                if key in known_dir_keys:
                    cleaned_path = strip_comments(value)
                    directory_config[key] = Paths.expand_path(cleaned_path)

        # Get network config
        network_dict = config_dict.get(SECTION_NETWORK, {})

        network_config = NetworkConfig(
            retry_attempts=int(
                strip_comments(network_dict.get("retry_attempts", 3))
            )
            if isinstance(network_dict, dict)
            else 3,
            timeout_seconds=int(
                strip_comments(network_dict.get("timeout_seconds", 10))
            )
            if isinstance(network_dict, dict)
            else 10,
        )

        return GlobalConfig(
            config_version=str(
                get_scalar_config("config_version", GLOBAL_CONFIG_VERSION)
            ),
            max_concurrent_downloads=int(
                get_scalar_config("max_concurrent_downloads", 5)
            ),
            max_backup=int(get_scalar_config("max_backup", 1)),
            log_level=str(get_scalar_config("log_level", "INFO")),
            console_log_level=str(
                get_scalar_config(
                    "console_log_level", DEFAULT_CONSOLE_LOG_LEVEL
                )
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
                settings=directory_config.get("settings", self.config_dir),
                logs=directory_config.get("logs", self.config_dir / "logs"),
                cache=directory_config.get("cache", self.config_dir / "cache"),
                tmp=directory_config.get("tmp", self.config_dir / "tmp"),
            ),
        )
