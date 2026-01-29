"""Catalog loader for AppImage catalog entries.

This module handles loading and validating catalog entries from the bundled
catalog directory, ensuring they conform to the v2 catalog schema.
"""

from pathlib import Path
from typing import cast

import orjson

from my_unicorn.config.paths import Paths
from my_unicorn.logger import get_logger
from my_unicorn.types import CatalogConfig

logger = get_logger(__name__)


class CatalogLoader:
    """Load and validate app catalog entries."""

    def __init__(self, catalog_dir: Path | None = None) -> None:
        """Initialize catalog loader.

        Args:
            catalog_dir: Optional custom catalog directory.
                        Defaults to bundled catalog.
        """
        self.catalog_dir = catalog_dir or Paths.CATALOG_DIR

    def load(self, app_name: str) -> CatalogConfig:
        """Load catalog entry for app.

        Args:
            app_name: Application name

        Returns:
            Catalog entry dictionary

        Raises:
            FileNotFoundError: If catalog entry doesn't exist
            ValueError: If catalog entry is invalid
        """
        path = self.catalog_dir / f"{app_name}.json"

        if not path.exists():
            msg = f"Catalog entry not found for '{app_name}'"
            raise FileNotFoundError(msg)

        # Load JSON
        with path.open("rb") as f:
            try:
                data = orjson.loads(f.read())
            except orjson.JSONDecodeError as e:
                msg = f"Invalid JSON in catalog entry for '{app_name}': {e}"
                raise ValueError(msg) from e

        return cast("CatalogConfig", data)

    def load_all(self) -> tuple[dict[str, CatalogConfig], list[str]]:
        """Load all catalog entries.

        Returns:
            Tuple of (catalog_entries, failed_apps) where:
            - catalog_entries: Dictionary mapping app names to catalog entries
            - failed_apps: List of app names that failed to load
        """
        catalog_entries = {}
        failed_apps = []

        for path in self.catalog_dir.glob("*.json"):
            app_name = path.stem
            try:
                catalog_entries[app_name] = self.load(app_name)
            except (FileNotFoundError, ValueError) as e:
                # Skip invalid entries but log the error
                logger.warning(
                    "Skipping invalid catalog entry %s: %s", app_name, e
                )
                failed_apps.append(app_name)

        return catalog_entries, failed_apps

    def exists(self, app_name: str) -> bool:
        """Check if catalog entry exists.

        Args:
            app_name: Application name

        Returns:
            True if catalog entry exists, False otherwise
        """
        path = self.catalog_dir / f"{app_name}.json"
        return path.exists()

    def list_apps(self) -> list[str]:
        """List all available apps in catalog.

        Returns:
            List of app names
        """
        return [path.stem for path in self.catalog_dir.glob("*.json")]

    def validate_catalog(self) -> tuple[list[str], list[str]]:
        """Validate all catalog entries.

        Returns:
            Tuple of (valid_apps, invalid_apps)
        """
        valid_apps = []
        invalid_apps = []

        for app_name in self.list_apps():
            try:
                self.load(app_name)
                valid_apps.append(app_name)
            except (FileNotFoundError, ValueError):
                invalid_apps.append(app_name)

        return valid_apps, invalid_apps
