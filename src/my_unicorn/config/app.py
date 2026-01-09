"""App-specific configuration manager for JSON state files."""

import copy
import logging
from pathlib import Path
from typing import Any, cast

import orjson

from my_unicorn.config.paths import Paths
from my_unicorn.config.schemas.validator import (
    SchemaValidationError,
    validate_app_state,
)
from my_unicorn.domain.constants import APP_CONFIG_VERSION
from my_unicorn.domain.types import AppConfig

logger = logging.getLogger(__name__)


class AppConfigManager:
    """Manages app-specific JSON configurations."""

    def __init__(
        self,
        apps_dir: Path | None = None,
        catalog_manager: "Any | None" = None,  # CatalogLoader/CatalogManager
    ) -> None:
        """Initialize app config manager.

        Args:
            apps_dir: Apps directory path (defaults to Paths.APPS_DIR)
            catalog_manager: Catalog manager for loading catalog entries
                (optional for testing)

        """
        self.apps_dir = apps_dir or Paths.APPS_DIR
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
        app_file = self.apps_dir / f"{app_name}.json"
        if not app_file.exists():
            return None

        try:
            with app_file.open("rb") as f:
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
            msg = f"Failed to load app_config for {app_name}: {e}"
            raise ValueError(msg) from e

    def save_app_config(self, app_name: str, config: AppConfig) -> None:
        """Save app-specific configuration.

        Args:
            app_name: Name of the application
            config: App configuration to save

        Raises:
            ValueError: If config cannot be saved

        """
        app_file = self.apps_dir / f"{app_name}.json"

        try:
            # Validate before saving
            validate_app_state(cast("dict[str, Any]", config), app_name)

            with app_file.open("wb") as f:
                f.write(
                    orjson.dumps(
                        config,
                        option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
                    )
                )
        except SchemaValidationError as e:
            msg = f"Cannot save invalid app config for {app_name}: {e}"
            raise ValueError(msg) from e
        except OSError as e:
            msg = f"Failed to save app config for {app_name}: {e}"
            raise ValueError(msg) from e

    def list_installed_apps(self) -> list[str]:
        """Get list of installed apps.

        Returns:
            List of installed application names

        """
        if not self.apps_dir.exists():
            return []

        return [f.stem for f in self.apps_dir.glob("*.json") if f.is_file()]

    def remove_app_config(self, app_name: str) -> bool:
        """Remove app configuration file.

        Args:
            app_name: Name of the application

        Returns:
            True if file was removed, False if it didn't exist

        """
        app_file = self.apps_dir / f"{app_name}.json"
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

        # Note: Do NOT copy the top-level "source" string field
        # ("catalog" or "url") to effective config. The effective config
        # should only have the nested source dict from catalog/overrides
        # which contains {owner, repo, etc.}

        return effective

    def _deep_copy(self, obj: dict) -> dict:
        """Deep copy dictionary.

        Args:
            obj: Dictionary to copy

        Returns:
            Deep copy of dictionary

        """
        return copy.deepcopy(obj)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge override into base.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary with override taking precedence

        """
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
