"""App-specific configuration manager for JSON state files."""

import copy
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import orjson

if TYPE_CHECKING:
    from my_unicorn.config.catalog import CatalogLoader

from my_unicorn.config.paths import Paths
from my_unicorn.config.schemas.validator import (
    SchemaValidationError,
    validate_app_state,
)
from my_unicorn.constants import APP_CONFIG_VERSION
from my_unicorn.types import AppStateConfig

logger = logging.getLogger(__name__)


class AppConfigManager:
    """Manages app-specific JSON configurations."""

    def __init__(
        self,
        apps_dir: Path | None = None,
        catalog_manager: "CatalogLoader | None" = None,
    ) -> None:
        """Initialize app config manager.

        Args:
            apps_dir: Apps directory path (defaults to Paths.APPS_DIR)
            catalog_manager: Catalog manager for loading catalog entries
                (optional for testing)

        """
        self.apps_dir = apps_dir or Paths.APPS_DIR
        self.catalog_manager = catalog_manager

    def load_app_config(self, app_name: str) -> dict | None:
        """Load merged effective configuration (SINGLE SOURCE OF TRUTH).

        This is the primary method for loading app configuration.
        Returns fully merged config: Catalog + State + Overrides.

        Args:
            app_name: Name of the application

        Returns:
            Merged configuration dictionary or None if not found

        Raises:
            ValueError: If config file is invalid or needs migration

        """
        raw_config = self.load_raw_app_config(app_name)
        if not raw_config:
            return None
        return self._build_effective_config(raw_config)

    def load_raw_app_config(self, app_name: str) -> AppStateConfig | None:
        """Load raw app state config without merging.

        This loads the raw app state structure (source, catalog_ref, state, overrides)
        without merging catalog or building effective config.
        Use this when you need to modify and save the state.

        Args:
            app_name: Name of the application

        Returns:
            Raw app state config or None if not found

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
                raise ValueError(msg) from None

            # Validate against schema
            validate_app_state(config_data, app_name)

            return cast("AppStateConfig", config_data)
        except SchemaValidationError as e:
            msg = f"Invalid app config for {app_name}: {e}"
            raise ValueError(msg) from e
        except orjson.JSONDecodeError as e:
            msg = f"Invalid JSON in app config for {app_name}: {e}"
            raise ValueError(msg) from e
        except OSError as e:
            msg = f"Failed to load app_config for {app_name}: {e}"
            raise ValueError(msg) from e

    def save_app_config(
        self,
        app_name: str,
        config: AppStateConfig,
        *,
        skip_validation: bool = False,
    ) -> None:
        """Save app-specific configuration.

        Args:
            app_name: Name of the application
            config: App configuration to save
            skip_validation: If True, skip schema validation (use when config
                was recently loaded and validated)

        Raises:
            ValueError: If config cannot be saved

        """
        app_file = self.apps_dir / f"{app_name}.json"

        try:
            # Validate before saving
            if not skip_validation:
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

    def _build_effective_config(self, app_config: AppStateConfig) -> dict:
        """Build merged effective configuration (PRIVATE).

        Merges: Catalog (if exists) + State + Overrides
        This is called internally by load_app_config().

        Args:
            app_config: Raw app state config

        Returns:
            Merged configuration dictionary

        Priority (low to high):
            1. Catalog defaults (if catalog_ref exists)
            2. Runtime state (version, paths, etc.)
            3. User overrides (explicit customizations)

        """
        effective = {}

        # Step 1: Load catalog as base (if referenced)
        catalog_ref = app_config.get("catalog_ref")
        if catalog_ref and self.catalog_manager:
            try:
                catalog_ref_str = cast("str", catalog_ref)
                catalog = self.catalog_manager.load(catalog_ref_str)
                effective = self._deep_copy(cast("dict[str, Any]", catalog))
            except (FileNotFoundError, ValueError):
                # Catalog not found or invalid, skip catalog defaults
                pass

        # Step 2: Merge overrides (for URL installs or user customizations)
        overrides = cast("dict[str, Any]", app_config.get("overrides", {}))
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
