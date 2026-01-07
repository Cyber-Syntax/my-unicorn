"""Migration utilities and helpers.

Provides functions for detecting and handling config version mismatches
without raising errors, for graceful degradation in commands.
"""

from pathlib import Path
from typing import Any

import orjson

from my_unicorn.domain.constants import APP_CONFIG_VERSION
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def needs_migration_from_config(config: dict[str, Any]) -> bool:
    """Check if a loaded config dict needs migration.

    Args:
        config: Loaded config dict

    Returns:
        True if migration needed, False otherwise

    """
    if not config:
        return False

    try:
        current_version = config.get("config_version", "1.0.0")
        return current_version != APP_CONFIG_VERSION
    except Exception:
        return False


def needs_app_migration(app_config_path: Path) -> bool:
    """Check if app config needs migration without raising errors.

    Args:
        app_config_path: Path to app config file

    Returns:
        True if migration needed, False otherwise

    """
    try:
        if not app_config_path.exists():
            return False

        with app_config_path.open("rb") as f:
            config = orjson.loads(f.read())

        current_version = config.get("config_version", "1.0.0")
        return current_version != APP_CONFIG_VERSION

    except Exception as e:
        logger.debug(
            "Error checking config version for %s: %s", app_config_path, e
        )
        return False


def get_config_version(app_config_path: Path) -> str | None:
    """Get config version without raising errors.

    Args:
        app_config_path: Path to app config file

    Returns:
        Config version string, or None if cannot be determined

    """
    try:
        if not app_config_path.exists():
            return None

        with app_config_path.open("rb") as f:
            config = orjson.loads(f.read())

        return config.get("config_version", "1.0.0")

    except Exception as e:
        logger.debug(
            "Error reading config version for %s: %s", app_config_path, e
        )
        return None


def get_apps_needing_migration(apps_dir: Path) -> list[tuple[str, str]]:
    """Get list of apps that need migration.

    Args:
        apps_dir: Directory containing app configs

    Returns:
        List of (app_name, current_version) tuples for apps needing migration

    """
    apps_to_migrate: list[tuple[str, str]] = []

    if not apps_dir.exists():
        return apps_to_migrate

    for app_file in apps_dir.glob("*.json"):
        if not app_file.is_file():
            continue

        app_name = app_file.stem
        current_version = get_config_version(app_file)

        if current_version and current_version != APP_CONFIG_VERSION:
            apps_to_migrate.append((app_name, current_version))

    return apps_to_migrate
