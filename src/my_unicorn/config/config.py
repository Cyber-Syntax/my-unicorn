"""Configuration management for my-unicorn AppImage installer.

This module provides a lightweight facade that coordinates all configuration
managers. The actual implementations are in specialized modules:
- global.py: GlobalConfigManager for INI configuration
- app.py: AppConfigManager for per-app JSON configs
- catalog.py: CatalogLoader for bundled catalog access
- parser.py: INI parser utilities
- paths.py: Path constants and utilities

Requirements:
    - orjson: High-performance JSON library (required for all JSON operations)
"""

import importlib
import logging
from pathlib import Path

from my_unicorn.config.app import AppConfigManager
from my_unicorn.config.catalog import CatalogLoader
from my_unicorn.config.paths import Paths
from my_unicorn.domain.types import AppConfig, CatalogEntryV2, GlobalConfig

logger = logging.getLogger(__name__)

# Import from global module (avoiding keyword conflict)
_global_module = importlib.import_module("my_unicorn.config.global")
GlobalConfigManager = _global_module.GlobalConfigManager


class ConfigManager:
    """Facade that coordinates all configuration managers.

    This class provides a unified interface to the configuration system,
    delegating to specialized managers for different concerns.
    """

    def __init__(
        self, config_dir: Path | None = None, catalog_dir: Path | None = None
    ) -> None:
        """Initialize configuration manager.

        Args:
            config_dir: Optional custom config directory.
                Defaults to Paths.CONFIG_DIR
            catalog_dir: Optional custom catalog directory.
                Defaults to Paths.CATALOG_DIR
        """
        # Use Paths class for directory management
        self._config_dir = config_dir or Paths.CONFIG_DIR
        self._catalog_dir = catalog_dir or Paths.CATALOG_DIR

        # Initialize specialized managers
        self.global_config_manager = GlobalConfigManager(self._config_dir)
        self.catalog_loader = CatalogLoader(self._catalog_dir)

        # Determine apps_dir based on config_dir
        apps_dir = self._config_dir / "apps" if config_dir else Paths.APPS_DIR
        self.app_config_manager = AppConfigManager(
            apps_dir, self.catalog_loader
        )

        # Ensure directories and validate catalog
        if config_dir:
            # Custom directory: ensure it exists
            for directory in [self._config_dir, apps_dir]:
                directory.mkdir(parents=True, exist_ok=True)
        else:
            # Use Paths for standard setup
            Paths.ensure_directories()

        Paths.validate_catalog_directory()

    # Path properties
    @property
    def config_dir(self) -> Path:
        """Get the configuration directory path."""
        return self._config_dir

    @property
    def settings_file(self) -> Path:
        """Get the settings file path."""
        return self.global_config_manager.settings_file

    @property
    def apps_dir(self) -> Path:
        """Get the apps configuration directory path."""
        return self.app_config_manager.apps_dir

    @property
    def catalog_dir(self) -> Path:
        """Get the catalog directory path."""
        return self._catalog_dir

    def ensure_directories_from_config(self, config: GlobalConfig) -> None:
        """Ensure all directories from config exist.

        Args:
            config: Global configuration containing directory paths

        Raises:
            ValueError: If a configured path is a file or invalid
        """
        for key, directory in config["directory"].items():
            if directory.exists() and directory.is_file():
                msg = (
                    f"Configured {key} path '{directory}' is a file, "
                    "not a directory"
                )
                raise ValueError(msg)
            directory.mkdir(parents=True, exist_ok=True)

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

    # Catalog loader delegates
    def load_catalog(self, app_name: str) -> CatalogEntryV2:
        """Load catalog entry for an app from bundled catalog.

        Args:
            app_name: Application name

        Returns:
            Catalog entry

        Raises:
            FileNotFoundError: If catalog entry doesn't exist
            ValueError: If catalog entry is invalid
        """
        return self.catalog_loader.load(app_name)

    def list_catalog_apps(self) -> list[str]:
        """Get list of available apps in bundled catalog."""
        return self.catalog_loader.list_apps()

    def catalog_exists(self, app_name: str) -> bool:
        """Check if catalog entry exists for an app.

        Args:
            app_name: Application name

        Returns:
            True if catalog exists, False otherwise
        """
        return self.catalog_loader.exists(app_name)


# Global instance for easy access
config_manager = ConfigManager()
