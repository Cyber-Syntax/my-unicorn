"""Migration utilities and helpers.

Provides functions for detecting and handling config version mismatches
without raising errors, for graceful degradation in commands.
"""

from pathlib import Path
from typing import Any

import orjson
from packaging.version import InvalidVersion, Version

from my_unicorn.constants import APP_CONFIG_VERSION
from my_unicorn.logger import get_logger

# Maximum number of apps to list in migration warning
MAX_APPS_TO_LIST = 5

logger = get_logger(__name__)


def compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic version strings.

    Returns -1 if version1 < version2, 0 if equal, 1 if version1 > version2.
    Uses packaging.Version for robust semantic handling.
    """
    v1_clean = version1.lstrip("v").lower()
    v2_clean = version2.lstrip("v").lower()

    if v1_clean == v2_clean:
        return 0

    try:
        v1 = Version(v1_clean)
        v2 = Version(v2_clean)
        if v1 < v2:
            return -1
        if v1 > v2:
            return 1
        return 0
    except InvalidVersion:
        # Fallback to legacy numeric comparison
        def parse_version(v: str) -> list[int]:
            try:
                return [int(x) for x in v.split(".")]
            except ValueError:
                return [0, 0, 0]

        v1_parts = parse_version(v1_clean)
        v2_parts = parse_version(v2_clean)
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        if v1_parts < v2_parts:
            return -1
        if v1_parts > v2_parts:
            return 1
        return 0


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


def warn_about_migration(config_manager: Any) -> None:
    """Check and warn about apps needing migration.

    Args:
        config_manager: ConfigManager instance with apps_dir attribute.
            Using Any to avoid circular import.

    """
    apps_dir = config_manager.apps_dir
    apps_needing_migration = get_apps_needing_migration(apps_dir)

    if not apps_needing_migration:
        return

    logger.warning(
        "Found %d app(s) with old config format. "
        "Run 'my-unicorn migrate' to upgrade.",
        len(apps_needing_migration),
    )
    logger.info(
        "⚠️  Found %d app(s) with old config format.",
        len(apps_needing_migration),
    )
    logger.info("   Run 'my-unicorn migrate' to upgrade these apps:")
    for app_name, version in apps_needing_migration[:MAX_APPS_TO_LIST]:
        logger.info("   - %s (v%s)", app_name, version)
    if len(apps_needing_migration) > MAX_APPS_TO_LIST:
        remaining = len(apps_needing_migration) - MAX_APPS_TO_LIST
        logger.info("   ... and %d more", remaining)
