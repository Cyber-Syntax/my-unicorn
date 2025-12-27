"""Configuration management for my-unicorn AppImage installer.

This module handles both global INI configuration and per-app JSON
configurations. It provides path resolution, validation, and default values
as specified in the architecture documentation.

The catalog system uses bundled catalog files (v2/catalog/*.json) rather than
copying them to the user's config directory, reducing disk usage and ensuring
the catalog is always up-to-date with the package.

Requirements:
    - orjson: High-performance JSON library (required for all JSON operations)
"""

import configparser
from datetime import datetime
from pathlib import Path
from typing import cast

import orjson

from my_unicorn.constants import (
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    DEFAULT_APPS_DIR_NAME,
    DEFAULT_CONFIG_SUBDIR,
    DEFAULT_CONSOLE_LOG_LEVEL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_BACKUP,
    DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    DIRECTORY_KEYS,
    GLOBAL_CONFIG_VERSION,
    ISO_DATETIME_FORMAT,
    KEY_CONFIG_VERSION,
    KEY_CONSOLE_LOG_LEVEL,
    KEY_LOG_LEVEL,
    KEY_MAX_BACKUP,
    KEY_MAX_CONCURRENT_DOWNLOADS,
    SECTION_DEFAULT,
    SECTION_DIRECTORY,
    SECTION_NETWORK,
)
from my_unicorn.types import (
    AppConfig,
    CatalogEntry,
    DirectoryConfig,
    GlobalConfig,
    NetworkConfig,
)


def _strip_inline_comment(value: str) -> str:
    """Strip inline comments from configuration values.

    Args:
        value: Configuration value that may contain inline comment

    Returns:
        Value with inline comment removed (anything after '  #')

    """
    if "  #" in value:
        return value.split("  #")[0].strip()
    return value


class CommentAwareConfigParser(configparser.ConfigParser):
    """ConfigParser that strips inline comments when reading values."""

    def get(self, section, option, **kwargs):
        """Get a configuration value with inline comments stripped."""
        value = super().get(section, option, **kwargs)
        return _strip_inline_comment(value)


class ConfigCommentManager:
    """Manages configuration file comments for user-friendly documentation."""

    @staticmethod
    def get_file_header() -> str:
        """Generate file header comment with description and timestamp.

        Returns:
            Header comment string for the configuration file

        """
        timestamp = datetime.now().strftime(ISO_DATETIME_FORMAT)
        return f"""# My-Unicorn AppImage Installer Configuration
# This file contains settings for the my-unicorn AppImage installer.
# You can modify these values to customize the behavior of the application.
#
# Last updated: {timestamp}
# Configuration version: {GLOBAL_CONFIG_VERSION}

"""

    @staticmethod
    def get_section_comments() -> dict[str, str]:
        """Get comments for each configuration section.

        Returns:
            Dictionary mapping section names to their comment strings

        """
        return {
            SECTION_DEFAULT: """# ========================================
# MAIN CONFIGURATION
# ========================================
# These settings control the overall behavior of my-unicorn.
#
# config_version: Version of configuration format (DO NOT EDIT)
# max_concurrent_downloads: Max simultaneous downloads (1-10)
# max_backup: Number of backup copies to keep when updating apps (0-5)
# log_level: Detail level for log files (DEBUG, INFO, WARNING, ERROR)
# console_log_level: Console output detail level (DEBUG, INFO, etc.)

""",
            SECTION_NETWORK: """
# ========================================
# NETWORK CONFIGURATION
# ========================================
# Settings for downloading AppImages and accessing repositories.
#
# retry_attempts: Number of times to retry failed downloads (1-10)
# timeout_seconds: Seconds to wait before timing out requests (5-60)

""",
            SECTION_DIRECTORY: """
# ========================================
# DIRECTORY PATHS
# ========================================
# Customize where my-unicorn stores files and directories.
# Use absolute paths or paths starting with ~ for home directory.
#
# repo: Source code repository for my-unicorn cli (e.g git cloned)
# package: Installation directory for my-unicorn (necessary code files)
# download: Temporary download location for AppImages
# storage: Where installed AppImages are stored
# backup: Backup location for old AppImage versions
# icon: Directory for application icons
# settings: Configuration and settings directory
# logs: Log files location
# cache: Temporary cache directory
# tmp: Temporary files directory

""",
        }

    @staticmethod
    def get_key_comments() -> dict[str, dict[str, str]]:
        """Get inline comments for specific configuration keys.

        Returns:
            Nested dictionary mapping section -> key -> comment

        """
        return {
            SECTION_DEFAULT: {
                KEY_CONFIG_VERSION: "# DO NOT MODIFY - Config format version",
            },
            SECTION_NETWORK: {},
            SECTION_DIRECTORY: {},
        }


class DirectoryManager:
    """Manages directory operations and path resolution."""

    def __init__(
        self, config_dir: Path | None = None, catalog_dir: Path | None = None
    ) -> None:
        """Initialize directory manager.

        Args:
            config_dir: Optional custom config directory. Defaults to
                ~/.config/my-unicorn/
            catalog_dir: Optional custom catalog directory. Defaults to
                bundled catalog.

        """
        self._config_dir: Path = (
            config_dir or Path.home() / CONFIG_DIR_NAME / DEFAULT_CONFIG_SUBDIR
        )
        self._settings_file: Path = self._config_dir / CONFIG_FILE_NAME
        self._apps_dir: Path = self._config_dir / DEFAULT_APPS_DIR_NAME
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
            ValueError: If catalog entries fail schema validation

        """
        from my_unicorn.schemas import SchemaValidationError, validate_catalog

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

        # Validate all catalog files against schema
        invalid_catalogs = []
        for catalog_file in catalog_files:
            try:
                with open(catalog_file, "rb") as f:
                    catalog_data = orjson.loads(f.read())
                validate_catalog(catalog_data, catalog_file.stem)
            except SchemaValidationError as e:
                invalid_catalogs.append(f"{catalog_file.stem}: {e}")
            except Exception as e:
                invalid_catalogs.append(
                    f"{catalog_file.stem}: Failed to load - {e}"
                )

        if invalid_catalogs:
            raise ValueError(
                "Invalid catalog entries found:\n"
                + "\n".join(f"  - {err}" for err in invalid_catalogs)
            )

    def ensure_directories_from_config(self, config: GlobalConfig) -> None:
        """Ensure all directories from config exist.

        Args:
            config: Global configuration containing directory paths

        """
        for directory in config["directory"].values():
            directory.mkdir(parents=True, exist_ok=True)


class GlobalConfigManager:
    """Manages global INI configuration."""

    def __init__(self, directory_manager: DirectoryManager) -> None:
        """Initialize global config manager.

        Args:
            directory_manager: Directory manager for path operations

        """
        self.directory_manager = directory_manager
        # Import migration module here to avoid circular imports
        from my_unicorn.migration.global_config import ConfigMigration

        self.migration = ConfigMigration(directory_manager)

    def get_default_global_config(self) -> dict[str, str | dict[str, str]]:
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
                "settings": str(self.directory_manager.config_dir),
                "logs": str(self.directory_manager.config_dir / "logs"),
                "cache": str(self.directory_manager.config_dir / "cache"),
                "tmp": str(self.directory_manager.config_dir / "tmp"),
            },
        }

    def _create_config_from_defaults(
        self, defaults: dict[str, str | dict[str, str]]
    ) -> CommentAwareConfigParser:
        """Create ConfigParser from defaults dictionary.

        Args:
            defaults: Default configuration values

        Returns:
            ConfigParser populated with defaults

        """
        config = CommentAwareConfigParser()

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
        if self.directory_manager.settings_file.exists():
            # Create a config parser with only user settings first
            user_config = CommentAwareConfigParser()
            user_config.read(self.directory_manager.settings_file)

            # Perform migration if needed (no circular import)
            if not self.migration.migrate_if_needed(user_config, defaults):
                # Migration failed, fall back to defaults
                print(
                    "Configuration migration failed, using default settings."
                )
                self.save_global_config(
                    self._convert_to_global_config(defaults)
                )
                # Re-read after saving defaults
                user_config.clear()
                user_config.read(self.directory_manager.settings_file)

            # Now set up config with defaults and user values
            config = self._create_config_from_defaults(defaults)

            # Override with user settings
            config.read(self.directory_manager.settings_file)
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
        with open(
            self.directory_manager.settings_file, "w", encoding="utf-8"
        ) as f:
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
            # Cast the top-level config to a plain dict before indexing with
            # SECTION_* constants. Type checkers require string literals when
            # interacting with TypedDicts directly.
            network_section = cast("dict", config)[SECTION_NETWORK]
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
                key: str(path)
                for key, path in cast("dict", config)[
                    SECTION_DIRECTORY
                ].items()
            }

            for key, value in directory_data.items():
                inline_comment = key_comments[SECTION_DIRECTORY].get(key, "")
                if inline_comment:
                    f.write(f"{key} = {value}  {inline_comment}\n")
                else:
                    f.write(f"{key} = {value}\n")

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
                    # Only get keys that are explicitly in this section,
                    # not from DEFAULT
                    if config.has_option(
                        section_name, key
                    ) and not config.has_option(SECTION_DEFAULT, key):
                        section_dict[key] = config.get(section_name, key)
                config_dict[section_name] = section_dict

            # Add DEFAULT section items separately
            for key, raw_value in config.defaults().items():
                # Strip inline comments from default values too
                config_dict[key] = _strip_inline_comment(raw_value)
        else:
            config_dict = config

        # Helper to strip comments from config values
        def strip_comments(value):
            """Strip inline comments from config values."""
            return (
                _strip_inline_comment(value)
                if isinstance(value, str)
                else value
            )

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
                    directory_config[key] = self.directory_manager.expand_path(
                        cleaned_path
                    )

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

    def __init__(
        self,
        directory_manager: DirectoryManager,
        catalog_manager: "CatalogManager | None" = None,
    ) -> None:
        """Initialize app config manager.

        Args:
            directory_manager: Directory manager for path operations
            catalog_manager: Catalog manager for loading catalog entries (optional for testing)

        """
        self.directory_manager = directory_manager
        self.catalog_manager = catalog_manager

    def load_app_config(self, app_name: str) -> AppConfig | None:
        """Load app-specific configuration.

        Args:
            app_name: Name of the application

        Returns:
            App configuration or None if not found

        Raises:
            ValueError: If config file is invalid or needs migration

        """
        from my_unicorn.constants import APP_CONFIG_VERSION
        from my_unicorn.schemas import (
            SchemaValidationError,
            validate_app_state,
        )

        app_file = self.directory_manager.apps_dir / f"{app_name}.json"
        if not app_file.exists():
            return None

        try:
            with open(app_file, "rb") as f:
                config_data = orjson.loads(f.read())

            # Validate config version (no auto-migration)
            current_version = config_data.get("config_version")
            if current_version != APP_CONFIG_VERSION:
                msg = (
                    f"Config for '{app_name}' is version {current_version}, "
                    f"expected {APP_CONFIG_VERSION}. "
                    f"Run 'my-unicorn migrate' to upgrade."
                )
                raise ValueError(msg)

            # Validate against schema
            validate_app_state(config_data, app_name)

            return cast("AppConfig", config_data)
        except SchemaValidationError as e:
            msg = f"Invalid app config for {app_name}: {e}"
            raise ValueError(msg) from e
        except orjson.JSONDecodeError as e:
            msg = f"Invalid JSON in app config for {app_name}: {e}"
            raise ValueError(msg) from e
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
        from my_unicorn.schemas import (
            SchemaValidationError,
            validate_app_state,
        )

        app_file = self.directory_manager.apps_dir / f"{app_name}.json"

        try:
            # Validate before saving
            validate_app_state(config, app_name)

            with open(app_file, "wb") as f:
                f.write(orjson.dumps(config, option=orjson.OPT_INDENT_2))
        except SchemaValidationError as e:
            msg = f"Cannot save invalid app config for {app_name}: {e}"
            raise ValueError(msg) from e
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

    def get_effective_config(self, app_name: str) -> dict:
        """Get merged effective configuration.

        This is the SINGLE source of truth for app configuration.
        Merges: Catalog (if exists) + State + Overrides

        Args:
            app_name: Application name

        Returns:
            Merged configuration dictionary

        Raises:
            ValueError: If app config not found

        Priority (low to high):
            1. Catalog defaults (if catalog_ref exists)
            2. Runtime state (version, paths, etc.)
            3. User overrides (explicit customizations)

        """
        app_config = self.load_app_config(app_name)
        if not app_config:
            msg = f"No config found for {app_name}"
            raise ValueError(msg)

        effective = {}

        # Step 1: Load catalog as base (if referenced)
        catalog_ref = app_config.get("catalog_ref")
        if catalog_ref and self.catalog_manager:
            catalog = self.catalog_manager.load_catalog_entry(catalog_ref)
            if catalog:
                effective = self._deep_copy(catalog)

        # Step 2: Merge overrides (for URL installs or user customizations)
        overrides = app_config.get("overrides", {})
        if overrides:
            effective = self._deep_merge(effective, overrides)

        # Step 3: Inject runtime state (version, paths, etc.)
        state = app_config.get("state", {})
        effective["state"] = state
        effective["config_version"] = app_config.get("config_version")

        # Note: Do NOT copy the top-level "source" string field ("catalog" or "url")
        # to effective config. The effective config should only have the nested
        # source dict from catalog/overrides which contains {owner, repo, etc.}

        return effective

    def _deep_copy(self, obj: dict) -> dict:
        """Deep copy dictionary.

        Args:
            obj: Dictionary to copy

        Returns:
            Deep copy of dictionary

        """
        import copy

        return copy.deepcopy(obj)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge override into base.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary with override taking precedence

        """
        import copy

        result = copy.deepcopy(base)

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare semantic versions.

        Args:
            version1: First version (e.g., "1.0.0")
            version2: Second version (e.g., "2.0.0")

        Returns:
            -1 if v1 < v2, 0 if equal, 1 if v1 > v2

        """

        def parse_version(v: str) -> list[int]:
            try:
                return [int(x) for x in v.split(".")]
            except ValueError:
                return [0, 0, 0]

        v1 = parse_version(version1)
        v2 = parse_version(version2)

        max_len = max(len(v1), len(v2))
        v1.extend([0] * (max_len - len(v1)))
        v2.extend([0] * (max_len - len(v2)))

        for a, b in zip(v1, v2, strict=False):
            if a < b:
                return -1
            if a > b:
                return 1
        return 0


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
        from my_unicorn.schemas import SchemaValidationError, validate_catalog

        catalog_file = self.directory_manager.catalog_dir / f"{app_name}.json"
        if not catalog_file.exists():
            return None

        try:
            with open(catalog_file, "rb") as f:
                catalog_data = orjson.loads(f.read())

            # Validate against schema
            validate_catalog(catalog_data, app_name)

            return cast("CatalogEntry", catalog_data)
        except SchemaValidationError as e:
            raise ValueError(
                f"Invalid catalog entry for {app_name}: {e}"
            ) from e
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
        # Create catalog manager first as app_config_manager depends on it
        self.catalog_manager = CatalogManager(self.directory_manager)
        self.app_config_manager = AppConfigManager(
            self.directory_manager, self.catalog_manager
        )

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
