"""Path constants and utilities for my-unicorn configuration.

This module centralizes all path management for the application,
making it easy to reference and override paths consistently.
"""

from pathlib import Path

from my_unicorn.domain.constants import (
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    DEFAULT_APPS_DIR_NAME,
    DEFAULT_CONFIG_SUBDIR,
)


class Paths:
    """Application paths and directory structure."""

    # Base directories
    HOME_DIR = Path.home()
    CONFIG_BASE_DIR = HOME_DIR / DEFAULT_CONFIG_SUBDIR
    CONFIG_DIR = CONFIG_BASE_DIR / CONFIG_DIR_NAME

    # Catalog directory (bundled with package)
    PACKAGE_DIR = Path(__file__).parent.parent
    CATALOG_DIR = PACKAGE_DIR / "catalog"

    # User config directories
    CACHE_DIR = CONFIG_DIR / "cache" / "releases"
    APPS_DIR = CONFIG_DIR / DEFAULT_APPS_DIR_NAME
    LOGS_DIR = CONFIG_DIR / "logs"
    BACKUPS_DIR = APPS_DIR / "backups"

    # Configuration files
    GLOBAL_CONFIG_FILE = CONFIG_DIR / CONFIG_FILE_NAME

    # Migration directories
    MIGRATION_BACKUP_DIR = APPS_DIR / "backups"

    @classmethod
    def get_app_state_path(cls, app_name: str) -> Path:
        """Get path to app state file.

        Args:
            app_name: Application name

        Returns:
            Path to app state JSON file
        """
        return cls.APPS_DIR / f"{app_name}.json"

    @classmethod
    def get_catalog_entry_path(cls, app_name: str) -> Path:
        """Get path to catalog entry file.

        Args:
            app_name: Application name

        Returns:
            Path to catalog JSON file
        """
        return cls.CATALOG_DIR / f"{app_name}.json"

    @classmethod
    def get_cache_path(cls, cache_key: str) -> Path:
        """Get path to cache file.

        Args:
            cache_key: Cache identifier (e.g., "owner_repo")

        Returns:
            Path to cache JSON file
        """
        return cls.CACHE_DIR / f"{cache_key}.json"

    @classmethod
    def ensure_directories(cls) -> None:
        """Create necessary directories if they don't exist."""
        for directory in [
            cls.CONFIG_DIR,
            cls.CACHE_DIR,
            cls.APPS_DIR,
            cls.LOGS_DIR,
            cls.BACKUPS_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
