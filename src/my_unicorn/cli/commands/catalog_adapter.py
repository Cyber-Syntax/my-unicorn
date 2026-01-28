"""Catalog manager adapter for command handlers.

This adapter provides a catalog manager interface for the installation system.
"""

from my_unicorn.config import ConfigManager
from my_unicorn.types import AppStateConfig, CatalogConfig


class CatalogManagerAdapter:
    """Adapter for catalog manager interface used by installation system."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize adapter with config manager.

        Args:
            config_manager: ConfigManager instance

        """
        self.config_manager = config_manager

    def get_available_apps(self) -> dict[str, CatalogConfig]:
        """Get available apps from catalog.

        Returns:
            Dictionary of app names to their configurations

        """
        apps = {}
        for app_name in self.config_manager.list_catalog_apps():
            try:
                config = self.config_manager.load_catalog(app_name)
                apps[app_name] = config
            except (FileNotFoundError, ValueError):
                # Skip invalid entries
                continue
        return apps

    def get_app_config(self, app_name: str) -> CatalogConfig | None:
        """Get configuration for a specific app.

        Args:
            app_name: Name of the app

        Returns:
            App configuration or None if not found

        """
        try:
            return self.config_manager.load_catalog(app_name)
        except (FileNotFoundError, ValueError):
            return None

    def get_installed_app_config(self, app_name: str) -> AppStateConfig | None:
        """Get installed app configuration.

        Args:
            app_name: Name of the app

        Returns:
            Installed app configuration or None if not found

        """
        try:
            return self.config_manager.load_app_config(app_name)
        except (FileNotFoundError, KeyError):
            return None

    def save_app_config(
        self,
        app_name: str,
        config: AppStateConfig,
        *,
        skip_validation: bool = False,
    ) -> None:
        """Save app configuration.

        Args:
            app_name: Name of the app
            config: Configuration to save
            skip_validation: If True, skip schema validation

        """
        self.config_manager.save_app_config(app_name, config, skip_validation)

    def remove_app_config(self, app_name: str) -> bool:
        """Remove app configuration.

        Args:
            app_name: Name of the app

        Returns:
            True if removed, False if not found

        """
        return self.config_manager.remove_app_config(app_name)
